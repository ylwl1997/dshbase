import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.66.1.16", username="root", password="60851.org", timeout=30)

def run(c, timeout=120):
    print("====", c, "====")
    stdin, stdout, stderr = ssh.exec_command(c, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print("STDERR:", err)

cmds = [
    "uname -a",
    "ls -la /opt/soft/Driver/GLink/",
    "lsmod | grep -E 'cvg|xdma' || true",
    "lspci -nn | grep -Ei '289e|10ee|7120|7028|Cavige|Xilinx' || true",
    "ls -la /dev/cvgdev* /dev/xdma0_* 2>/dev/null || true",
    "ls -la /opt/soft/Driver/GLink/WGLK220_V3 2>/dev/null | head -40",
    "ls -la /opt/soft/Driver/GLink/Driver/ 2>/dev/null",
]
for c in cmds:
    run(c)
ssh.close()
