# -*- coding: utf-8 -*-
import paramiko
import sys
sys.stdout.reconfigure(encoding="utf-8")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("100.66.1.16", username="root", password="60851.org", timeout=20)
cmd = r"""
python3 - <<'PY'
import os
root='/opt/soft/Driver/GLink/Doc'
for dirpath, dirs, files in os.walk(root):
    if 'SmartNCShortMsg_Demo' in dirpath and 'Demo' in dirpath:
        if 'FPGA' in dirpath: 
            pass
        for f in files:
            if f.endswith(('.c','.h','.vhd','.txt','.md')):
                print(os.path.join(dirpath,f))
PY
"""
stdin, stdout, stderr = c.exec_command(cmd, timeout=60)
print(stdout.read().decode("utf-8", "replace")[:8000])
print(stderr.read().decode("utf-8", "replace")[:2000])
c.close()
