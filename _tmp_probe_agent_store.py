#!/usr/bin/env python3
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("64.83.13.119", port=22022, username="box", password="PBkNIKuNgv3OrOTMTiPK",
          timeout=15, allow_agent=False, look_for_keys=False)

cmds = [
    "cat /home/box/sand-data/source-map.json",
    "ls -la /home/box/sand-data/agents/",
    "find /home/box/sand-data/agents -name '*.json' | head -20",
    "grep -r hopBaseUrl /home/box/sand-data/agents 2>/dev/null | head -5",
    "grep -r modelId /home/box/sand-data/agents/acdb77da-34a3-4188-9135-9780e8ed1721 2>/dev/null | head -10",
    "sqlite3 /home/box/sand-data/agents/acdb77da-34a3-4188-9135-9780e8ed1721/store.db '.tables' 2>/dev/null",
    "sqlite3 /home/box/sand-data/agents/acdb77da-34a3-4188-9135-9780e8ed1721/store.db \"SELECT name FROM sqlite_master WHERE type='table'\" 2>/dev/null",
]
for cmd in cmds:
    print("\n===", cmd[:80], "===")
    _, o, e = c.exec_command(cmd, timeout=30)
    print((o.read() + e.read()).decode("utf-8", "replace")[:2500])

c.close()
