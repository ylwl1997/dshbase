#!/usr/bin/env python3
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("64.83.13.119", port=22022, username="box", password="PBkNIKuNgv3OrOTMTiPK",
          timeout=15, allow_agent=False, look_for_keys=False)

remote_py = r"""
text=open('/home/box/sand-host/host-main.cjs','r',encoding='utf-8',errors='replace').read()
patterns = [
    'chat/completions', 'api.x.ai', 'x.ai/v1', 'llm-gateway', 'LlmGateway',
    'openai.com', '127.0.0.1:', 'localhost:', 'model-bindings',
    'sand-data/model', 'grok-4', 'RequestedModel', 'customBaseUrl',
]
for pat in patterns:
    cnt = text.count(pat)
    if cnt:
        idx = text.find(pat)
        print(f'{pat}: {cnt} hits, first at {idx}')
        print(text[max(0,idx-120):idx+180][:350])
        print('---')
"""
sftp = c.open_sftp()
with sftp.file("/tmp/grep_llm.py", "w") as f:
    f.write(remote_py)
sftp.close()
_, o, _ = c.exec_command("python3 /tmp/grep_llm.py", timeout=60)
print(o.read().decode("utf-8", "replace")[:8000])
c.close()
