#!/usr/bin/env python3
import paramiko
from pathlib import Path

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("64.83.13.119", port=22022, username="box", password="PBkNIKuNgv3OrOTMTiPK",
          timeout=15, allow_agent=False, look_for_keys=False)

remote_py = r"""
text=open('/home/box/sand-host/host-main.cjs','r',encoding='utf-8',errors='replace').read()
for pat in ['ModelAllowlistByok', 'modelAllowlist', 'byokEntries', 'readModelAllowlist']:
    idx = 0
    n = 0
    while n < 5:
        idx = text.find(pat, idx)
        if idx < 0: break
        print('---', pat, idx, '---')
        print(text[max(0,idx-100):idx+300][:450])
        idx += len(pat)
        n += 1
"""
sftp = c.open_sftp()
with sftp.file("/tmp/grep_byok3.py", "w") as f:
    f.write(remote_py)
sftp.close()
_, o, _ = c.exec_command("python3 /tmp/grep_byok3.py", timeout=60)
out = o.read().decode("utf-8", "replace")
Path(r"C:\Users\Administrator\dshbase\_tmp_byok3.txt").write_text(out, encoding="utf-8")
print(len(out))
