#!/usr/bin/env python3
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("64.83.13.119", port=22022, username="box", password="PBkNIKuNgv3OrOTMTiPK",
          timeout=15, allow_agent=False, look_for_keys=False)

remote_py = r"""
import re
text=open('/home/box/sand-host/host-main.cjs','r',encoding='utf-8',errors='replace').read()
for pat in ['resolveModelId','model-bindings','hopBaseUrl','MODEL_BINDINGS','readBindings','loadBindings','ModelAllowlistByok']:
    idx=text.find(pat)
    print(pat, 'at', idx)
    if idx>=0:
        print(text[max(0,idx-200):idx+500][:700])
        print('---')
"""
sftp = c.open_sftp()
with sftp.file("/tmp/grep_model.py", "w") as f:
    f.write(remote_py)
sftp.close()

_, o, _ = c.exec_command("python3 /tmp/grep_model.py", timeout=60)
print(o.read().decode("utf-8", "replace")[:6000])

_, o, _ = c.exec_command(
    "curl -s -m 5 -H 'Authorization: Bearer local' http://127.0.0.1:1337/v1/models 2>/dev/null | head -c 800",
    timeout=15,
)
print("\nexec-daemon models:", o.read().decode("utf-8", "replace"))

c.close()
