import paramiko
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.66.1.16", username="root", password="60851.org", timeout=30)

def run(c, timeout=120):
    print("====", c[:160], "====")
    stdin, stdout, stderr = ssh.exec_command(c, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out:
        print(out[-12000:] if len(out) > 12000 else out)
    if err.strip():
        print("STDERR:", err[-4000:] if len(err) > 4000 else err)
    return out, err

run("sed -n '2100,2284p' /opt/soft/K72_GLink/Code/demo/test_glink_api.c")
run("sed -n '400,430p' /opt/soft/Driver/GLink/WGLK220_V3/PublicHead/PublicHead/FC_L1_API.h")
run("grep -n 'Get_PortLinkState\\|AllPortLinkState\\|LinkState\\|PORT_STATE' /opt/soft/Driver/GLink/WGLK220_V3/PublicHead/PublicHead/FC_L1_API.h | head -40")
run("grep -n 'printf.*端口\\|printf.*链路\\|Get_PortLinkState\\|LinkState' /opt/soft/Driver/GLink/WGLK220_V3/Demo/DemoAPeriod.cpp | head -30")
