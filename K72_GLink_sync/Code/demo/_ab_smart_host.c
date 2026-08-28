#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>
#include "../api/glink_api.h"
#include "../api/glink_regs.h"

/*
 * 按厂家 SmartNCShortMsg DSP demo 对齐的主机侧复测
 * 假设: 厂家 K72 FPGA 桥接正确; 查软件配置/组帧/SEL/通道
 *
 * DSP demo 要点:
 *   REG00 NODE=0x0200 (demo板); 我们AB用 0x8003
 *   REG03 CHEN=0x0003
 *   REG02 MODE=SmartNC1 only 或 SmartNT1 only (分板);
 *         单卡AB必须 SmartNC1|SmartNT1=0x0110
 *   REG29 TIMEOUT=0x8000
 *   REG2A CONFIG=0x0400 (仅短报bit10)
 *   表54: sa=1, conf=0x1010 (len=16, 1个NT, 无重传), nt=0x0001型SmartNT1
 *   触发: FPGA侧 TRIG (对应我们 P_CTRL + WD)
 */

static void dump(const char *t)
{
    uint16_t st = JlkRegRead(JLK_REG_SMARTNC1_STATUS);
    printf("[%s] ID=%04X MODE=%04X CHEN=%04X TO=%04X SNC=%04X SNT=%04X "
           "ST=%04X fail=%u SP=%04X FC61=%04X SEL=%02X WD=%u RD=%u "
           "LKA=%d LKB=%d STAT4=%08X DBG=%08X\n",
           t,
           JlkRegRead(JLK_REG_NODE_ID),
           JlkRegRead(JLK_REG_WORK_MODE),
           JlkRegRead(JLK_REG_CHANNEL_EN),
           JlkRegRead(JLK_REG_SMARTNC1_TIMEOUT),
           JlkRegRead(JLK_REG_SMARTNC1_CONFIG),
           JlkRegRead(JLK_REG_SMARTNT1_CONFIG),
           st, (st >> 4) & 0xF, SmartNcGetCurrentSp(1),
           JlkRegRead(0x61),
           (unsigned)(FpgaRegRead(P_FIFO_SELECT_REGISTER) & 0xFF),
           (unsigned)FpgaRegRead(P_WD_FIFO1_WR_NUM),
           (unsigned)FpgaRegRead(P_RD_FIFO1_WR_NUM),
           GlinkGetLinkStatus(0), GlinkGetLinkStatus(1),
           FpgaRegRead(P_STATUS_REGISTER),
           FpgaGetDebug());
}

/* 低层: 不改 SEL, 直接写 WD + SEND_NUM + CTRL (贴近厂家桥用法) */
static void raw_send_words(const uint16_t *w, int n)
{
    int i;
    /* 保持复位默认 SEL=0xC8: F1_WR=NC1, F1_RD=NT1 —— 单卡AB最合适 */
    printf("  SEL keep=%02X, write %d words to WD then CTRL\n",
           (unsigned)(FpgaRegRead(P_FIFO_SELECT_REGISTER) & 0xFF), n);
    for (i = 0; i < n; i++)
        FpgaRegWrite(P_FIFO1_WRITE_REGISTER, w[i]);
    FpgaRegWrite(P_NC1_SEND_NUM, (uint32_t)n);
    FpgaRegWrite(P_CTRL_REGISTER, CTRL_NC1_TX);
}

