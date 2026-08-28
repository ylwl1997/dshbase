import paramiko
import sys
import time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.66.1.16", username="root", password="60851.org", timeout=30)

def run(c, timeout=180):
    print("====", c[:180], "====")
    stdin, stdout, stderr = ssh.exec_command(c, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out:
        print(out[-12000:] if len(out) > 12000 else out)
    if err.strip():
        print("STDERR:", err[-4000:] if len(err) > 4000 else err)
    return out, err

run("grep -n 'GLINK_RATE\\|emFC_PORT_SPEED\\|PORT_SPEED_' /opt/soft/K72_GLink/Code/api/glink_api.h /opt/soft/Driver/GLink/WGLK220_V3/PublicHead/PublicHead/FC_L1_API.h | head -60")
run("sed -n '320,380p' /opt/soft/Driver/GLink/WGLK220_V3/Demo/DemoAPeriod.cpp")
run("grep -n 'JLK_REG_CH_A_STATUS\\|LinkStatus\\|0x0007\\|LINK' /opt/soft/K72_GLink/Code/api/glink_api.c /opt/soft/K72_GLink/Code/api/glink_regs.h | head -40")

# Run Demo with pty: send q quickly after first screen
chan = ssh.get_transport().open_session()
chan.get_pty(term="vt100", width=120, height=40)
chan.exec_command("cd /opt/soft/Driver/GLink/WGLK220_V3/Demo && ./DemoAPeriod")
time.sleep(2.5)
out = b""
while chan.recv_ready():
    out += chan.recv(65535)
print("==== DemoAPeriod first screen ====")
print(out.decode("utf-8", errors="replace"))
chan.send("q\n")
time.sleep(1)
while chan.recv_ready():
    out += chan.recv(65535)
print("==== after q ====")
print(out.decode("utf-8", errors="replace")[-4000:])
chan.close()

# Also try existing Demo binary briefly
