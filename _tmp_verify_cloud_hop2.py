#!/usr/bin/env python3
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("64.83.13.119", port=22022, username="box", password="PBkNIKuNgv3OrOTMTiPK",
          timeout=15, allow_agent=False, look_for_keys=False)
sftp = c.open_sftp()

test_py = """import json, urllib.request
body=json.dumps({"model":"qwen3.6-flash","messages":[{"role":"user","content":"Reply exactly: CLOUD_QWEN_OK"}],"max_tokens":32}).encode()
req=urllib.request.Request("http://127.0.0.1:18792/v1/chat/completions", data=body, method="POST", headers={"Content-Type":"application/json"})
with urllib.request.urlopen(req, timeout=60) as r:
    d=json.loads(r.read().decode())
print("RESULT:", d["choices"][0]["message"]["content"])
"""
with sftp.file("/tmp/test_hop.py", "w") as f:
    f.write(test_py)
sftp.close()

cmds = [
    "python3 /tmp/test_hop.py",
    "grep -r model-bindings /home/box 2>/dev/null | grep -v Binary | head -25",
    "grep -r hopBaseUrl /home/box 2>/dev/null | grep -v Binary | head -15",
    "grep -r modelBindings /home/box/sand-host 2>/dev/null | head -10",
    "strings /home/box/sand-host/host-main.cjs 2>/dev/null | grep -i model-bind | head -5",
    "strings /exec-daemon/index.js 2>/dev/null | grep -i model-bind | head -5",
    "curl -s http://127.0.0.1:1337/health 2>/dev/null | head -c 500",
    "curl -s http://127.0.0.1:1340/health 2>/dev/null | head -c 500",
]
for cmd in cmds:
    print("===", cmd[:80], "===")
    _, o, e = c.exec_command(cmd, timeout=60)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    print(out[:1500] if out else err[:500])
c.close()
