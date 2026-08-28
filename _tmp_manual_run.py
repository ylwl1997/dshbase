# -*- coding: utf-8 -*-
import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("100.66.1.16", username="root", password="60851.org", timeout=20)
sftp = c.open_sftp()
for loc, rem in [
    (r"C:\Users\Administrator\dshbase\K72_GLink_sync\Code\demo\_ab_manual_check.c",
     "/opt/soft/K72_GLink/Code/demo/_ab_manual_check.c"),
    (r"C:\Users\Administrator\dshbase\K72_GLink_sync\Code\api\glink_api.c",
     "/opt/soft/K72_GLink/Code/api/glink_api.c"),
    (r"C:\Users\Administrator\dshbase\K72_GLink_sync\Code\api\glink_regs.h",
     "/opt/soft/K72_GLink/Code/api/glink_regs.h"),
]:
    sftp.put(loc, rem)
sftp.close()
cmd = (
    "cd /opt/soft/K72_GLink/Code/demo && "
    "gcc -Wall -O2 -I../api -o _ab_manual_check _ab_manual_check.c ../api/glink_api.c 2>&1 && "
    "./_ab_manual_check 2>&1"
)
stdin, stdout, stderr = c.exec_command(cmd, timeout=180)
print(stdout.read().decode("utf-8", "replace"))
err = stderr.read().decode("utf-8", "replace")
if err:
    print("STDERR", err[:1500])
c.close()
