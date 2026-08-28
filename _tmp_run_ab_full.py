# -*- coding: utf-8 -*-
import paramiko
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("100.66.1.16", username="root", password="60851.org", timeout=20)
sftp = c.open_sftp()
for loc, rem in [
    (r"C:\Users\Administrator\dshbase\K72_GLink_sync\Code\demo\test_glink_api.c",
     "/opt/soft/K72_GLink/Code/demo/test_glink_api.c"),
    (r"C:\Users\Administrator\dshbase\K72_GLink_sync\Code\api\glink_api.c",
     "/opt/soft/K72_GLink/Code/api/glink_api.c"),
    (r"C:\Users\Administrator\dshbase\K72_GLink_sync\Code\api\glink_regs.h",
     "/opt/soft/K72_GLink/Code/api/glink_regs.h"),
]:
    sftp.put(loc, rem)
    print("put", rem)
sftp.close()

stdin, stdout, stderr = c.exec_command(
    "cd /opt/soft/K72_GLink/Code/demo && "
    "gcc -Wall -O2 -I../api -o test_glink_api test_glink_api.c ../api/glink_api.c 2>&1",
    timeout=90,
)
comp = stdout.read().decode("utf-8", "replace")
print(comp)
if "error:" in comp:
    print(stderr.read().decode("utf-8", "replace")[:2000])
    c.close()
    sys.exit(1)

print("===== RUN ab-full =====", flush=True)
stdin, stdout, stderr = c.exec_command(
    "cd /opt/soft/K72_GLink/Code/demo && ./test_glink_api ab-full 2>&1",
    timeout=600,
)
chan = stdout.channel
parts = []
deadline = time.time() + 560
while True:
    if chan.recv_ready():
        chunk = chan.recv(65536).decode("utf-8", "replace")
        parts.append(chunk)
        sys.stdout.write(chunk)
        sys.stdout.flush()
    if chan.recv_stderr_ready():
        chunk = chan.recv_stderr(65536).decode("utf-8", "replace")
        parts.append(chunk)
        sys.stdout.write(chunk)
        sys.stdout.flush()
    if chan.exit_status_ready():
        while chan.recv_ready():
            chunk = chan.recv(65536).decode("utf-8", "replace")
            parts.append(chunk)
            sys.stdout.write(chunk)
        break
    if time.time() > deadline:
        print("\nTIMEOUT killing...")
        break
    time.sleep(0.15)

status = chan.recv_exit_status() if chan.exit_status_ready() else -1
text = "".join(parts)
open(r"C:\Users\Administrator\dshbase\_tmp_ab_full_out.txt", "w", encoding="utf-8").write(text)
print("\n===== exit", status, "=====")
# print result lines only
print("\n----- RESULT LINES -----")
for line in text.splitlines():
    s = line.strip()
    if s.startswith(">>>>") or "汇总:" in s or s.startswith("========"):
        print(s)
c.close()
sys.exit(0 if status == 0 else 1)
