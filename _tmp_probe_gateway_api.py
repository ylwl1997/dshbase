#!/usr/bin/env python3
"""Discover gateway/exec-daemon API and trigger test turn."""
import json
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("64.83.13.119", port=22022, username="box", password="PBkNIKuNgv3OrOTMTiPK",
          timeout=15, allow_agent=False, look_for_keys=False)

# get gateway token
_, o, _ = c.exec_command("cat /home/box/sand-data/gateway.json", timeout=10)
gw = json.loads(o.read().decode())
token = gw["token"]
port = gw["port"]
auth = f'-H "Authorization: Bearer {token}"'

paths = [
    "/health", "/healthz", "/status", "/v1/health",
    "/api/health", "/exec/health", "/agent/health",
    "/turn", "/v1/turn", "/chat", "/v1/chat",
    "/prompt", "/run", "/execute", "/message",
    "/agents", "/v1/agents", "/active-agent",
    "/model-bindings", "/config/model-bindings",
    "/internal/model-bindings",
]
print(f"Gateway :{port} token={token[:12]}...")
for p in paths:
    cmd = f'curl -s -m 3 {auth} http://127.0.0.1:{port}{p} 2>/dev/null | head -c 300'
    _, o, _ = c.exec_command(cmd, timeout=10)
    out = o.read().decode("utf-8", "replace").strip()
    if out and "not found" not in out.lower():
        print(f"GET {p}: {out[:250]}")

# port 1337
print("\n=== port 1337 ===")
for p in ["/", "/health", "/healthz", "/status", "/openapi.json", "/docs"]:
    cmd = f'curl -s -m 3 http://127.0.0.1:1337{p} 2>/dev/null | head -c 300'
    _, o, _ = c.exec_command(cmd, timeout=10)
    out = o.read().decode("utf-8", "replace").strip()
    if out:
        print(f"GET {p}: {out[:250]}")

# grep sand-host minified
print("\n=== sand-host strings ===")
cmds = [
    "strings /home/box/sand-host/host-main.cjs 2>/dev/null | grep -iE 'model.bind|hopBase|bindings.json' | head -15",
    "strings /home/box/sand-host/host-main.cjs 2>/dev/null | grep -iE 'sand-data' | head -15",
    "ls -la /home/box/sand-host/",
    "head -c 500 /home/box/sand-data/settings.json",
    "cat /home/box/sand-data/model-bindings.json",
]
for cmd in cmds:
    print("\n---", cmd[:70])
    _, o, _ = c.exec_command(cmd, timeout=30)
    print(o.read().decode("utf-8", "replace")[:2000])

c.close()
