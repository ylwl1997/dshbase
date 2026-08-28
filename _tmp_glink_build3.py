import paramiko
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.66.1.16", username="root", password="60851.org", timeout=30)

def run(c, timeout=600):
    print("====", c[:140], "====")
    stdin, stdout, stderr = ssh.exec_command(c, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out:
        print(out[-12000:] if len(out) > 12000 else out)
    if err.strip():
        print("STDERR:", err[-6000:] if len(err) > 6000 else err)
    return out, err

# reconfigure
run("cd /opt/soft/Driver/GLink/WGLK220_V3 && ./configure --prefix=/opt/soft/Driver/GLink/WGLK220_V3/install 2>&1 | tail -40")
run("cd /opt/soft/Driver/GLink/WGLK220_V3 && make -j$(nproc) 2>&1 | tail -80")
