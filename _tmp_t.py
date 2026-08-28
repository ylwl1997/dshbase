import paramiko, sys
sys.stdout.reconfigure(encoding="utf-8")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("100.66.1.16", username="root", password="60851.org", timeout=15)
sftp = client.open_sftp()
sftp.put(r"C:\Users\Administrator\dshbase\K72_GLink_sync\Code\demo\test_glink_api.c",
         "/opt/soft/K72_GLink/Code/demo/test_glink_api.c")
sftp.close()
stdin, stdout, stderr = client.exec_command(
    "cd /opt/soft/K72_GLink/Code/demo && make 2>&1"
)
out = stdout.read().decode("utf-8", errors="replace")
err = stderr.read().decode("utf-8", errors="replace")
print(out)
print(err)
if "error:" in out.lower() or "error:" in err.lower():
    client.close(); raise SystemExit(1)
# run API test and peer auto
stdin, stdout, stderr = client.exec_command(
    "cd /opt/soft/K72_GLink/Code/demo && ./test_glink_api 9 2>&1",
    timeout=120
)
print(stdout.read().decode("utf-8", errors="replace")[-12000:])
print("exit9", stdout.channel.recv_exit_status())
stdin, stdout, stderr = client.exec_command(
    "cd /opt/soft/K72_GLink/Code/demo && ./test_glink_api 11 2>&1",
    timeout=120
)
print(stdout.read().decode("utf-8", errors="replace")[-6000:])
print("exit11", stdout.channel.recv_exit_status())
client.close()
