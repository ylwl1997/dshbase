#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import paramiko
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PASS = "100.66.1.16", "root", "60851.org"


def run(c, cmd, timeout=180):
    print("\n====", cmd[:180].replace("\n", " | "))
    _, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    text = (out + (("\nSTDERR:\n" + err) if err.strip() else "")).rstrip()
    if len(text) > 18000:
        text = text[:4000] + "\n...\n" + text[-14000:]
    print(text)
    print("exit=", code)
    return code, out


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=20)
    print("SSH OK", HOST)

    sftp = c.open_sftp()
    sftp.put(
        r"C:\Users\Administrator\dshbase\K72_GLink_sync\Code\demo\test_glink_dual.c",
        "/opt/soft/K72_GLink/Code/demo/test_glink_dual.c",
    )
    sftp.close()

    run(c, """
lspci -nn -d 10ee:7028
lsmod | grep xdma_minimal || insmod /opt/soft/K72_GLink/Drive/xdma_minimal.ko
ls -l /dev/xdma*_user
""")

    run(c, """
cd /opt/soft/K72_GLink/Code/demo
gcc -O2 -I../api -o test_glink_dual test_glink_dual.c ../api/glink_api.c 2>&1 | grep -E 'error:' || echo compile_ok
test -x test_glink_api || make -s
echo '===== 1) rate-sync ====='
./test_glink_api rate-sync 2>&1 | tail -25
""", timeout=90)

    run(c, """
cd /opt/soft/K72_GLink/Code/demo
echo '===== 2) LINK detect ====='
./test_glink_api link 2>&1
""", timeout=90)

    run(c, """
cd /opt/soft/K72_GLink/Code/demo
echo '===== 3) dual Ctrl NC=0 NT=1 (expect CH_A) ====='
./test_glink_dual 0 1 2>&1
echo EXIT_01:$?
""", timeout=120)

    # If 0->1 failed on link, still try swap; if pass, also try reverse as bonus
    run(c, """
cd /opt/soft/K72_GLink/Code/demo
echo '===== 4) dual Ctrl NC=1 NT=0 ====='
./test_glink_dual 1 0 2>&1
echo EXIT_10:$?
""", timeout=120)

    c.close()


if __name__ == "__main__":
    main()
