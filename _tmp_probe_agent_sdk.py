#!/usr/bin/env python3
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("64.83.13.119", port=22022, username="box", password="PBkNIKuNgv3OrOTMTiPK",
          timeout=15, allow_agent=False, look_for_keys=False)

cmds = [
    "ls -la /exec-daemon/agent-sdk/",
    "head -80 /exec-daemon/agent-sdk/README.md 2>/dev/null || head -80 /exec-daemon/agent-sdk/package.json 2>/dev/null",
    "grep -r 'model-bindings' /exec-daemon/agent-sdk 2>/dev/null | head -10",
    "cat /home/box/sand-host/version",
    "grep -aoE '.{0,80}RoutedModelUpdate.{0,120}' /home/box/sand-host/host-main.cjs | head -3",
]
for cmd in cmds:
    print("\n===", cmd[:80])
    _, o, _ = c.exec_command(cmd, timeout=30)
    print(o.read().decode("utf-8", "replace")[:2500])

c.close()
