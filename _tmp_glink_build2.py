import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.66.1.16", username="root", password="60851.org", timeout=30)

def run(c, timeout=300):
    print("====", c[:140], "====")
    stdin, stdout, stderr = ssh.exec_command(c, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out:
        print(out[-12000:] if len(out) > 12000 else out)
    if err.strip():
        print("STDERR:", err[-6000:] if len(err) > 6000 else err)
    return out, err

# Fix build: reconfigure from current dir OR compile Demo manually
run("ls -la /opt/soft/Driver/GLink/WGLK220_V3/WinApi/FC_L0_API/.libs/ /opt/soft/Driver/GLink/WGLK220_V3/WinApi/FC_L1_API/.libs/")
run("head -5 /opt/soft/Driver/GLink/WGLK220_V3/Demo/DemoAPeriod.cpp; grep -n 'FC_Dev_\\|main\\|scanf\\|getchar\\|cin' /opt/soft/Driver/GLink/WGLK220_V3/Demo/DemoAPeriod.cpp | head -40")
run("find /opt/soft/Driver/GLink/WGLK220_V3/PublicHead -name '*.h' | head -40")

# Rebuild libs if needed via reconfigure
run("""cd /opt/soft/Driver/GLink/WGLK220_V3 && ./configure --prefix=/opt/soft/Driver/GLink/WGLK220_V3/install 2>&1 | tail -30""")
