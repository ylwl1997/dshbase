#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Restore Cavige BAR if needed, set 2.5G, poll K72+Cavige links, attempt Ctrl smoke."""
import paramiko, sys, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("100.66.1.16", username="root", password="60851.org",
          timeout=20, look_for_keys=False, allow_agent=False)

def run(cmd, t=180):
    print(f"\n===== {cmd[:140]}{'...' if len(cmd)>140 else ''} =====", flush=True)
    _, out, err = c.exec_command(cmd, timeout=t)
    o = out.read().decode("utf-8", "replace")
    e = err.read().decode("utf-8", "replace")
    code = out.channel.recv_exit_status()
    if o: print(o, end="" if o.endswith("\n") else "\n")
    if e: print("[stderr]\n" + e, end="" if e.endswith("\n") else "\n")
    print(f"[exit={code}]", flush=True)
    return code, o, e

# Upload improved cvg tool that restores BAR then brings up
src = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <map>
#include "FC_L1_API.h"
#include "DevRegisterDef.h"

static void dump_ports(FC_DEV_HANDLE h, const char *tag)
{
    printf("[%s]\n", tag);
    for (int ch = 0; ch < 2; ch++) {
        for (int p = 0; p < 2; p++) {
            FC_DWORD raw_link=0, raw_ps=0, api_ls=0;
            emDevPortState ps = PORT_STATE_INIT;
            emFC_PORT_SPEED sp = (emFC_PORT_SPEED)0;
            FC_Dev_ReadRegister(h, REG_MAC_LINK_STATE(ch,p), &raw_link);
            FC_Dev_ReadRegister(h, REG_MAC_PORT_STATE(ch,p), &raw_ps);
            FC_Dev_Get_PortLinkState(h, ch, (FC_WORD)p, &api_ls);
            FC_Dev_Get_PortState(h, ch, (FC_WORD)p, &ps);
            FC_Dev_GetPortSpeed_Bank(h, 0, (FC_WORD)ch, (FC_WORD)(ch*2+p), &sp);
            printf("  ch%d port%d(=光口? phys %d) RAW_LINK=0x%X RAW_PS=0x%X API_link=%u pstate=%d speed=%d\n",
                   ch, p, ch*2+p, raw_link, raw_ps, api_ls, (int)ps, (int)sp);
        }
    }
    FC_DWORD all=0; Dev_Get_AllPortLinkState(h, &all);
    printf("  AllPortLinkState=0x%08X\n", all);
}

int main(int argc, char **argv)
{
    emFC_PORT_SPEED want = PORT_SPEED_2p5G;
    int wait_ms = 12000;
    if (argc>=2 && !strcmp(argv[1],"5")) want = PORT_SPEED_5G;
    if (argc>=3) wait_ms = atoi(argv[2]);

    pDevNode_st list=NULL;
    FC_Dev_ScanLocalDevList(&list);
    FC_DEV_HANDLE h=NULL;
    if (FC_Dev_OpenDevByIndex(0,&h,FC_TRUE)!=FC_SUCCESS || !h) {
        printf("open fail\n"); return 1;
    }

    FC_DWORD cap=0, ver=0;
    FC_Dev_ReadRegister(h, REG_PCIE_IP_VERSION, &ver);
    FC_Dev_ReadRegister(h, REG_PCIE_FC_CARD_CAP, &cap);
    printf("IP_VER=0x%08X CARD_CAP=0x%08X (cardType=0x%X fpga=0x%X clock=%u board=%u)\n",
           ver, cap, cap&0xff, (cap>>8)&0xff, (cap>>16)&0xf, (cap>>20)&0xf);

    FC_DWORD dma=0,gt=0,bank=0,port=0;
    FC_Dev_GetChannelNum(h,&dma,&gt,&bank,&port);
    printf("GetChannelNum dma=%u gt=%u bank=%u port=%u\n", dma,gt,bank,port);

    for (int i=0;i<2;i++) {
        FC_CHL_HANDLE ch=NULL;
        int r=FC_Dev_OpenChl(h,(FC_BYTE)i,&ch);
        FC_DWORD tv=(((i*2+1)<<8)&0xFF00)|((i*2)&0xFF);
        int pr=FC_Dev_Set_Ch_Protocol_GTPort(h,i,0x1,tv);
        printf("OpenChl(%d) ret=%d protoGT=0x%X ret=%d\n", i,r,tv,pr);
    }

    dump_ports(h, "BEFORE_SPEED");

    /* set 2.5G on bank 0 (and 1 if present) */
    int nb = (bank>0 && bank<8) ? (int)bank : 1;
    for (int b=0;b<nb;b++) {
        int r=FC_Dev_SetAllPortSpeed_Bank(h,b,want);
        printf("SetAllPortSpeed_Bank(%d,%d) ret=%d\n", b,(int)want,r);
    }
    FC_Dev_SetAllPortSpeed_KU(h, want);
    FC_Dev_Reset_AllPort(h);
    usleep(500000);
    FC_Dev_LinkReset(h);
    usleep(300000);

    dump_ports(h, "AFTER_SPEED_RESET");

    int t=0, up=0;
    while (t<=wait_ms) {
        printf("--- t=%dms ---\n", t);
        up=0;
        for (int ch=0; ch<1; ch++) { /* station0 ports 0/1 = dual optical */
            for (int p=0;p<2;p++) {
                FC_DWORD raw_link=0, api_ls=0;
                emDevPortState ps=PORT_STATE_INIT;
                FC_Dev_ReadRegister(h, REG_MAC_LINK_STATE(ch,p), &raw_link);
                FC_Dev_Get_PortLinkState(h, ch, (FC_WORD)p, &api_ls);
                FC_Dev_Get_PortState(h, ch, (FC_WORD)p, &ps);
                printf("  st0 port%d RAW_LINK=0x%X API=%u pstate=%d\n", p, raw_link, api_ls, (int)ps);
                if (raw_link==1 || api_ls==1 || ps==PORT_STATE_AC || ps==PORT_STATE_LR)
                    up=1;
            }
        }
        if (up) break;
        usleep(1000000); t+=1000;
    }
    dump_ports(h, "FINAL");
    /* keep handle briefly for peer; close at end */
    FC_Dev_Close(h);
    return up?0:10;
}
'''

sftp = c.open_sftp()
with sftp.file("/tmp/cvg_link2.cpp", "w") as f:
    f.write(src)
sftp.close()

run(r'''
# Ensure BAR0 programmed every time (PCI reset earlier cleared it)
BAR=$(setpci -s 8c:00.0 BASE_ADDRESS_0)
if [ "$BAR" = "00000000" ]; then
  setpci -s 8c:00.0 BASE_ADDRESS_0=0xb0000000
