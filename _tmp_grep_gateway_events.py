#!/usr/bin/env python3
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("64.83.13.119", port=22022, username="box", password="PBkNIKuNgv3OrOTMTiPK",
          timeout=15, allow_agent=False, look_for_keys=False)

remote_py = r"""
text=open('/home/box/sand-host/host-main.cjs','r',encoding='utf-8',errors='replace').read()
start = text.find('GATEWAY_EVENTS_PATH')
print(text[start:start+3000][:2800])
"""
sftp = c.open_sftp()
with sftp.file("/tmp/grep_events.py", "w") as f:
    f.write(remote_py)
sftp.close()
_, o, _ = c.exec_command("python3 /tmp/grep_events.py", timeout=60)
print(o.read().decode("utf-8", "replace"))
c.close()
