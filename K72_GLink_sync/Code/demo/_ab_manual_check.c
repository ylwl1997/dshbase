#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>
#include "../api/glink_api.h"
#include "../api/glink_regs.h"

/*
 * 按软件设计指南 V1.6 表54 核对:
 *   NT type[14:12]: 000=SmartNT1 .. 011=SmartNT4, 100=CtrlNT
 *   短报 SmartNC→SmartNT: 厂家确认 FIFO_SEL 用复位默认 0xC8
 *     (WR=NC1, RD=NT1), 不用 WR=RD=NC 的 0xC0
 *   手册允许 SmartNC短报 访问 CtrlNT 或 SmartNT短报
 */

static void dump(const char *t)
{
    uint16_t st = JlkRegRead(JLK_REG_SMARTNC1_STATUS);
    printf("[%s] MODE=%04X CHEN=%04X SNC=%04X SNT=%04X ST=%04X fail=%u "
           "busy14=%u busy15=%u SEL=%02X RD=%u FC60=%04X FC61=%04X "
           "LKA=%d LKB=%d STAT4=%08X\n",
           t,
           JlkRegRead(JLK_REG_WORK_MODE),
           JlkRegRead(JLK_REG_CHANNEL_EN),
           JlkRegRead(JLK_REG_SMARTNC1_CONFIG),
           JlkRegRead(JLK_REG_SMARTNT1_CONFIG),
           st, (st >> 4) & 0xF, (st >> 14) & 1, (st >> 15) & 1,
           (unsigned)(FpgaRegRead(P_FIFO_SELECT_REGISTER) & 0xFF),
           (unsigned)FpgaRegRead(P_RD_FIFO1_WR_NUM),
           JlkRegRead(0x60), JlkRegRead(0x61),
           GlinkGetLinkStatus(0), GlinkGetLinkStatus(1),
           FpgaRegRead(P_STATUS_REGISTER));
}

static void raw_send(const uint16_t *w, int n, uint32_t sel)
{
    int i;
    FpgaRegWrite(P_FIFO_SELECT_REGISTER, sel);
    printf("  SEL=%02X words:", (unsigned)(FpgaRegRead(P_FIFO_SELECT_REGISTER) & 0xFF));
    for (i = 0; i < n; i++) printf(" %04X", w[i]);
    printf("\n");
    for (i = 0; i < n; i++)
        FpgaRegWrite(P_FIFO1_WRITE_REGISTER, w[i]);
    FpgaRegWrite(P_NC1_SEND_NUM, (uint32_t)n);
    FpgaRegWrite(P_CTRL_REGISTER, CTRL_NC1_TX);
}

static int wait_done(int ms)
{
    int i;
    uint16_t st;
    for (i = 0; i < ms / 10; i++) {
        st = JlkRegRead(JLK_REG_SMARTNC1_STATUS);
        if (!(st & 0xC000))
            return 0;
        usleep(10000);
    }
    return -1;
}

static void try_read_rd(int maxw)
{
    uint32_t n = FpgaRegRead(P_RD_FIFO1_WR_NUM);
    int i;
    printf("  RD_count=%u", (unsigned)n);
    if (n > 2 && n < 512) {
        printf(" data:");
        for (i = 0; i < (int)n - 2 && i < maxw; i++)
            printf(" %04X", (unsigned)(FpgaRegRead(P_DATA_READ_REGISTER) & 0xFFFF));
    }
    printf("\n");
}

