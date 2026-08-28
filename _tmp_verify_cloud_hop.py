#!/usr/bin/env python3
import json
import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(
    "64.83.13.119",
    port=22022,
    username="box",
    password="PBkNIKuNgv3OrOTMTiPK",
    timeout=15,
    allow_agent=False,
    look_for_keys=False,
)


def run(cmd, timeout=90):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    return o.read().decode("utf-8", "replace"), e.read().decode("utf-8", "replace")


print("=== healthz ===")
print(run("curl -s http://127.0.0.1:18792/healthz")[0])

print("=== chat via hop ===")
py = r"""
import json, urllib.request
body=json.dumps({"model":"qwen3.6-flash","messages":[{"role":"user","content":"Reply exactly: CLOUD_QWEN_OK"}],"max_tokens":32}).encode()
req=urllib.request.Request("http://127.0.0.1:18792/v1/chat/completions", data=body, method="POST", headers={"Content-Type":"application/json"})
with urllib.request.urlopen(req, timeout=60) as r:
    d=json.loads(r.read().decode())
print(d["choices"][0]["message"]["content"])
"""
out, err = run(f"python3 -c {json.dumps(py)}")
print(out.strip())
if err.strip():
    print("ERR", err[:300])

print("=== process ===")
print(run("pgrep -af token-plan-hop; ss -tlnp | grep 18792")[0])

print("=== bindings head ===")
print(run("head -20 /home/box/sand-data/model-bindings.json")[0])

print("=== search sand-host for bindings ===")
for pat in ["model-bindings", "hopBaseUrl", "modelBindings"]:
    out, _ = run(f"grep -r '{pat}' /home/box/sand-host 2>/dev/null | head -8")
    if out.strip():
        print(f"-- {pat} --")
        print(out)

print("=== active agent ===")
print(run("cat /home/box/sand-data/agents/active-agent.json")[0])

c.close()
