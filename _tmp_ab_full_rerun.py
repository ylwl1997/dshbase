# -*- coding: utf-8 -*-
import paramiko, sys
sys.stdout.reconfigure(encoding="utf-8")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("100.66.1.16", username="root", password="60851.org", timeout=20)
sftp = c.open_sftp()
sftp.put(r"C:\Users\Administrator\dshbase\K72_GLink_sync\Code\demo\test_glink_api.c",
         "/opt/soft/K72_GLink/Code/demo/test_glink_api.c")
sftp.close()
stdin, stdout, stderr = c.exec_command(
    "cd /opt/soft/K72_GLink/Code/demo && "
    "gcc -Wall -O2 -I../api -o test_glink_api test_glink_api.c ../api/glink_api.c 2>&1 && "
    "./test_glink_api ab-full 2>&1 | grep -E '>>>>|汇总:|【GLink|失败]|通过]|跳过]|STATUS=|fail_cnt|长报'",
    timeout=600,
)
print(stdout.read().decode("utf-8", "replace"))
c.close()
