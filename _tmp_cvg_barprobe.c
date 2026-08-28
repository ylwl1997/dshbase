/* cvg_barprobe.c — probe readable register ranges on Cavige BAR */
#include <stdio.h>
#include <stdint.h>
#include "FC_L1_API.h"

static void rd(FC_DEV_HANDLE h, unsigned off, const char *name)
{
    FC_DWORD v = 0;
    int r = FC_Dev_ReadRegister(h, off, &v);
    printf("  [0x%08X] %-28s ret=%d val=0x%08X%s\n",
           off, name ? name : "", r, v,
           (v == 0xFFFFFFFFu) ? "  <ALL_ONES>" : "");
}

int main(void)
{
    pDevNode_st list = NULL;
    FC_Dev_ScanLocalDevList(&list);
    FC_DEV_HANDLE h = NULL;
    if (FC_Dev_OpenDevByIndex(0, &h, FC_TRUE) != FC_SUCCESS || !h) {
        printf("open fail\n");
        return 1;
    }

    printf("=== Common / PCIe cap region ===\n");
    rd(h, 0x00000, "BAR+0");
    rd(h, 0x00004, "BAR+4");
    rd(h, 0x10000, "REG_COMM / IP_VERSION");
    rd(h, 0x10014, "REDUN_MODE");
    rd(h, 0x11010, "FC_CARD_CAP");
    rd(h, 0x11014, "FC_CH_CAP");
    rd(h, 0x11018, "FC_CARD_SPEED");
    rd(h, 0x1101C, "BD_MEMSIZE");
    rd(h, 0x11020, "DMA_NUM_MASK");
    rd(h, 0x11024, "DMA_DL_FUNC");
    rd(h, 0x11028, "DMA_UL_FUNC");

    printf("=== GT base 0x30000 ===\n");
    for (unsigned o = 0; o <= 0x220; o += 0x4) {
        FC_DWORD v = 0;
        FC_Dev_ReadRegister(h, 0x30000 + o, &v);
        if (v != 0xFFFFFFFFu && v != 0) {
            printf("  GT+0x%X = 0x%08X\n", o, v);
        }
    }
    rd(h, 0x3021C, "GT_CLK_MODE");

    printf("=== MAC ch0 port0 region around 0x89000 ===\n");
    /* REG_1553_BASE 0x80000 + MAC 0x9000 = 0x89000 */
    for (unsigned o = 0; o <= 0xC0; o += 4) {
        FC_DWORD v = 0;
        FC_Dev_ReadRegister(h, 0x89000 + o, &v);
        if (v != 0xFFFFFFFFu) {
            printf("  MAC0+0x%X = 0x%08X\n", o, v);
        }
    }

    printf("=== sparse scan first 1MB for non-FF ===\n");
    int hits = 0;
    for (unsigned off = 0; off < 0x100000; off += 0x1000) {
        FC_DWORD v = 0;
        FC_Dev_ReadRegister(h, off, &v);
        if (v != 0xFFFFFFFFu) {
            printf("  hit 0x%08X = 0x%08X\n", off, v);
            if (++hits >= 64) break;
        }
    }
    printf("hits=%d\n", hits);

    /* try system reset then re-read CARD_CAP */
    printf("=== SystemReset then CARD_CAP ===\n");
    FC_Dev_SystemReset(h);
    usleep(500000);
    rd(h, 0x11010, "FC_CARD_CAP after reset");
    rd(h, 0x10000, "IP_VERSION after reset");

    FC_Dev_Close(h);
    return 0;
}
