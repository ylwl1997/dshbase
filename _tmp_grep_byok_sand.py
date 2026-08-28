#!/usr/bin/env python3
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("64.83.13.119", port=22022, username="box", password="PBkNIKuNgv3OrOTMTiPK",
          timeout=15, allow_agent=False, look_for_keys=False)
cmds = [
    "grep -ri byok /home/box/sand-data 2>/dev/null | head -10",
    "grep -ri allowlist /home/box/sand-data 2>/dev/null | head -10",
    "grep -ri llm_gateway /home/box/sand-data 2>/dev/null | head -10",
    "find /home/box/sand-data -name '*byok*' -o -name '*allowlist*' 2>/dev/null",
]
for cmd in cmds:
    print("===", cmd)
    _, o, _ = c.exec_command(cmd, timeout=20)
    print(o.read().decode("utf-8", "replace")[:1500] or "(none)")
c.close()
