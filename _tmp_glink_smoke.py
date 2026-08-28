import paramiko
import sys
import time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("100.66.1.16", username="root", password="60851.org", timeout=30)

def run(c, timeout=180):
    print("====", c[:180], "====")
    stdin, stdout, stderr = ssh.exec_command(c, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out:
        print(out[-15000:] if len(out) > 15000 else out)
    if err.strip():
        print("STDERR:", err[-6000:] if len(err) > 6000 else err)
    return out, err

smoke = r'''
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include "FC_L1_API.h"

static const char* link_name(unsigned int s) {
    switch (s) {
    case 0: return "INIT";
    case 1: return "OFFLINE";
    case 2: return "LR";
    case 3: return "ACTIVE";
    case 4: return "INVALID";
    default: return "UNKNOWN";
    }
}

int main(void) {
    pDevNode_st list = NULL;
    int r = FC_Dev_ScanLocalDevList(&list);
    printf("ScanLocalDevList ret=%d\n", r);
    int n = 0;
    for (pDevNode_st p = list; p; p = p->pNexDev, n++) {
        printf("  [%d] name=%s bank=%d chl=%d\n", n, p->pName, (int)p->bankNum, (int)p->chlNum);
    }
    int cnt = FC_Dev_GetLocalDevCnt();
    printf("LocalDevCnt=%d\n", cnt);
    if (cnt <= 0) return 1;

    FC_DEV_HANDLE hDev = NULL;
    r = FC_Dev_OpenDevByIndex(0, &hDev, FC_TRUE);
    printf("OpenDevByIndex(0) ret=%d h=%p\n", r, (void*)hDev);
    if (!hDev) return 2;

    FC_DWORD dma=0, gt=0, bank=0, port=0;
    r = FC_Dev_GetChannelNum(hDev, &dma, &gt, &bank, &port);
    printf("GetChannelNum ret=%d DMA/chl=%u GT=%u Bank=%u PortPerCh=%u\n",
           r, dma, gt, bank, port);

    FC_DWORD all = 0;
    r = Dev_Get_AllPortLinkState(hDev, &all);
    printf("AllPortLinkState ret=%d raw=0x%08X\n", r, all);

    unsigned int stations = (dma ? dma : 2);
    unsigned int ports = (port ? port : 2);
    if (stations > 8) stations = 8;
    if (ports > 8) ports = 8;
    for (unsigned int i = 0; i < stations; i++) {
        for (unsigned int j = 0; j < ports; j++) {
            FC_DWORD st = 0;
            int rr = FC_Dev_Get_PortLinkState(hDev, i, (FC_WORD)j, &st);
            printf("  station=%u port=%u ret=%d state=%u (%s)\n",
                   i, j, rr, st, link_name(st));
        }
    }

    FC_Dev_Close(hDev);
    printf("Smoke OK\n");
    return 0;
}
'''

k72 = r'''
#include <stdio.h>
#include <stdint.h>
#include "glink_api.h"
#include "glink_regs.h"

int main(void) {
    if (GlinkOpen() != 0) {
        printf("GlinkOpen failed\n");
        return 1;
    }
    uint32_t fpga=0, jlk=0;
    GlinkGetHardWareInfo(&fpga, &jlk);
    printf("FPGA=0x%X JLK_ID=0x%X\n", fpga, jlk);
    printf("rate=%d\n", (int)GlinkGetRate());
    printf("CH_A_STATUS=0x%04X CH_B_STATUS=0x%04X\n",
           JlkRegRead(JLK_REG_CH_A_STATUS), JlkRegRead(JLK_REG_CH_B_STATUS));
    printf("LinkA=%d LinkB=%d\n",
           GlinkGetLinkStatus(GLINK_CH_A), GlinkGetLinkStatus(GLINK_CH_B));
    printf("A_RUN=0x%04X B_RUN=0x%04X\n",
           GlinkGetARunStatus(), GlinkGetBRunStatus());
    GlinkClose();
    return 0;
}
'''

sftp = ssh.open_sftp()
with sftp.file("/tmp/cvg_smoke.cpp", "w") as f:
    f.write(smoke)
with sftp.file("/tmp/k72_link.c", "w") as f:
    f.write(k72)
sftp.close()

run("""cd /tmp && g++ -g -o cvg_smoke cvg_smoke.cpp -fpermissive \
  -I/opt/soft/Driver/GLink/WGLK220_V3/PublicHead/Commont \
  -I/opt/soft/Driver/GLink/WGLK220_V3/PublicHead/PublicHead \
  -I/opt/soft/Driver/GLink/WGLK220_V3/PublicHead/SysDifferent \
  -I/opt/soft/Driver/GLink/WGLK220_V3/PublicHead/WinDriverHead \
  -L/opt/soft/Driver/GLink/WGLK220_V3/WinApi/FC_L1_API/.libs \
  -L/opt/soft/Driver/GLink/WGLK220_V3/WinApi/FC_L0_API/.libs \
  -Wl,-Bstatic -lfcl1 -lfcl0 -Wl,-Bdynamic -lpthread 2>&1""")

run("""cd /tmp && gcc -g -o k72_link k72_link.c \
  -I/opt/soft/K72_GLink/Code/api \
  -L/opt/soft/K72_GLink/Code/api -lglink_api 2>&1 || \
  (ls /opt/soft/K72_GLink/Code/api/; \
   gcc -g -o k72_link k72_link.c /opt/soft/K72_GLink/Code/api/glink_api.c \
   -I/opt/soft/K72_GLink/Code/api 2>&1)""")

run("/tmp/cvg_smoke 2>&1")
run("/tmp/k72_link 2>&1")
