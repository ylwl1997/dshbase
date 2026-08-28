import paramiko
import sys
import select
import time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.66.1.16", username="root", password="60851.org", timeout=30)

def run(c, timeout=300):
    print("====", c[:180], "====")
    stdin, stdout, stderr = ssh.exec_command(c, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out:
        print(out[-15000:] if len(out) > 15000 else out)
    if err.strip():
        print("STDERR:", err[-8000:] if len(err) > 8000 else err)
    return out, err

# Get exact API prototypes
run("""sed -n '1,80p' /opt/soft/Driver/GLink/WGLK220_V3/PublicHead/PublicHead/FC_L1_API.h | head -5; \
grep -n 'FC_Dev_ScanLocalDevList\|FC_Dev_OpenDevByIndex\|FC_Dev_Get_PortLinkState\|Dev_Get_AllPortLinkState\|FC_Dev_GetChannelNum\|FC_Dev_CloseDev\|typedef.*DevNode\|struct.*DevNode\|pDevNode_st\|FC_DEV_HANDLE\|FC_RESULT' /opt/soft/Driver/GLink/WGLK220_V3/PublicHead/PublicHead/FC_L1_API.h | head -80""")

run("""grep -n 'link\|Link\|CH_A\|CH_B\|status\|光\|端口' /opt/soft/K72_GLink/Code/demo/test_glink_api.c | head -50; \
/opt/soft/K72_GLink/Code/demo/test_glink_api --help 2>&1 | head -40; \
echo '---'; /opt/soft/K72_GLink/Code/demo/test_glink_api 2>&1 | head -5""")