static int bringup_ab(uint16_t chen, uint16_t snc_cfg, uint16_t snt_cfg,
                      int use_api_init)
{
    K72Reset();
    FpgaRegWrite(P_GC_MODE_REGISTER, 1);
    GlinkSetRate(GLINK_RATE_2G5);
    FpgaFifoReset();
    /* 复位默认: F1_WR=NC1, F1_RD=NT1 (RTL); 强制写回, 避免历史 SEL 残留 */
    FpgaRegWrite(P_FIFO_SELECT_REGISTER, 0xC8);

    /* demo: REG01 soft reset */
    JlkRegWrite(0x01, 0x0001);
    usleep(1000);
    JlkRegWrite(0x01, 0x0000);

    JlkRegWrite(JLK_REG_NODE_ID, NODE_ID_DEFAULT); /* 0x8003 */
    JlkRegWrite(JLK_REG_CHANNEL_EN, chen);
    JlkRegWrite(JLK_REG_INT_MODE, 0x0002);
    JlkRegWrite(JLK_REG_TIMESTAMP, 0xFFFF);
    JlkRegWrite(JLK_REG_WORK_MODE, (uint16_t)(MODE_SMARTNC1 | MODE_SMARTNT1));
    /* Smart 不刷全 MEM(会冲 SP); 仅设 SP */
    JlkMemWrite(0x0108, 0x3000); /* SP */

    JlkRegWrite(JLK_REG_SMARTNC1_TIMEOUT, 0x8000); /* demo */
    JlkRegWrite(JLK_REG_SMARTNC1_CONFIG, snc_cfg);
    JlkRegWrite(JLK_REG_SMARTNT1_CONFIG, snt_cfg);

    if (use_api_init) {
        smartnc_config_t snc;
        smartnt_config_t snt;
        memset(&snc, 0, sizeof(snc));
        snc.timeout = 0x8000;
        snc.short_msg_mode = 1;
        snc.single_channel = 0;
        SmartNcInit(1, &snc);
        memset(&snt, 0, sizeof(snt));
        /* 厂家短报: REG3C=0x4000, 无需配对 NC ID */
        snt.pair_nc_id = 0;
        snt.pair_nc_ch = 0;
        snt.short_msg_mode = 1;
        SmartNtInit(1, &snt);
    }

    for (int i = 0; i < 40; i++) {
        if (GlinkGetLinkStatus(0) && GlinkGetLinkStatus(1))
            break;
        usleep(100000);
    }
    printf("LINK A=%d B=%d CHEN=0x%04X SNC=0x%04X SNT=0x%04X\n",
           GlinkGetLinkStatus(0), GlinkGetLinkStatus(1),
           JlkRegRead(JLK_REG_CHANNEL_EN),
           JlkRegRead(JLK_REG_SMARTNC1_CONFIG),
           JlkRegRead(JLK_REG_SMARTNT1_CONFIG));
    return (GlinkGetLinkStatus(0) && GlinkGetLinkStatus(1)) ? 0 : -1;
}

static void run_case(const char *name, uint16_t chen, uint16_t snc_cfg,
                     uint16_t snt_cfg, uint16_t sa, uint16_t conf,
                     uint16_t nt_word, int n_payload_bytes)
{
    uint16_t words[3 + 256];
    uint8_t tx[64];
    int n = 0, i, wc;
    uint32_t rd0, rd1;
    uint16_t st;

    printf("\n######## %s ########\n", name);
    if (bringup_ab(chen, snc_cfg, snt_cfg, 0) != 0) {
        printf("AB link fail\n");
        return;
    }
    dump("pre");

    for (i = 0; i < n_payload_bytes; i++)
        tx[i] = (uint8_t)(0xA0 + i);

    words[n++] = sa;
    words[n++] = conf;
    words[n++] = nt_word;
    wc = (n_payload_bytes + 1) / 2;
    for (i = 0; i < wc; i++) {
        uint16_t lo = tx[i * 2];
        uint16_t hi = (i * 2 + 1 < n_payload_bytes) ? tx[i * 2 + 1] : 0;
        words[n++] = (uint16_t)(lo | (hi << 8));
    }

    printf("  frame:");
    for (i = 0; i < n; i++)
        printf(" %04X", words[i]);
    printf(" (%d words)\n", n);

    rd0 = FpgaRegRead(P_RD_FIFO1_WR_NUM);
    raw_send_words(words, n);
    usleep(50000);
    dump("50ms");
    for (i = 0; i < 60; i++) {
        st = JlkRegRead(JLK_REG_SMARTNC1_STATUS);
        if (!(st & 0xC000) && ((st >> 4) & 0xF))
            break; /* fail_cnt set and not busy */
        if (!(st & 0xC000) && i > 5)
            break;
        usleep(50000);
    }
    dump("done");
    rd1 = FpgaRegRead(P_RD_FIFO1_WR_NUM);
    printf("  RD %u->%u  FC61=%04X\n", (unsigned)rd0, (unsigned)rd1,
           JlkRegRead(0x61));
    if (rd1 != rd0)
        printf("  *** RD changed — possible RX ***\n");
    else
        printf("  no RD change\n");

    /* FPGA STATUS done bits */
    printf("  FPGA P_STATUS=%08X\n", FpgaRegRead(P_STATUS_REGISTER));
}

