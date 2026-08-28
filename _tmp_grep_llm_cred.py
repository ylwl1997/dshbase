#!/usr/bin/env python3
import paramiko
from pathlib import Path

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("64.83.13.119", port=22022, username="box", password="PBkNIKuNgv3OrOTMTiPK",
          timeout=15, allow_agent=False, look_for_keys=False)

remote_py = r"""
text=open('/home/box/sand-host/host-main.cjs','r',encoding='utf-8',errors='replace').read()
idx = text.find('client_llm_gateway_credential')
while idx >= 0:
    snippet = text[max(0,idx-200):idx+500]
    if 'function' in snippet or 'if (' in snippet or 'create' in snippet.lower():
        print('--- @', idx, '---')
        print(snippet[:700])
        print()
    idx = text.find('client_llm_gateway_credential', idx+1)
    if idx > 0 and idx - text.find('client_llm_gateway_credential') > 50000:
        break
# also search resolveSandRequestedModel
for pat in ['resolveSandRequestedModel', 'SAND_DEFAULT_MODEL_ID', 'createCursorSandInference']:
    idx = text.find(pat)
    print(f'\n=== {pat} @ {idx} ===')
    if idx>=0:
        print(text[idx:idx+800][:750])
"""
sftp = c.open_sftp()
with sftp.file("/tmp/grep_llm_cred.py", "w") as f:
    f.write(remote_py)
sftp.close()
_, o, _ = c.exec_command("python3 /tmp/grep_llm_cred.py 2>/dev/null | head -120", timeout=90)
out = o.read().decode("utf-8", "replace")
Path(r"C:\Users\Administrator\dshbase\_tmp_llm_cred_grep.txt").write_text(out, encoding="utf-8")
print("wrote", len(out), "chars")
