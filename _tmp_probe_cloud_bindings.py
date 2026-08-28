#!/usr/bin/env python3
"""Deep probe: bindings path, exec-daemon, hop log tail, persistence."""
import json
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("64.83.13.119", port=22022, username="box", password="PBkNIKuNgv3OrOTMTiPK",
          timeout=15, allow_agent=False, look_for_keys=False)

cmds = [
    "cat /home/box/sand-data/gateway.json 2>/dev/null",
    "ls -la /home/box/sand-data/",
    "find /home/box -maxdepth 3 -name '*.json' 2>/dev/null | xargs grep -l hopBaseUrl 2>/dev/null",
    "curl -s http://127.0.0.1:1340/ 2>/dev/null | head -c 800",
    "curl -s http://127.0.0.1:1340/routes 2>/dev/null | head -c 1200",
    "curl -s http://127.0.0.1:1340/agents 2>/dev/null | head -c 1200",
    "curl -s http://127.0.0.1:1340/bindings 2>/dev/null | head -c 1200",
    "curl -s http://127.0.0.1:1340/model-bindings 2>/dev/null | head -c 1200",
    "ss -tlnp | grep -E '1337|1340|14002|18792'",
    "tail -20 /home/box/opengrok/token-plan-hop.log 2>/dev/null",
    "grep -r model-bindings /home/box/sand-data /exec-daemon 2>/dev/null | head -20",
    "ls -la /exec-daemon/ 2>/dev/null | head -20",
    "strings /exec-daemon/index.js 2>/dev/null | grep -iE 'model.bind|hopBase|18792' | head -20",
    "cat /home/box/.profile /home/box/.bashrc 2>/dev/null | grep -i hop",
    "ls -la /etc/systemd/system/*hop* 2>/dev/null; crontab -l 2>/dev/null",
]
for cmd in cmds:
    print("\n===", cmd[:90], "===")
    _, o, e = c.exec_command(cmd, timeout=30)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    print((out or err)[:2000])

c.close()
