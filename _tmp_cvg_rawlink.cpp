/* cvg_rawlink.cpp — dump capability + raw MAC link/port regs + set speed carefully */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "FC_L1_API.h"
#include "DevRegisterDef.h"

static void dump_cap(FC_DEV_HANDLE h)
{
    FC_Dev_Cap_st cap;
    memset(&cap, 0, sizeof(cap));
    int r = FC_Dev_GetCapability(h, &cap);
    printf("GetCapability ret=%d\n", r);
    printf("  nFpgaType=0x%X nChlNum=%u nBankNum=%u nPortNum=%u nChlMode=%u nClock=%u\n",
           cap.nFpgaType, cap.nChlNum, cap.nBankNum, cap.nPortNum, cap.nChlMode, cap.nClock);

    FC_HardWareInfo_st hi;
    memset(&hi, 0, sizeof(hi));
    r = FC_Dev_Get_HardWareInfo(h, &hi);
    printf("Get_HardWareInfo ret=%d\n", r);
    /* print raw bytes of struct cautiously */
    unsigned char *p = (unsigned char *)&hi;
    printf("  HardWareInfo raw[64]:");
    for (int i = 0; i < 64; i++)
        printf(" %02X", p[i]);
    printf("\n");
}

static void dump_mac(FC_DEV_HANDLE h, int max_ch)
{
    printf("RAW REG_MAC_LINK_STATE / PORT_STATE / offline cnt:\n");
    for (int ch = 0; ch < max_ch; ch++) {
        for (int port = 0; port < 2; port++) {
            FC_DWORD link = 0, pstate = 0, off = 0;
            FC_Dev_ReadRegister(h, REG_MAC_LINK_STATE(ch, port), &link);
            FC_Dev_ReadRegister(h, REG_MAC_PORT_STATE(ch, port), &pstate);
            FC_Dev_ReadRegister(h, REG_MAC_LINK_OFFLINE_CNT(ch, port), &off);
            FC_DWORD api_ls = 0;
            emDevPortState ps = PORT_STATE_INIT;
            FC_Dev_Get_PortLinkState(h, ch, (FC_WORD)port, &api_ls);
            FC_Dev_Get_PortState(h, ch, (FC_WORD)port, &ps);
            printf("  ch=%d port=%d RAW_LINK=0x%08X RAW_PSTATE=0x%08X OFFCNT=%u API_link=%u API_pstate=%d\n",
                   ch, port, link, pstate, off, api_ls, (int)ps);
        }
    }
}

int main(int argc, char **argv)
{
    emFC_PORT_SPEED want = PORT_SPEED_2p5G;
    int hold_ms = 15000;
    if (argc >= 2) {
        if (!strcmp(argv[1], "5")) want = PORT_SPEED_5G;
        else if (!strcmp(argv[1], "2.5")) want = PORT_SPEED_2p5G;
        else if (!strcmp(argv[1], "1.25")) want = PORT_SPEED_1p25G;
    }
    if (argc >= 3)
        hold_ms = atoi(argv[2]);

    pDevNode_st list = NULL;
    FC_Dev_ScanLocalDevList(&list);
    FC_DEV_HANDLE h = NULL;
    if (FC_Dev_OpenDevByIndex(0, &h, FC_TRUE) != FC_SUCCESS || !h) {
        printf("open fail\n");
        return 1;
    }

    dump_cap(h);

    FC_DWORD dma=0, gt=0, bank=0, port=0;
    FC_Dev_GetChannelNum(h, &dma, &gt, &bank, &port);
    printf("GetChannelNum dma=%u gt=%u bank=%u port=%u\n", dma, gt, bank, port);

    /* open first 2 channels like Demo (DMA resource limited) */
    for (int i = 0; i < 2; i++) {
        FC_CHL_HANDLE ch = NULL;
        int r = FC_Dev_OpenChl(h, (FC_BYTE)i, &ch);
        FC_DWORD tv = (((i * 2 + 1) << 8) & 0xFF00) | ((i * 2) & 0xFF);
        int pr = FC_Dev_Set_Ch_Protocol_GTPort(h, i, 0x1, tv);
        printf("OpenChl(%d) ret=%d SetProtoGT=0x%X ret=%d\n", i, r, tv, pr);
    }

    printf("\n=== BEFORE speed ===\n");
    dump_mac(h, 4);
    FC_DWORD all = 0;
    Dev_Get_AllPortLinkState(h, &all);
    printf("AllPortLinkState=0x%08X\n", all);

    /* only banks 0..1 like a normal dual-port card; Demo uses m_nBankNum */
    int nb = (int)bank;
    if (nb <= 0 || nb > 4) nb = 1;
    printf("\nSetting speed enum=%d on banks 0..%d\n", (int)want, nb - 1);
    for (int b = 0; b < nb; b++) {
        int r = FC_Dev_SetAllPortSpeed_Bank(h, b, want);
        printf("  SetAllPortSpeed_Bank(%d) ret=%d\n", b, r);
    }
    /* also try KU all-port API */
    int rk = FC_Dev_SetAllPortSpeed_KU(h, want);
    printf("  SetAllPortSpeed_KU ret=%d\n", rk);

    FC_Dev_Reset_AllPort(h);
    usleep(500000);

    /* also try LinkReset */
    FC_Dev_LinkReset(h);
    usleep(200000);

    int t = 0;
    while (t <= hold_ms) {
        printf("\n=== t=%dms ===\n", t);
        dump_mac(h, 2);
        Dev_Get_AllPortLinkState(h, &all);
        printf("AllPortLinkState=0x%08X\n", all);
        /* speed readback station0 ports */
        for (int j = 0; j < 2; j++) {
            emFC_PORT_SPEED sp = (emFC_PORT_SPEED)0;
            FC_Dev_GetPortSpeed_Bank(h, 0, 0, (FC_WORD)j, &sp);
            printf("  GetPortSpeed_Bank(bank0,ch0,port%d)=%d\n", j, (int)sp);
        }
        usleep(2000000);
        t += 2000;
    }

    FC_Dev_Close(h);
    return 0;
}
