/* k72_bringup.c — reset/rate/config then poll CH_A/B link */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "glink_api.h"
#include "glink_regs.h"

static void dump_once(const char *tag)
{
    printf("[%s] rate=%d CH_A=0x%04X CH_B=0x%04X LinkA=%d LinkB=%d A_RUN=0x%04X B_RUN=0x%04X WORK=0x%04X CH_EN=0x%04X ID=0x%04X\n",
           tag,
           (int)GlinkGetRate(),
           JlkRegRead(JLK_REG_CH_A_STATUS),
           JlkRegRead(JLK_REG_CH_B_STATUS),
           GlinkGetLinkStatus(GLINK_CH_A),
           GlinkGetLinkStatus(GLINK_CH_B),
           GlinkGetARunStatus(),
           GlinkGetBRunStatus(),
           JlkRegRead(JLK_REG_WORK_MODE),
           JlkRegRead(JLK_REG_CHANNEL_EN),
           JlkRegRead(JLK_REG_NODE_ID));
}

int main(int argc, char **argv)
{
    int wait_ms = 8000;
    int set_rate = 1;
    int do_cfg = 1;
    int rate_val = GLINK_RATE_2G5;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--wait") == 0 && i + 1 < argc)
            wait_ms = atoi(argv[++i]);
        else if (strcmp(argv[i], "--rate") == 0 && i + 1 < argc)
            rate_val = atoi(argv[++i]);
        else if (strcmp(argv[i], "--nocfg") == 0)
            do_cfg = 0;
        else if (strcmp(argv[i], "--norate") == 0)
            set_rate = 0;
    }

    if (GlinkOpen() != 0) {
        printf("GlinkOpen failed\n");
        return 1;
    }

    dump_once("before");

    if (do_cfg) {
        printf("K72Reset + GC_MODE=1 + JlkConfig(NC_NT)...\n");
        if (K72Reset() != 0) {
            printf("K72Reset failed\n");
            GlinkClose();
            return 2;
        }
        FpgaRegWrite(P_GC_MODE_REGISTER, 1);
        if (set_rate) {
            GlinkSetRate((glink_rate_t)rate_val);
            printf("GlinkSetRate(%d) -> readback %d\n", rate_val, (int)GlinkGetRate());
        }
        if (JlkConfig(0x8003, GLINK_ROLE_NC_NT) != 0) {
            printf("JlkConfig failed\n");
            GlinkClose();
            return 3;
        }
        JlkRegWrite(JLK_REG_CHANNEL_EN, CHANNEL_EN_AB);
        MemorySpaceInit();
    } else if (set_rate) {
        GlinkSetRate((glink_rate_t)rate_val);
        printf("GlinkSetRate(%d) -> readback %d\n", rate_val, (int)GlinkGetRate());
    }

    dump_once("after_cfg");

    int elapsed = 0;
    while (elapsed <= wait_ms) {
        int a = GlinkGetLinkStatus(GLINK_CH_A);
        int b = GlinkGetLinkStatus(GLINK_CH_B);
        printf("t=%4dms LinkA=%d LinkB=%d A=0x%04X B=0x%04X\n",
               elapsed, a, b,
               JlkRegRead(JLK_REG_CH_A_STATUS),
               JlkRegRead(JLK_REG_CH_B_STATUS));
        if (a || b)
            break;
        usleep(500000);
        elapsed += 500;
    }

    dump_once("final");
    GlinkClose();
    return 0;
}
