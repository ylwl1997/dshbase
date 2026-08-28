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

run("grep -n 'FC_Dev_ScanLocalDevList\\|FC_Dev_OpenDevByIndex\\|FC_Dev_Get_PortLinkState\\|Dev_Get_AllPortLinkState\\|FC_Dev_GetChannelNum\\|FC_Dev_CloseDev\\|struct.*DevNode\\|pDevNode_st' /opt/soft/Driver/GLink/WGLK220_V3/PublicHead/PublicHead/FC_L1_API.h | head -80")
run("grep -n 'FC_RESULT\\|FC_TRUE\\|FC_FALSE\\|typedef.*FC_RESULT' /opt/soft/Driver/GLink/WGLK220_V3/PublicHead/PublicHead/FC_L1_API.h | head -20")
run("grep -n 'main\\|argv\\|link\\|status\\|CH_A\\|optical\\|opt_status\\|print_usage\\|usage' /opt/soft/K72_GLink/Code/demo/test_glink_api.c | head -80")
run("file /opt/soft/K72_GLink/Code/demo/test_glink_api; ls -la /opt/soft/K72_GLink/Code/demo/test_glink_api")
ssh.close()
