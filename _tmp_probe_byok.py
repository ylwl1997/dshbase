#!/usr/bin/env python3
import json
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("64.83.13.119", port=22022, username="box", password="PBkNIKuNgv3OrOTMTiPK",
          timeout=15, allow_agent=False, look_for_keys=False)

cmds = [
    "cat /home/box/sand-data/agents/acdb77da-34a3-4188-9135-9780e8ed1721/settings.json",
    "cat /home/box/sand-data/agents/acdb77da-34a3-4188-9135-9780e8ed1721/profile.json",
    "grep -i byok /home/box/sand-data/sand-statsig-bootstrap.json 2>/dev/null | head -5",
    "grep -i model /home/box/sand-data/sand-feature-flag-overrides.json 2>/dev/null",
    "grep -aoE '.{0,60}(ModelAllowlist|model.bind|BYOK|byok).{0,60}' /home/box/sand-host/host-main.cjs 2>/dev/null | head -10",
    "grep -aoE '.{0,60}(ModelAllowlist|model.bind|BYOK|byok).{0,60}' /exec-daemon/index.js 2>/dev/null | head -10",
    # recent transcripts
    "ls -lt /home/box/sand-data/agent-transcripts/ | head -8",
    "find /home/box/sand-data/agent-transcripts -name '*.jsonl' -mmin -120 | head -3 | xargs tail -3 2>/dev/null",
]
for cmd in cmds:
    print("\n===", cmd[:85], "===")
    _, o, e = c.exec_command(cmd, timeout=30)
    print((o.read() + e.read()).decode("utf-8", "replace")[:3000])

c.close()
