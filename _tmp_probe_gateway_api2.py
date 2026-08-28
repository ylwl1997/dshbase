#!/usr/bin/env python3
import json
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("64.83.13.119", port=22022, username="box", password="PBkNIKuNgv3OrOTMTiPK",
          timeout=15, allow_agent=False, look_for_keys=False)

# deep grep host-main for bindings-related strings
_, o, _ = c.exec_command(
    r"grep -aoE '.{0,40}(model.?bind|hopBase|hop.?base|modelBindings).{0,40}' "
    r"/home/box/sand-host/host-main.cjs 2>/dev/null | head -20",
    timeout=60,
)
print("host-main grep:", o.read().decode("utf-8", "replace")[:3000] or "(none)")

# exec-daemon index routes
_, o, _ = c.exec_command(
    r"grep -aoE '.{0,30}(/v1/|/health|/turn|/chat|/prompt|/run|model).{0,30}' "
    r"/exec-daemon/index.js 2>/dev/null | sort -u | head -40",
    timeout=60,
)
print("\nexec-daemon routes:", o.read().decode("utf-8", "replace")[:3000] or "(none)")

# gateway POST probes with token
_, o, _ = c.exec_command("cat /home/box/sand-data/gateway.json", timeout=10)
gw = json.loads(o.read().decode())
token = gw["token"]

test_script = f'''import urllib.request, json
token = {json.dumps(token)}
base = "http://127.0.0.1:1340"
paths = [
  ("POST", "/v1/chat/completions", {{"model":"qwen3.6-flash","messages":[{{"role":"user","content":"ping"}}]}}),
  ("POST", "/turn", {{"agentId":"acdb77da-34a3-4188-9135-9780e8ed1721","message":"Reply exactly: QWEN_ROUTE_TEST"}}),
  ("POST", "/prompt", {{"text":"Reply exactly: QWEN_ROUTE_TEST"}}),
  ("POST", "/run", {{"prompt":"Reply exactly: QWEN_ROUTE_TEST"}}),
  ("POST", "/message", {{"content":"Reply exactly: QWEN_ROUTE_TEST"}}),
  ("POST", "/execute", {{"command":"echo test"}}),
]
for method, path, body in paths:
    req = urllib.request.Request(base+path, data=json.dumps(body).encode(), method=method)
    req.add_header("Authorization", "Bearer "+token)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            print(method, path, r.status, r.read(200).decode("utf-8","replace"))
    except Exception as e:
        print(method, path, "ERR", str(e)[:120])
'''
sftp = c.open_sftp()
with sftp.file("/tmp/gw_probe.py", "w") as f:
    f.write(test_script)
sftp.close()
_, o, e = c.exec_command("python3 /tmp/gw_probe.py", timeout=60)
print("\nGW POST probe:\n", o.read().decode("utf-8", "replace"))

# check hop log line count before/after - also look at sand-host process
_, o, _ = c.exec_command("wc -l /home/box/opengrok/token-plan-hop.log; ps aux | grep -E 'sand-host|host-main|exec-daemon' | grep -v grep", timeout=15)
print("\n", o.read().decode("utf-8", "replace"))

c.close()
