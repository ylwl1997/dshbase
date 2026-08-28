#!/usr/bin/env python3
import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("64.83.13.119", port=22022, username="box", password="PBkNIKuNgv3OrOTMTiPK", timeout=15, allow_agent=False, look_for_keys=False)
cmds = [
    "find /home/box -name 'provider-maps*' 2>/dev/null",
    "ls -la /home/box/sand-host/extensions/ 2>/dev/null",
    "cat /home/box/sand-data/sand-feature-flag-overrides.json",
]
for cmd in cmds:
    print("===", cmd)
    _, o, _ = c.exec_command(cmd, timeout=15)
    print(o.read().decode("utf-8", "replace")[:1500])
c.close()