fi
setpci -s 8c:00.0 COMMAND=0x0006
echo "BAR0=$(setpci -s 8c:00.0 BASE_ADDRESS_0) CMD=$(setpci -s 8c:00.0 COMMAND)"

g++ -O2 -fpermissive \
  -I/opt/soft/Driver/GLink/WGLK220_V3/PublicHead/PublicHead \
  -I/opt/soft/Driver/GLink/WGLK220_V3/PublicHead/Commont \
  -I/opt/soft/Driver/GLink/WGLK220_V3/PublicHead/SysDifferent \
  -I/opt/soft/Driver/GLink/WGLK220_V3/PublicHead/WinDriverHead \
  /tmp/cvg_link2.cpp \
  -L/opt/soft/Driver/GLink/WGLK220_V3/WinApi/FC_L1_API/.libs \
  -L/opt/soft/Driver/GLink/WGLK220_V3/WinApi/FC_L0_API/.libs \
  -lfcl1 -lfcl0 -lpthread -o /tmp/cvg_link2 && echo COMPILE_OK
''')

# Run Cavige bringup and K72 in overlapping fashion via background
run(r'''
# BAR guard
BAR=$(setpci -s 8c:00.0 BASE_ADDRESS_0); [ "$BAR" = "00000000" ] && setpci -s 8c:00.0 BASE_ADDRESS_0=0xb0000000
setpci -s 8c:00.0 COMMAND=0x0006

echo "======== CVG 2.5G ========"
/tmp/cvg_link2 2.5 10000
echo "======== K72 after/during ========"
/tmp/k72_bringup --wait 8000
echo "======== CVG quick recheck ========"
BAR=$(setpci -s 8c:00.0 BASE_ADDRESS_0); [ "$BAR" = "00000000" ] && setpci -s 8c:00.0 BASE_ADDRESS_0=0xb0000000
setpci -s 8c:00.0 COMMAND=0x0006
/tmp/cvg_smoke
python3 - << 'PY'
import mmap,os,struct
fd=os.open('/sys/bus/pci/devices/0000:8c:00.0/resource0', os.O_RDWR|os.O_SYNC)
m=mmap.mmap(fd,16*1024*1024,mmap.MAP_SHARED,mmap.PROT_READ|mmap.PROT_WRITE)
# station0 port0/1 link+pstate; also try station1
offs=[
 (0x8902C,'st0p0_LINK'),(0x89050,'st0p0_PS'),
 (0x8A02C,'st0p1_LINK'),(0x8A050,'st0p1_PS'),
 (0x9902C,'st1p0_LINK'),(0x99050,'st1p0_PS'),
 (0x9A02C,'st1p1_LINK'),(0x9A050,'st1p1_PS'),
 (0x11010,'CARD_CAP'),(0x10000,'IP_VER'),
]
for off,name in offs:
    m.seek(off); v=struct.unpack('<I',m.read(4))[0]
    print(f'{name:12s} @0x{off:X} = 0x{v:08X}')
m.close(); os.close(fd)
PY
''')

c.close()
print("DONE", flush=True)
