#!/usr/bin/env python3
import json
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("64.83.13.119", port=22022, username="box", password="PBkNIKuNgv3OrOTMTiPK",
          timeout=15, allow_agent=False, look_for_keys=False)

remote_py = r"""
text=open('/home/box/sand-host/host-main.cjs','r',encoding='utf-8',errors='replace').read()
# find gateway route registrations
for pat in ['"/health"', '"/steer"', '"/send"', '"/prompt"', '"/turn"', '"/chat"', '"/agent"', '"/v1/', 'createServer', 'gateway']:
    idx = 0
    hits = 0
    while hits < 3:
        idx = text.find(pat, idx)
        if idx < 0: break
        print(f'--- {pat} @ {idx} ---')
        print(text[max(0,idx-80):idx+200][:320])
        idx += len(pat)
        hits += 1
"""
sftp = c.open_sftp()
with sftp.file("/tmp/grep_routes.py", "w") as f:
    f.write(remote_py)
sftp.close()
_, o, _ = c.exec_command("python3 /tmp/grep_routes.py", timeout=60)
print(o.read().decode("utf-8", "replace")[:8000])

# read recent audit for model info
cmds = [
    "python3 -c \"import json;d=json.load(open('/home/box/sand-data/agents/audit-outbox.json')); print(type(d), len(d) if isinstance(d,list) else list(d.keys())[:5])\"",
    "tail -c 4000 /home/box/sand-data/agents/audit-outbox.json",
    "ls /home/box/sand-data/agent-transcripts/a67d15ec-b377-46ba-b6f3-182a0982f683/",
    "tail -2 /home/box/sand-data/agent-transcripts/a67d15ec-b377-46ba-b6f3-182a0982f683/*.jsonl 2>/dev/null | head -c 3000",
]
for cmd in cmds:
    print("\n===", cmd[:70])
    _, o, _ = c.exec_command(cmd, timeout=30)
    print(o.read().decode("utf-8", "replace")[:3500])

c.close()
