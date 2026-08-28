#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import paramiko, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("100.66.1.16", username="root", password="60851.org",
          timeout=20, look_for_keys=False, allow_agent=False)

def run(cmd, t=120):
    print(f"\n===== {cmd[:100]} =====", flush=True)
    _, out, err = c.exec_command(cmd, timeout=t)
    print(out.read().decode("utf-8", "replace"), end="")
    e = err.read().decode("utf-8", "replace")
    if e:
        print("[stderr]", e[:600])
    print("exit", out.channel.recv_exit_status(), flush=True)

run(r'''
set -e
# Unbind driver during reset to avoid races
echo "unbind cavige_dev"
echo 0000:8c:00.0 > /sys/bus/pci/drivers/cavige_dev/unbind 2>/dev/null || true
sleep 0.5

echo "PCI function reset..."
echo 1 > /sys/bus/pci/devices/0000:8c:00.0/reset
sleep 1

# CRITICAL: restore BAR+CMD immediately (reset clears BAR0)
START=$(awk 'NR==1{printf "0x%x",$1+0}' /sys/bus/pci/devices/0000:8c:00.0/resource)
echo "resource_start=$START"
setpci -s 8c:00.0 BASE_ADDRESS_0=${START:-0xb0000000}
setpci -s 8c:00.0 COMMAND=0x0006
echo "BAR=$(setpci -s 8c:00.0 BASE_ADDRESS_0) CMD=$(setpci -s 8c:00.0 COMMAND)"
lspci -s 8c:00.0 -vv | egrep 'Control:|Region 0|DevSta:'

echo "=== MMIO after reset+BAR restore ==="
python3 - << 'PY'
import mmap,os,struct
fd=os.open('/sys/bus/pci/devices/0000:8c:00.0/resource0', os.O_RDWR|os.O_SYNC)
m=mmap.mmap(fd, 16*1024*1024, mmap.MAP_SHARED, mmap.PROT_READ|mmap.PROT_WRITE)
def r(o):
 m.seek(o); return struct.unpack('<I', m.read(4))[0]
hits=0
print('key regs:')
for n,o in [('+0',0),('IP',0x10000),('CAP',0x11010),('SPEED',0x11018),
            ('L0',0x8902C),('PS0',0x89050),('L1',0x8A02C),('PS1',0x8A050),
            ('RATE0',0x30040),('GTRATE',0x30060),('CLK',0x3021C)]:
  v=r(o); print(f'  {n:7s}=0x{v:08X}')
print('sparse non-DEED in 0..0x20000 step 0x1000:')
for o in range(0, 0x20000, 0x1000):
  v=r(o)
  if v not in (0xDEEDBEEF, 0xFFFFFFFF):
    print(f'  0x{o:05X}=0x{v:08X}'); hits+=1
print('hits', hits)
m.close(); os.close(fd)
PY

# rebind driver
echo "bind cavige_dev"
echo 0000:8c:00.0 > /sys/bus/pci/drivers/cavige_dev/bind 2>/dev/null || \
  echo 289e 7120 > /sys/bus/pci/drivers/cavige_dev/new_id 2>/dev/null || true
# if still unbound, insmod path
if ! ls /dev/cvgdev* >/dev/null 2>&1; then
  rmmod cvgDrv 2>/dev/null || true
  # restore BAR again before insmod
  setpci -s 8c:00.0 BASE_ADDRESS_0=${START:-0xb0000000}
  setpci -s 8c:00.0 COMMAND=0x0006
  insmod /opt/soft/Driver/GLink/Driver/cvgDrv.ko
fi
sleep 0.5
# driver may clear BAR on probe? restore again
BAR=$(setpci -s 8c:00.0 BASE_ADDRESS_0)
[ "$BAR" = "00000000" ] && setpci -s 8c:00.0 BASE_ADDRESS_0=${START:-0xb0000000}
setpci -s 8c:00.0 COMMAND=0x0006
echo "final BAR=$(setpci -s 8c:00.0 BASE_ADDRESS_0) CMD=$(setpci -s 8c:00.0 COMMAND)"
ls -l /dev/cvgdev* 2>/dev/null || true

echo "=== MMIO after rebind ==="
python3 - << 'PY'
import mmap,os,struct
fd=os.open('/sys/bus/pci/devices/0000:8c:00.0/resource0', os.O_RDWR|os.O_SYNC)
m=mmap.mmap(fd, 16*1024*1024, mmap.MAP_SHARED, mmap.PROT_READ|mmap.PROT_WRITE)
def r(o):
 m.seek(o); return struct.unpack('<I', m.read(4))[0]
for n,o in [('IP',0x10000),('CAP',0x11010),('L0',0x8902C),('PS0',0x89050),('L1',0x8A02C),('PS1',0x8A050),('RATE0',0x30040)]:
  print(f'{n}=0x{r(o):08X}')
m.close(); os.close(fd)
PY
''')

c.close()
