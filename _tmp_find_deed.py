#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("100.66.1.16", username="root", password="60851.org",
          timeout=20, look_for_keys=False, allow_agent=False)

def run(cmd, t=90):
    print(f"\n===== {cmd[:120]} =====", flush=True)
    _, out, err = c.exec_command(cmd, timeout=t)
    print(out.read().decode("utf-8", "replace"), end="")
    e = err.read().decode("utf-8", "replace")
    if e:
        print("[stderr]", e[:800])
    print("exit", out.channel.recv_exit_status(), flush=True)

run("grep -rn 'DEEDBEEF\\|0xDEED' /opt/soft/Driver/GLink/WGLK220_V3 --include='*.c' --include='*.h' 2>/dev/null | sed -n '1,30p'")
run("strings /opt/soft/Driver/GLink/WGLK220_V3/PublicHead/Commont/DevRegisterDef.h | grep -iE 'SPEED|CLK_MODE|GT_.*RATE|PORT_SPEED|REG_GT' | sed -n '1,50p'")
run("sed -n '945,1040p' /opt/soft/Driver/GLink/WGLK220_V3/WinApi/FC_L1_API/FC_Dev_Operate.c")
run("grep -n 'DEEDBEEF\\|ReadRegister' /opt/soft/Driver/GLink/WGLK220_V3/PublicHead/SysDifferent/BaseDevOper.c /opt/soft/Driver/GLink/Driver/Interface/* 2>/dev/null | sed -n '1,40p'")
c.close()