int main(void)
{
    if (GlinkOpenPath(0, "/dev/xdma0_user") != 0) {
        printf("open fail\n");
        return 1;
    }
    printf("=== Host-side Smart recheck (assume vendor FPGA OK) ===\n");

    /* A: 厂家短报: SNT=0x4000(无需配对), 帧 nt=0x4003 (同 demo 0x4001 编码, ID=本节点3) */
    run_case("A vendor-short SNT=0x4000 nt=0x4003 CHEN=0x0003 SNC=0x0400",
             0x0003, 0x0400, 0x4000,
             0x0001, 0x1010, 0x4003, 16);

    /* B: 同上 + CHEN=0x00C3 */
    run_case("B vendor-short CHEN=0x00C3 nt=0x4003",
             0x00C3, 0x0400, 0x4000,
             0x0001, 0x1010, 0x4003, 16);

    /* C: 带重传 */
    run_case("C retry conf=0x1410 nt=0x4003",
             0x00C3, 0x0400, 0x4000,
             0x0001, 0x1410, 0x4003, 16);

    /* D: 旧误用 type=0 的 nt=0x0003 对照 */
    run_case("D old nt=0x0003 (type0) SNT=0x4000",
             0x0003, 0x0400, 0x4000,
             0x0001, 0x1010, 0x0003, 16);

    /* E: SNT 带 pair_nc_id=3 (长报风格) */
    run_case("E SNT=0x4003 pair+short nt=0x4003",
             0x00C3, 0x0400, 0x4003,
             0x0001, 0x1010, 0x4003, 16);

    /* F: API SendEx, nt_type=4 → 帧字 0x4003, SEL 只改 WR */
    printf("\n######## F API SmartNcShortMsgSendEx type=4 ########\n");
    if (bringup_ab(0x0003, 0x0400, 0x4000, 1) == 0) {
        uint8_t tx[16];
        uint32_t rd0, rd1;
        int i;
        for (i = 0; i < 16; i++) tx[i] = (uint8_t)(0xA0 + i);
        dump("F-pre");
        rd0 = FpgaRegRead(P_RD_FIFO1_WR_NUM);
        SmartNcShortMsgSendEx(1, 0x0001, 0x0003, 4 /*demo 0x4xxx*/, tx, 16, 0);
        SmartNcWaitDone(1, 3000);
        dump("F-post");
        rd1 = FpgaRegRead(P_RD_FIFO1_WR_NUM);
        printf("  RD %u->%u SEL=%02X\n", (unsigned)rd0, (unsigned)rd1,
               (unsigned)(FpgaRegRead(P_FIFO_SELECT_REGISTER) & 0xFF));
    }

    /* Ctrl 冒烟确认链路 */
    printf("\n######## Ctrl smoke ########\n");
    K72Reset();
    JlkConfig(NODE_ID_DEFAULT, GLINK_ROLE_NC_NT);
    for (int i = 0; i < 30; i++) {
        if (GlinkGetLinkStatus(0) && GlinkGetLinkStatus(1)) break;
        usleep(100000);
    }
    printf("Ctrl role LINK A=%d B=%d\n", GlinkGetLinkStatus(0), GlinkGetLinkStatus(1));

    GlinkCloseAll();
    return 0;
}
