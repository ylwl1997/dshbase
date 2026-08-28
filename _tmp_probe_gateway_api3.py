#!/usr/bin/env python3
import json
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("64.83.13.119", port=22022, username="box", password="PBkNIKuNgv3OrOTMTiPK",
          timeout=15, allow_agent=False, look_for_keys=False)

_, o, _ = c.exec_command("cat /home/box/sand-data/gateway.json", timeout=10)
gw = json.loads(o.read().decode())
token = gw["token"]
port = gw["port"]
auth = f'Authorization: Bearer {token}'

remote_py = f"""
import json, urllib.request
token = {json.dumps(token)}
base = "http://127.0.0.1:{port}"
headers = {{"Authorization": "Bearer "+token, "Content-Type": "application/json"}}
paths = [
  ("GET", "/health", None),
  ("GET", "/api/health", None),
  ("GET", "/events", None),
  ("GET", "/api/events", None),
  ("POST", "/api/events", {{"type":"ping"}}),
  ("POST", "/events", {{"type":"ping"}}),
  ("GET", "/api/agents", None),
  ("POST", "/api/steer", {{"agentId":"a67d15ec-b377-46ba-b6f3-182a0982f683","message":"Reply exactly: QWEN_ROUTE_TEST"}}),
  ("POST", "/api/send", {{"text":"Reply exactly: QWEN_ROUTE_TEST"}}),
  ("POST", "/api/prompt", {{"prompt":"Reply exactly: QWEN_ROUTE_TEST"}}),
]
for method, path, body in paths:
    req = urllib.request.Request(base+path, method=method, headers=headers)
    if body is not None:
        req.data = json.dumps(body).encode()
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            print(method, path, r.status, r.read(250).decode("utf-8","replace"))
    except Exception as e:
        print(method, path, "ERR", str(e)[:150])
"""
sftp = c.open_sftp()
with sftp.file("/tmp/gw_api.py", "w") as f:
    f.write(remote_py)
sftp.close()
_, o, _ = c.exec_command("python3 /tmp/gw_api.py", timeout=60)
print(o.read().decode("utf-8", "replace"))

# grep bindings in host-main broader
remote_py2 = r"""
text=open('/home/box/sand-host/host-main.cjs','r',encoding='utf-8',errors='replace').read()
for pat in ['bindings', 'Bindings', 'BINDINGS']:
    cnt = text.count(pat)
    if cnt:
        print(pat, cnt)
        idx = text.find(pat)
        while idx >= 0 and idx < 30_000_000:
            snippet = text[max(0,idx-60):idx+120]
            if 'model' in snippet.lower() or 'hop' in snippet.lower() or 'bind' in snippet.lower():
                print(' @', idx, ':', snippet[:200])
            idx = text.find(pat, idx+1)
            if idx > text.find(pat)+50000: break
"""
sftp2 = c.open_sftp()
with sftp2.file("/tmp/grep_bind2.py", "w") as f:
    f.write(remote_py2)
sftp2.close()
_, o, _ = c.exec_command("python3 /tmp/grep_bind2.py 2>/dev/null | head -40", timeout=60)
print("\nbindings grep:\n", o.read().decode("utf-8", "replace")[:4000])

c.close()
