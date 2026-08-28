/* cvg_bringup.cpp — open like DemoAPeriod, set 2.5G, poll port link */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <map>
#include "FC_L1_API.h"

static const char *speed_name(int s)
{
    switch (s) {
    case PORT_SPEED_1p25G: return "1.25G";
    case PORT_SPEED_2p5G:  return "2.5G";
    case PORT_SPEED_5G:    return "5G";
    case PORT_SPEED_625M:  return "625M";
    case PORT_SPEED_1G:    return "1G";
    case PORT_SPEED_2G:    return "2G";
    case PORT_SPEED_4G:    return "4G";
    default: return "?";
    }
}

static const char *pstate_name(int s)
{
    switch (s) {
    case PORT_STATE_INIT: return "INIT";
    case PORT_STATE_OFFLINE: return "OFFLINE";
    case PORT_STATE_LR: return "LR";
    case PORT_STATE_AC: return "ACTIVE";
    case PORT_STATE_INVALID: return "INVALID";
    default: return "UNK";
    }
}

int main(int argc, char **argv)
{
    emFC_PORT_SPEED want = PORT_SPEED_2p5G;
    int wait_ms = 8000;
    int do_reset = 1;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--speed") == 0 && i + 1 < argc) {
            const char *s = argv[++i];
            if (!strcmp(s, "2.5") || !strcmp(s, "2p5") || !strcmp(s, "2.5G"))
                want = PORT_SPEED_2p5G;
            else if (!strcmp(s, "5") || !strcmp(s, "5G"))
                want = PORT_SPEED_5G;
            else if (!strcmp(s, "1.25") || !strcmp(s, "1p25"))
                want = PORT_SPEED_1p25G;
            else if (!strcmp(s, "625") || !strcmp(s, "625M"))
                want = PORT_SPEED_625M;
        } else if (strcmp(argv[i], "--wait") == 0 && i + 1 < argc) {
            wait_ms = atoi(argv[++i]);
        } else if (strcmp(argv[i], "--noreset") == 0) {
            do_reset = 0;
        }
    }

    pDevNode_st list = NULL;
    int r = FC_Dev_ScanLocalDevList(&list);
    printf("ScanLocalDevList ret=%d cnt=%d\n", r, FC_Dev_GetLocalDevCnt());
    if (FC_Dev_GetLocalDevCnt() <= 0)
        return 1;

    FC_DEV_HANDLE hDev = NULL;
    r = FC_Dev_OpenDevByIndex(0, &hDev, FC_TRUE);
    printf("OpenDevByIndex ret=%d h=%p\n", r, (void *)hDev);
    if (!hDev)
        return 2;

    FC_DWORD nChl = 0, nGT = 0, nBank = 0, nPort = 0;
    r = FC_Dev_GetChannelNum(hDev, &nChl, &nGT, &nBank, &nPort);
    printf("GetChannelNum ret=%d chl=%u gt=%u bank=%u portPerCh=%u\n",
           r, nChl, nGT, nBank, nPort);

    /* Mirror DemoAPeriod OpenBoard: open chls + GLink protocol + GT port map */
    std::map<int, FC_CHL_HANDLE> chls;
    for (FC_DWORD i = 0; i < nChl; i++) {
        FC_CHL_HANDLE h = NULL;
        r = FC_Dev_OpenChl(hDev, (FC_BYTE)i, &h);
        chls[(int)i] = (r == FC_SUCCESS) ? h : NULL;
        FC_DWORD tempvalue = 0;
        if (nPort == 1)
            tempvalue = (i * nPort) & 0xFF;
        else if (nPort == 2)
            tempvalue = (((i * nPort + 1) << 8) & 0xFF00) | ((i * nPort) & 0xFF);
        int pr = FC_Dev_Set_Ch_Protocol_GTPort(hDev, i, 0x1 /*GLink*/, tempvalue);
        printf("  OpenChl(%u) ret=%d h=%p  SetProtocolGTPort=0x%X ret=%d\n",
               i, r, (void *)h, tempvalue, pr);
    }

    printf("BEFORE speed set; dumping port states...\n");
    for (FC_DWORD i = 0; i < nChl && i < 4; i++) {
        for (FC_DWORD j = 0; j < nPort && j < 2; j++) {
            FC_DWORD ls = 0;
            emDevPortState ps = PORT_STATE_INIT;
            emFC_PORT_SPEED sp = (emFC_PORT_SPEED)0;
            FC_Dev_Get_PortLinkState(hDev, i, (FC_WORD)j, &ls);
            FC_Dev_Get_PortState(hDev, i, (FC_WORD)j, &ps);
            FC_Dev_GetPortSpeed_Bank(hDev, (FC_WORD)i, (FC_WORD)i, (FC_WORD)(i * nPort + j), &sp);
            printf("  BEFORE st=%u port=%u link=%u pstate=%d(%s) speed=%d(%s)\n",
                   i, j, ls, (int)ps, pstate_name(ps), (int)sp, speed_name(sp));
        }
    }

    for (FC_DWORD b = 0; b < nBank; b++) {
        int sr = FC_Dev_SetAllPortSpeed_Bank(hDev, b, want);
        printf("SetAllPortSpeed_Bank(bank=%u, %s) ret=%d\n", b, speed_name(want), sr);
    }

    if (do_reset) {
        printf("Reset_AllPort + sleep 500ms...\n");
        FC_Dev_Reset_AllPort(hDev);
        usleep(500000);
    }

    int elapsed = 0;
    int any_up = 0;
    while (elapsed <= wait_ms) {
        printf("--- t=%dms ---\n", elapsed);
        any_up = 0;
        for (FC_DWORD i = 0; i < nChl && i < 4; i++) {
            for (FC_DWORD j = 0; j < nPort && j < 2; j++) {
                FC_DWORD ls = 0;
                emDevPortState ps = PORT_STATE_INIT;
                emFC_PORT_SPEED sp = (emFC_PORT_SPEED)0;
                FC_Dev_Get_PortLinkState(hDev, i, (FC_WORD)j, &ls);
                FC_Dev_Get_PortState(hDev, i, (FC_WORD)j, &ps);
                FC_Dev_GetPortSpeed_Bank(hDev, (FC_WORD)i, (FC_WORD)i,
                                        (FC_WORD)(i * nPort + j), &sp);
                printf("  st=%u port=%u  physPort=%u  link=%u  pstate=%d(%s)  speed=%d(%s)\n",
                       i, j, (unsigned)(i * nPort + j),
                       ls, (int)ps, pstate_name(ps), (int)sp, speed_name(sp));
                if (ls || ps == PORT_STATE_AC || ps == PORT_STATE_LR)
                    any_up = 1;
            }
        }
        if (any_up)
            break;
        usleep(1000000);
        elapsed += 1000;
    }

    FC_DWORD all = 0;
    Dev_Get_AllPortLinkState(hDev, &all);
    printf("AllPortLinkState=0x%08X any_up=%d\n", all, any_up);

    FC_Dev_Close(hDev);
    printf("cvg_bringup done\n");
    return any_up ? 0 : 10;
}
