#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import paramiko, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("100.66.1.16", username="root", password="60851.org",
          timeout=20, look_for_keys=False, allow_agent=False)

def run(cmd, t=120):
    print(f"\n===== {cmd[:120]}{'...' if len(cmd)>120 else ''} =====", flush=True)
    _, out, err = c.exec_command(cmd, timeout=t)
    o = out.read().decode("utf-8", "replace")
    e = err.read().decode("utf-8", "replace")
    code = out.channel.recv_exit_status()
    if o: print(o, end="" if o.endswith("\n") else "\n")
    if e: print("[stderr]\n" + e, end="" if e.endswith("\n") else "\n")
    print(f"[exit={code}]", flush=True)
    return code, o, e

# 1) PCI/BAR health for Cavige
run(r'''
echo "=== Cavige PCI ==="
lspci -s 8c:00.0 -vv | egrep "Control:|Region 0|DevSta:|LnkSta:"
echo "COMMAND=$(setpci -s 8c:00.0 COMMAND)"
echo "BAR0_cfg=$(setpci -s 8c:00.0 BASE_ADDRESS_0)"
echo "enable=$(cat /sys/bus/pci/devices/0000:8c:00.0/enable)"
echo "resource:"; cat /sys/bus/pci/devices/0000:8c:00.0/resource
xxd -g4 -l 32 /sys/bus/pci/devices/0000:8c:00.0/config
''')

# 2) If BAR0 is 0, re-enable Mem and ensure BAR programmed; try remove/rescan carefully
run(r'''
BAR=$(setpci -s 8c:00.0 BASE_ADDRESS_0)
CMD=$(setpci -s 8c:00.0 COMMAND)
echo "BAR0=$BAR CMD=$CMD"
# Ensure Mem+BusMaster
setpci -s 8c:00.0 COMMAND=0x0006
# If BAR looks unprogrammed (0), try writing known addr from resource file
RES=$(awk 'NR==1{print $1}' /sys/bus/pci/devices/0000:8c:00.0/resource)
echo "resource0_start=$RES"
if [ "$BAR" = "00000000" ] || [ "$BAR" = "0" ]; then
  echo "BAR0 unprogrammed; attempting restore from resource start"
  # resource start is phys addr; PCI BAR bit0=0 for mem
  setpci -s 8c:00.0 BASE_ADDRESS_0=$RES
  setpci -s 8c:00.0 COMMAND=0x0006
fi
echo "AFTER: BAR0=$(setpci -s 8c:00.0 BASE_ADDRESS_0) CMD=$(setpci -s 8c:00.0 COMMAND)"
lspci -s 8c:00.0 -vv | egrep "Control:|Region 0"
''')

# 3) Direct MMIO probe after BAR fix
run(r'''
python3 << 'PY'
import mmap, os, struct
path='/sys/bus/pci/devices/0000:8c:00.0/resource0'
fd=os.open(path, os.O_RDWR | os.O_SYNC)
m=mmap.mmap(fd, min(os.fstat(fd).st_size, 16*1024*1024), mmap.MAP_SHARED, mmap.PROT_READ|mmap.PROT_WRITE)
print('map_size', m.size())
for off in [0,4,0x10000,0x11010,0x30000,0x3021C,0x89000,0x8902C,0x89050]:
    try:
        m.seek(off)
        v=struct.unpack('<I', m.read(4))[0]
        print(f'phys+0x{off:X} = 0x{v:08X}')
    except Exception as e:
        print(f'phys+0x{off:X} ERR {e}')
m.close(); os.close(fd)
PY
''')

# 4) K72 link status now (dual fiber)
run("/tmp/k72_link; echo '---'; /tmp/k72_bringup --wait 6000")

c.close()
print("\nDONE batch1", flush=True)