/* SmartNC短报 -> CtrlNT (表54 type=100), MODE=SmartNC1|CtrlNT */
static void case_smart_to_ctrlnt(void)
{
    uint16_t w[16];
    uint8_t payload[16];
    int i, n = 0;

    printf("\n==== CASE1 SmartNC->CtrlNT (manual type=100) ====\n");
    K72Reset();
    FpgaRegWrite(P_GC_MODE_REGISTER, 1);
    GlinkSetRate(GLINK_RATE_2G5);
    FpgaFifoReset();
    /* 厂家默认: WR=NC1 RD=NT1 → 0xC8 */
    FpgaRegWrite(P_FIFO_SELECT_REGISTER, 0xC8);

    JlkRegWrite(0x01, 0x0001); usleep(1000); JlkRegWrite(0x01, 0x0000);
    JlkRegWrite(JLK_REG_NODE_ID, NODE_ID_DEFAULT);
    JlkRegWrite(JLK_REG_CHANNEL_EN, 0x0003);
    JlkRegWrite(JLK_REG_INT_MODE, 0x0002);
    JlkRegWrite(JLK_REG_INT_MASK, 0x0804);
    JlkRegWrite(JLK_REG_TIMESTAMP, 0xFFFF);
    /* CtrlNT 必需配置 (同 Ctrl demo) */
    JlkRegWrite(0x24, 0xA0);
    JlkRegWrite(0x25, 0x1C);
    MemorySpaceInit();
    NcMemoryMapInit(0x0200, 0x0400);
    NtChannelMap(0, 0x0003);
    NtChannelMap(1, 0x0003);

    JlkRegWrite(JLK_REG_SMARTNC1_TIMEOUT, 0x8000);
    JlkRegWrite(JLK_REG_SMARTNC1_CONFIG, 0x0400); /* short only */
    JlkRegWrite(JLK_REG_WORK_MODE, (uint16_t)(MODE_SMARTNC1 | MODE_CTRLNT));

    for (i = 0; i < 40; i++) {
        if (GlinkGetLinkStatus(0) && GlinkGetLinkStatus(1)) break;
        usleep(100000);
    }
    dump("pre");

    for (i = 0; i < 16; i++) payload[i] = (uint8_t)(0xA0 + i);
    w[n++] = 0x0001;           /* SA */
    w[n++] = 0x1010;           /* 1 NT, len=16, NT收 */
    w[n++] = 0x4003;           /* type=100 CtrlNT, ID=3 */
    for (i = 0; i < 8; i++)
        w[n++] = (uint16_t)(payload[i * 2] | (payload[i * 2 + 1] << 8));

    raw_send(w, n, 0xC8);
    wait_done(3000);
    dump("post");
    try_read_rd(16);
}

/* SmartNC短报 -> SmartNT1 (表54 type=000) */
static void case_smart_to_smartnt(uint32_t sel)
{
    uint16_t w[16];
    uint8_t payload[16];
    int i, n = 0;

    printf("\n==== CASE2 SmartNC->SmartNT1 type=000 SEL=%02X ====\n",
           (unsigned)sel);
    K72Reset();
    FpgaRegWrite(P_GC_MODE_REGISTER, 1);
    GlinkSetRate(GLINK_RATE_2G5);
    FpgaFifoReset();
    FpgaRegWrite(P_FIFO_SELECT_REGISTER, sel);

    JlkRegWrite(0x01, 0x0001); usleep(1000); JlkRegWrite(0x01, 0x0000);
    JlkRegWrite(JLK_REG_NODE_ID, NODE_ID_DEFAULT);
    JlkRegWrite(JLK_REG_CHANNEL_EN, 0x0003);
    JlkRegWrite(JLK_REG_INT_MODE, 0x0002);
    JlkRegWrite(JLK_REG_TIMESTAMP, 0xFFFF);
    JlkMemWrite(0x0108, 0x3000);
    JlkRegWrite(JLK_REG_SMARTNC1_TIMEOUT, 0x8000);
    JlkRegWrite(JLK_REG_SMARTNC1_CONFIG, 0x0400);
    JlkRegWrite(JLK_REG_SMARTNT1_CONFIG, 0x4000); /* short, no pair */
    JlkRegWrite(JLK_REG_WORK_MODE, (uint16_t)(MODE_SMARTNC1 | MODE_SMARTNT1));

    for (i = 0; i < 40; i++) {
        if (GlinkGetLinkStatus(0) && GlinkGetLinkStatus(1)) break;
        usleep(100000);
    }
    dump("pre");

    for (i = 0; i < 16; i++) payload[i] = (uint8_t)(0xA0 + i);
    w[n++] = 0x0001;
    w[n++] = 0x1010;
    w[n++] = 0x0003; /* type=000 SmartNT1, ID=3 */
    for (i = 0; i < 8; i++)
        w[n++] = (uint16_t)(payload[i * 2] | (payload[i * 2 + 1] << 8));

    raw_send(w, n, sel);
    wait_done(3000);
    dump("post");
    try_read_rd(16);
}

int main(void)
{
    if (GlinkOpenPath(0, "/dev/xdma0_user") != 0) {
        printf("open fail\n");
        return 1;
    }
    printf("=== Manual V1.6 Table54 host check ===\n");
    printf("FIFO_SEL 厂家确认默认 0xC8 (WR=NC1, RD=NT1)\n");
    case_smart_to_ctrlnt();
    case_smart_to_smartnt(0xC8); /* 厂家确认: WR=NC1 RD=NT1 */
    GlinkCloseAll();
    return 0;
}
