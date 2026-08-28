#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Restore BAR, MMIO poll Cavige + bring up K72, try set 2.5G via GT regs."""
import paramiko, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("100.66.1.16", username="root", password="60851.org",
          timeout=20, look_for_keys=False, allow_agent=False)

def run(cmd, t=120):
    print(f"\n===== {cmd[:130]} =====", flush=True)
    _, out, err = c.exec_command(cmd, timeout=t)
    print(out.read().decode("utf-8", "replace"), end="")
    e = err.read().decode("utf-8", "replace")
    if e:
        print("[stderr]", e[:1000])
    print("exit", out.channel.recv_exit_status(), flush=True)

run("grep -rn 'DEEDBEEF\\|deedbeef\\|0x[Dd][Ee][Ee][Dd]' /opt/soft/Driver/GLink/Driver --include='*.c' --include='*.h' 2>/dev/null | sed -n '1,40p'")
run("grep -n 'SetPortSpeed_Bank\\|REG_GT_RATE\\|emSpeed' /opt/soft/Driver/GLink/WGLK220_V3/WinApi/FC_L1_API/FC_Dev_Operate.c | sed -n '1,40p'")
run("sed -n '1470,1650p' /opt/soft/Driver/GLink/WGLK220_V3/WinApi/FC_L1_API/FC_Dev_Operate.c")

# Remote pure-MMIO script
mmio = r'''
import mmap, os, struct, time, subprocess

def ensure_bar():
    bar = subprocess.check_output("setpci -s 8c:00.0 BASE_ADDRESS_0", shell=True).decode().strip()
    if bar == "00000000":
        subprocess.check_call("setpci -s 8c:00.0 BASE_ADDRESS_0=0xb0000000", shell=True)
    subprocess.check_call("setpci -s 8c:00.0 COMMAND=0x0006", shell=True)
    print("BAR0", subprocess.check_output("setpci -s 8c:00.0 BASE_ADDRESS_0", shell=True).decode().strip(),
          "CMD", subprocess.check_output("setpci -s 8c:00.0 COMMAND", shell=True).decode().strip())

def open_bar():
    fd = os.open("/sys/bus/pci/devices/0000:8c:00.0/resource0", os.O_RDWR | os.O_SYNC)
    m = mmap.mmap(fd, 16*1024*1024, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE)
    return fd, m

def r32(m, off):
    m.seek(off)
    return struct.unpack("<I", m.read(4))[0]

def w32(m, off, val):
    m.seek(off)
    m.write(struct.pack("<I", val & 0xffffffff))
    m.seek(off)
    return struct.unpack("<I", m.read(4))[0]

ensure_bar()
fd, m = open_bar()

print("IP_VER   ", hex(r32(m, 0x10000)))
print("CARD_CAP ", hex(r32(m, 0x11010)))
print("CARD_SPD ", hex(r32(m, 0x11018)))
print("GT_RATE  ", hex(r32(m, 0x30060)))
print("GT_CLK   ", hex(r32(m, 0x3021C)))
print("GT_RATE0 ", hex(r32(m, 0x30040)))
print("COMM_GT  ", hex(r32(m, 0x10040)))

# dump link/pstate before
for name, off in [
    ("st0p0_LINK", 0x8902C), ("st0p0_PS", 0x89050),
    ("st0p1_LINK", 0x8A02C), ("st0p1_PS", 0x8A050),
]:
    print(f"{name} {hex(r32(m, off))}")

# Try GLink 2.5G clock mode (V7 path uses CLK_MODE=1 for 1.25/2.5/5)
# Also poke REG_GT_RATE / REG_GT_RATE0 carefully
print("--- try set CLK_MODE=1 and GT rate fields ---")
print("w CLK_MODE", hex(w32(m, 0x3021C, 1)))
time.sleep(0.05)

# Read current GT_RATE0; set nibble pattern for ports if known
# From Demo: PORT_SPEED_2p5G enum=5. Hardware GT encoding may differ.
# Try writing REG_COMM_GT_RATE and REG_GT_RATE with a few candidates and observe link.
candidates = [
    ("gt_rate_0x55", 0x30060, 0x55),
    ("gt_rate_0x22", 0x30060, 0x22),
    ("gt_rate0_0x55", 0x30040, 0x55),
    ("comm_gt_0x55", 0x10040, 0x55),
]
for name, off, val in candidates:
    before = r32(m, off)
    after = w32(m, off, val)
    print(f"  {name}: {hex(before)} -> write {hex(val)} rb {hex(after)}")

# Soft GT reset bits?
print("GT_RESET before", hex(r32(m, 0x30030)))

print("--- poll 12s ---")
for t in range(0, 13):
    ensure_bar()
    # reopen if needed? keep same map
    a = r32(m, 0x8902C); aps = r32(m, 0x89050)
    b = r32(m, 0x8A02C); bps = r32(m, 0x8A050)
    print(f"t={t:2d}s p0_LINK={a:#x} p0_PS={aps:#x} p1_LINK={b:#x} p1_PS={bps:#x} CAP={r32(m,0x11010):#x}")
    time.sleep(1)

m.close(); os.close(fd)
'''

sftp = c.open_sftp()
with sftp.file("/tmp/cvg_mmio_poll.py", "w") as f:
    f.write(mmio)
sftp.close()

# Parallel: start K72 bringup in background while polling Cavige MMIO
run(r'''
# restore bar first
setpci -s 8c:00.0 BASE_ADDRESS_0=0xb0000000
setpci -s 8c:00.0 COMMAND=0x0006

# K72 bringup in background, keep configured
/tmp/k72_bringup --wait 15000 > /tmp/k72_poll.log 2>&1 &
KPID=$!
echo "k72_pid=$KPID"

python3 /tmp/cvg_mmio_poll.py

wait $KPID || true
echo "===== K72 LOG ====="
cat /tmp/k72_poll.log

echo "===== FINAL MMIO snapshot ====="
python3 - << 'PY'
import mmap,os,struct,subprocess
subprocess.call("setpci -s 8c:00.0 BASE_ADDRESS_0=0xb0000000",shell=True)
subprocess.call("setpci -s 8c:00.0 COMMAND=0x0006",shell=True)
fd=os.open("/sys/bus/pci/devices/0000:8c:00.0/resource0",os.O_RDWR|os.O_SYNC)
m=mmap.mmap(fd,16*1024*1024,mmap.MAP_SHARED,mmap.PROT_READ|mmap.PROT_WRITE)
def r(o):
 m.seek(o); return struct.unpack("<I",m.read(4))[0]
print("IP",hex(r(0x10000)),"CAP",hex(r(0x11010)))
print("p0",hex(r(0x8902C)),hex(r(0x89050)),"p1",hex(r(0x8A02C)),hex(r(0x8A050)))
print("GT_RATE",hex(r(0x30060)),"CLK",hex(r(0x3021C)),"RATE0",hex(r(0x30040)))
m.close();os.close(fd)
PY
/tmp/k72_link
''')

c.close()
print("DONE", flush=True)
