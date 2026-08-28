#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Safe Cavige health check + K72 link; avoid destructive rescan unless needed."""
import paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("100.66.1.16", username="root", password="60851.org",
          timeout=20, look_for_keys=False, allow_agent=False)

def run(cmd, t=90):
    print(f"\n===== {cmd[:120]} =====", flush=True)
    _, out, err = c.exec_command(cmd, timeout=t)
    o = out.read().decode("utf-8", "replace")
    e = err.read().decode("utf-8", "replace")
    print(o, end="" if not o or o.endswith("\n") else "\n")
    if e:
        print("[stderr]", e[:800])
    print("exit", out.channel.recv_exit_status(), flush=True)
    return o

# Status only first — no remove/rescan
o = run(r'''
echo "=== drivers/devs ==="
lsmod | egrep 'cvg|xdma' || true
ls -l /dev/cvgdev* /dev/xdma* 2>/dev/null || true
echo "=== Cavige PCI ==="
lspci -s 8c:00.0 -n 2>/dev/null || echo MISSING
lspci -s 8c:00.0 -vv 2>/dev/null | egrep 'Control:|Region 0|DevSta:|LnkSta:' || true
echo "BAR=$(setpci -s 8c:00.0 BASE_ADDRESS_0 2>/dev/null) CMD=$(setpci -s 8c:00.0 COMMAND 2>/dev/null)"

# Fix BAR/CMD if device present and BAR zero
if lspci -s 8c:00.0 -n >/dev/null 2>&1; then
  BAR=$(setpci -s 8c:00.0 BASE_ADDRESS_0)
  if [ "$BAR" = "00000000" ]; then
    # use resource file start if available
    START=$(awk 'NR==1{printf "0x%x",$1+0}' /sys/bus/pci/devices/0000:8c:00.0/resource 2>/dev/null)
    echo "BAR0 was 0; restoring from resource start=$START"
    if [ -n "$START" ] && [ "$START" != "0x0" ]; then
      setpci -s 8c:00.0 BASE_ADDRESS_0=$START
    else
      setpci -s 8c:00.0 BASE_ADDRESS_0=0xb0000000
    fi
  fi
  setpci -s 8c:00.0 COMMAND=0x0006
  echo "AFTER BAR=$(setpci -s 8c:00.0 BASE_ADDRESS_0) CMD=$(setpci -s 8c:00.0 COMMAND)"
fi

echo "=== Cavige MMIO ==="
python3 - << 'PY'
import mmap,os,struct,sys
path='/sys/bus/pci/devices/0000:8c:00.0/resource0'
if not os.path.exists(path):
    print('no resource0'); sys.exit(0)
fd=os.open(path, os.O_RDWR|os.O_SYNC)
size=min(os.fstat(fd).st_size, 16*1024*1024)
m=mmap.mmap(fd, size, mmap.MAP_SHARED, mmap.PROT_READ|mmap.PROT_WRITE)
def r(o):
    if o+4>size: return None
    m.seek(o); return struct.unpack('<I', m.read(4))[0]
vals={}
for n,o in [('+0',0),('IP',0x10000),('CAP',0x11010),('L0',0x8902C),('PS0',0x89050),('L1',0x8A02C),('PS1',0x8A050),('RATE0',0x30040),('GTRATE',0x30060),('CLK',0x3021C)]:
    v=r(o); vals[n]=v
    print(f'{n:6s}=0x{v:08X}' if v is not None else f'{n}=ERR')
# interpret
def link_ok(v):
    return v is not None and v != 0xFFFFFFFF and v != 0xDEEDBEEF and (v & 1)==1
def dead(v):
    return v in (None, 0xFFFFFFFF, 0xDEEDBEEF)
print('MMIO_DEAD', all(dead(vals[k]) for k in ('IP','CAP','L0','L1')))
print('PORT0_LINK_BIT', link_ok(vals['L0']), 'raw', hex(vals['L0']) if vals['L0'] is not None else None)
print('PORT1_LINK_BIT', link_ok(vals['L1']), 'raw', hex(vals['L1']) if vals['L1'] is not None else None)
m.close(); os.close(fd)
PY

echo "=== K72 link ==="
if [ -x /tmp/k72_link ]; then /tmp/k72_link; else echo no k72_link; fi
''')

# If MMIO still dead, try soft recovery: reload driver only (no pci remove)
if "MMIO_DEAD True" in o or "0xDEEDBEEF" in o:
    run(r'''
echo "=== soft recover: reload cvgDrv ==="
# ensure BAR first
if lspci -s 8c:00.0 -n >/dev/null 2>&1; then
  BAR=$(setpci -s 8c:00.0 BASE_ADDRESS_0)
  [ "$BAR" = "00000000" ] && setpci -s 8c:00.0 BASE_ADDRESS_0=0xb0000000
  setpci -s 8c:00.0 COMMAND=0x0006
fi
rmmod cvgDrv 2>/dev/null || true
sleep 1
# re-enable mem before insmod
setpci -s 8c:00.0 COMMAND=0x0006 2>/dev/null || true
BAR=$(setpci -s 8c:00.0 BASE_ADDRESS_0 2>/dev/null || echo none)
[ "$BAR" = "00000000" ] && setpci -s 8c:00.0 BASE_ADDRESS_0=0xb0000000
insmod /opt/soft/Driver/GLink/Driver/cvgDrv.ko
sleep 1
setpci -s 8c:00.0 COMMAND=0x0006
BAR=$(setpci -s 8c:00.0 BASE_ADDRESS_0)
[ "$BAR" = "00000000" ] && setpci -s 8c:00.0 BASE_ADDRESS_0=0xb0000000 && setpci -s 8c:00.0 COMMAND=0x0006
echo "BAR=$(setpci -s 8c:00.0 BASE_ADDRESS_0) CMD=$(setpci -s 8c:00.0 COMMAND)"
ls -l /dev/cvgdev* 2>/dev/null
python3 - << 'PY'
import mmap,os,struct
fd=os.open('/sys/bus/pci/devices/0000:8c:00.0/resource0', os.O_RDWR|os.O_SYNC)
m=mmap.mmap(fd, 16*1024*1024, mmap.MAP_SHARED, mmap.PROT_READ|mmap.PROT_WRITE)
def r(o):
 m.seek(o); return struct.unpack('<I',m.read(4))[0]
for n,o in [('IP',0x10000),('CAP',0x11010),('L0',0x8902C),('PS0',0x89050),('L1',0x8A02C),('PS1',0x8A050),('RATE0',0x30040)]:
 print(f'{n}=0x{r(o):08X}')
m.close(); os.close(fd)
PY
lsmod | egrep 'cvg|xdma'
''')

c.close()
print("DONE status", flush=True)
