#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import paramiko, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("100.66.1.16", username="root", password="60851.org",
          timeout=20, look_for_keys=False, allow_agent=False)

def run(cmd, t=120):
    print(f"\n===== {cmd[:140]} =====", flush=True)
    _, out, err = c.exec_command(cmd, timeout=t)
    print(out.read().decode("utf-8", "replace"), end="")
    e = err.read().decode("utf-8", "replace")
    if e:
        print("[stderr]", e[:1200])
    print("exit", out.channel.recv_exit_status(), flush=True)

run(r'''
set -e
echo "=== before: modules/devs ==="
lsmod | egrep 'cvg|xdma' || true
ls -l /dev/cvgdev* /dev/xdma* 2>/dev/null || true
lspci -s 8c:00.0 -n
echo "BAR=$(setpci -s 8c:00.0 BASE_ADDRESS_0) CMD=$(setpci -s 8c:00.0 COMMAND)"

echo "=== unload cvgDrv ==="
rmmod cvgDrv || true
sleep 1

echo "=== pci remove + rescan ==="
echo 1 > /sys/bus/pci/devices/0000:8c:00.0/remove
sleep 1
echo 1 > /sys/bus/pci/rescan
sleep 2

echo "=== after rescan ==="
lspci -s 8c:00.0 -vv | egrep 'Control:|Region 0|DevSta:|LnkSta:' || echo 'DEVICE MISSING'
if ! lspci -s 8c:00.0 -n >/dev/null 2>&1; then
  echo "FATAL: device not back after rescan"
  exit 2
fi
echo "BAR=$(setpci -s 8c:00.0 BASE_ADDRESS_0) CMD=$(setpci -s 8c:00.0 COMMAND)"
# enable mem+bm if needed
CMD=$(setpci -s 8c:00.0 COMMAND)
# set bits 1 and 2 without clearing others if possible
setpci -s 8c:00.0 COMMAND=0x0006
echo "CMD_now=$(setpci -s 8c:00.0 COMMAND) BAR=$(setpci -s 8c:00.0 BASE_ADDRESS_0)"

echo "=== MMIO before driver ==="
python3 - << 'PY'
import mmap,os,struct
path='/sys/bus/pci/devices/0000:8c:00.0/resource0'
fd=os.open(path, os.O_RDWR|os.O_SYNC)
m=mmap.mmap(fd, min(os.fstat(fd).st_size, 0x20000), mmap.MAP_SHARED, mmap.PROT_READ|mmap.PROT_WRITE)
def r(o):
  m.seek(o); return struct.unpack('<I', m.read(4))[0]
for o,n in [(0,'+0'),(0x10000,'IP'),(0x11010,'CAP'),(0x8902C,'L0'),(0x89050,'PS0'),(0x8A02C,'L1'),(0x8A050,'PS1'),(0x30060,'GT_RATE')]:
  try:
    print(f'{n:8s} @0x{o:X} = 0x{r(o):08X}')
  except Exception as e:
    print(n, e)
m.close(); os.close(fd)
PY

echo "=== load cvgDrv ==="
insmod /opt/soft/Driver/GLink/Driver/cvgDrv.ko || modprobe cvgDrv || true
sleep 1
ls -l /dev/cvgdev* 2>/dev/null || true
lsmod | grep cvg || true

# ensure command still good after driver bind
setpci -s 8c:00.0 COMMAND=0x0006
# if BAR cleared by something, restore from resource file
BAR=$(setpci -s 8c:00.0 BASE_ADDRESS_0)
if [ "$BAR" = "00000000" ]; then
  echo "BAR cleared after bind; restoring b0000000"
  setpci -s 8c:00.0 BASE_ADDRESS_0=0xb0000000
  setpci -s 8c:00.0 COMMAND=0x0006
fi
echo "final BAR=$(setpci -s 8c:00.0 BASE_ADDRESS_0) CMD=$(setpci -s 8c:00.0 COMMAND)"
lspci -s 8c:00.0 -vv | egrep 'Control:|Region 0'

echo "=== MMIO after driver ==="
python3 - << 'PY'
import mmap,os,struct
fd=os.open('/sys/bus/pci/devices/0000:8c:00.0/resource0', os.O_RDWR|os.O_SYNC)
m=mmap.mmap(fd, 16*1024*1024, mmap.MAP_SHARED, mmap.PROT_READ|mmap.PROT_WRITE)
def r(o):
  m.seek(o); return struct.unpack('<I', m.read(4))[0]
for o,n in [(0,'+0'),(0x10000,'IP'),(0x11010,'CAP'),(0x8902C,'L0'),(0x89050,'PS0'),(0x8A02C,'L1'),(0x8A050,'PS1'),(0x30040,'RATE0'),(0x30060,'GT_RATE'),(0x3021C,'CLK')]:
  print(f'{n:8s} = 0x{r(o):08X}')
m.close(); os.close(fd)
PY

# leave xdma alone
lsmod | egrep 'xdma|cvg'
ls -l /dev/xdma* /dev/cvgdev* 2>/dev/null
''')

c.close()
print("DONE recover", flush=True)
