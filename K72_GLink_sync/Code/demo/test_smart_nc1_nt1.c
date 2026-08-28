/*============================================================================
 * SmartNC1 → SmartNT1 短报验证 (K72 单卡 A↔B 自环)
 *
 * 依据 (不以厂家 FMC 工程为准, 其管脚/桥接与 K72 不同):
 *   - 软件设计指南 V1.6 表54/60、§6.5.8
 *   - K72 RTL_EMIF_IF.v : P_FIFO_SELECT 复位 WR=NC1 RD=NT1 → 0xC8
 *   - 本工程 glink_regs / 原理图约定
 *
 * 配置要点:
 *   SEL=0xC8  WORK=SmartNC1|SmartNT1  NODE=0x8003  CHEN=CHANNEL_EN_AB
 *   SNC=0x0400(仅短报)  SNT=0x4000(短报无配对)  TO=0x8000
 *   帧: SA=1, CFG=1路NT+NT收+len, type=000 SmartNT1, ID=本节点
 *
 * 运行: ./test_smart_nc1_nt1 [/dev/xdma0_user]
 * 退出: 0=用法+环回OK  1=用法失败  2=用法OK环回失败
 *============================================================================*/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <stdint.h>

#include "glink_api.h"
#include "glink_regs.h"

#define LOCAL_NODE      NODE_ID_DEFAULT  /* 0x8003, ID=3 + 奇校验 */
#define LOCAL_NT_ID     0x0003
#define PAYLOAD_LEN     16
#define SEL_TARGET      0xC8u
#define SNC_SHORT       0x0400u          /* bit10 短报, 关堆栈 */
#define SNT_SHORT       0x4000u          /* bit14 短报, 无配对 */
#define SNC_TIMEOUT     0x8000u

static int g_usage_ok = 1;
static int g_func_ok  = 0;

static void check(const char *name, int ok)
{
    printf("  [%s] %s\n", ok ? "PASS" : "FAIL", name);
    if (!ok)
        g_usage_ok = 0;
}

static void dump_bytes(const char *tag, const uint8_t *p, int n)
{
    int i;
    printf("  %s", tag);
    for (i = 0; i < n; i++)
        printf("%02X ", p[i]);
    printf("(%dB)\n", n);
}

/* 手册 5.2.17 REG 0x2C: bit[15:8]=SMARTNC1_TRIG 外部触发计数 */
static uint16_t smartnc1_run_reg(void)
{
    return JlkRegRead(JLK_REG_SMARTNC1_RUN);
}

static void dump_ext_trig(const char *tag)
{
    uint16_t run = smartnc1_run_reg();
    printf("  [%s] REG0x2C=%04X  ext_trig_cnt=%u (bit[15:8])  "
           "biz_start_cnt=%u (bit[11:8])\n",
           tag, run, (unsigned)((run >> 8) & 0xFFu),
           (unsigned)((run >> 8) & 0x0Fu));
}

static void dump_regs(const char *tag)
{
    uint16_t st = JlkRegRead(JLK_REG_SMARTNC1_STATUS);
    printf("  [%s] MODE=%04X NODE=%04X CHEN=%04X SNC=%04X SNT=%04X TO=%04X "
           "ST=%04X fail=%u b14=%u b15=%u SEL=%02X WD1=%u RD1=%u "
           "LKA=%d LKB=%d PSTAT=%08X\n",
           tag,
           JlkRegRead(JLK_REG_WORK_MODE),
           JlkRegRead(JLK_REG_NODE_ID),
           JlkRegRead(JLK_REG_CHANNEL_EN),
           JlkRegRead(JLK_REG_SMARTNC1_CONFIG),
           JlkRegRead(JLK_REG_SMARTNT1_CONFIG),
           JlkRegRead(JLK_REG_SMARTNC1_TIMEOUT),
           st, (st >> 4) & 0xF, (st >> 14) & 1, (st >> 15) & 1,
           (unsigned)SmartFifoGetSelect(),
           (unsigned)FpgaRegRead(P_WD_FIFO1_WR_NUM),
           (unsigned)FpgaRegRead(P_RD_FIFO1_WR_NUM),
           GlinkGetLinkStatus(GLINK_CH_A),
           GlinkGetLinkStatus(GLINK_CH_B),
           FpgaRegRead(P_STATUS_REGISTER));
    dump_ext_trig(tag);
}

static int bringup(void)
{
    smartnc_config_t snc;
    smartnt_config_t snt;
    uint32_t sel;

    printf("\n======== A. 手册/RTL 配置 ========\n");

    if (K72Reset() != 0) {
        check("K72Reset", 0);
        return -1;
    }
    check("K72Reset", 1);

    /* 标准模式 + 2.5G (与 K72 常用 Ctrl 路径一致) */
    FpgaRegWrite(P_GC_MODE_REGISTER, 1);
    GlinkSetRate(GLINK_RATE_2G5);
    FpgaFifoReset();

    sel = SmartFifoGetSelect();
    SmartFifoDumpSelect("after-FifoReset");
    check("SmartFifoSetNcShort → 0xC8", SmartFifoSetNcShort(1) == 0);
    sel = SmartFifoGetSelect();
    SmartFifoDumpSelect("after-SetNcShort");
    check("SEL WR=NC1 RD=NT1",
          (sel & 0x0Fu) == 0x08u);

    JlkRegWrite(0x01, 0x0001);
    usleep(1000);
    JlkRegWrite(0x01, 0x0000);

    JlkRegWrite(JLK_REG_NODE_ID, LOCAL_NODE);
    JlkRegWrite(JLK_REG_CHANNEL_EN, CHANNEL_EN_AB);
    JlkRegWrite(JLK_REG_INT_MODE, 0x0002);
    JlkRegWrite(JLK_REG_TIMESTAMP, DEFAULT_TIMESTAMP);

    memset(&snc, 0, sizeof(snc));
    snc.timeout = SNC_TIMEOUT;
    snc.short_msg_mode = 1;
    snc.stack_en = 0; /* 短报关堆栈 (手册: 堆栈描述块主要用于大数据流) */
    check("SmartNcInit short", SmartNcInit(1, &snc) == 0);
    JlkRegWrite(JLK_REG_SMARTNC1_CONFIG, SNC_SHORT);
    SmartNcSetStackPtr(1, MEM_SMARTNC1_STACK_BASE);

    memset(&snt, 0, sizeof(snt));
    snt.short_msg_mode = 1;
    snt.pair_nc_id = 0; /* 短报无需配对 */
    snt.pair_nc_ch = 0;
    check("SmartNtInit short", SmartNtInit(1, &snt) == 0);
    JlkRegWrite(JLK_REG_SMARTNT1_CONFIG, SNT_SHORT);

    JlkRegWrite(JLK_REG_WORK_MODE, (uint16_t)(MODE_SMARTNC1 | MODE_SMARTNT1));

    check("NODE==0x8003", JlkRegRead(JLK_REG_NODE_ID) == LOCAL_NODE);
    check("CHEN==CHANNEL_EN_AB", JlkRegRead(JLK_REG_CHANNEL_EN) == CHANNEL_EN_AB);
    check("SNC==0x0400", JlkRegRead(JLK_REG_SMARTNC1_CONFIG) == SNC_SHORT);
    check("SNT==0x4000", JlkRegRead(JLK_REG_SMARTNT1_CONFIG) == SNT_SHORT);
    check("TO==0x8000", JlkRegRead(JLK_REG_SMARTNC1_TIMEOUT) == SNC_TIMEOUT);
    check("WORK==0x0110", JlkRegRead(JLK_REG_WORK_MODE) == 0x0110);
    check("SEL 保持 0xC8", SmartFifoGetSelect() == SEL_TARGET);

    printf("  等待 A/B LINK...\n");
    if (GlinkWaitLinkUp(GLINK_CH_A, 15000) != 0 ||
        GlinkWaitLinkUp(GLINK_CH_B, 5000) != 0 ||
        !GlinkGetLinkStatus(GLINK_CH_A) ||
        !GlinkGetLinkStatus(GLINK_CH_B)) {
        check("A/B LINK UP", 0);
        dump_regs("link-fail");
        return -1;
    }
    check("A/B LINK UP", 1);
    dump_regs("ready");
    return 0;
}

static int do_send(const uint8_t *tx)
{
    uint32_t wd0, rd0;
    uint16_t st;
    uint8_t trig_pre, trig_post_ctrl, trig_post_done;
    int wret;

    printf("\n======== B. 表54 短报发送 (API) ========\n");
    printf("  目标: NT_ID=0x%03X type=000(SmartNT1) len=%d\n",
           LOCAL_NT_ID, PAYLOAD_LEN);
    printf("  主机序: 写 P_FIFO1(0x1000) → P_NC1_SEND_NUM(0x0008) → "
           "P_CTRL bit0(0x0000)\n");
    printf("  (FPGA 对照: REG0x2C bit[15:8] 应在 SMARTNC1_TRIG 上升沿 +1)\n");

    JlkRegWrite(JLK_REG_SMARTNC1_STATUS, 0x1000);
    usleep(500);

    wd0 = FpgaRegRead(P_WD_FIFO1_WR_NUM);
    rd0 = FpgaRegRead(P_RD_FIFO1_WR_NUM);
    check("Send 前 SEL=0xC8", SmartFifoSetNcShort(1) == 0);

    trig_pre = (uint8_t)((smartnc1_run_reg() >> 8) & 0xFFu);
    dump_ext_trig("pre-send");

    if (SmartNcShortMsgSendEx(1, 0x0001, LOCAL_NT_ID, 0 /*SmartNT1*/,
                              tx, PAYLOAD_LEN, 0) != 0) {
        check("ShortMsgSendEx", 0);
        return -1;
    }
    check("ShortMsgSendEx", 1);

    usleep(1000); /* 留 1ms 给 FPGA FSM/TRIG 完成 */
    trig_post_ctrl = (uint8_t)((smartnc1_run_reg() >> 8) & 0xFFu);
    dump_ext_trig("post-CTRL(+1ms)");
    printf("  ext_trig: pre=%u post-CTRL=%u delta=%d\n",
           (unsigned)trig_pre, (unsigned)trig_post_ctrl,
           (int)trig_post_ctrl - (int)trig_pre);
    if (trig_post_ctrl == trig_pre)
        printf("  [WARN] 外部触发计数未增 → JLK 可能未见到 SMARTNC1_TRIG 上升沿\n");
    else
        printf("  [INFO] 外部触发计数已增 → TRIG 上升沿已被 JLK 计入\n");

    wret = SmartNcWaitDone(1, 3000);
    st = JlkRegRead(JLK_REG_SMARTNC1_STATUS);
    printf("  WaitDone=%d  ST=%04X fail=%u b14=%u b15=%u  WD %u→%u  RD %u→%u\n",
           wret, st, (st >> 4) & 0xF, (st >> 14) & 1, (st >> 15) & 1,
           (unsigned)wd0, (unsigned)FpgaRegRead(P_WD_FIFO1_WR_NUM),
           (unsigned)rd0, (unsigned)FpgaRegRead(P_RD_FIFO1_WR_NUM));
    trig_post_done = (uint8_t)((smartnc1_run_reg() >> 8) & 0xFFu);
    dump_ext_trig("post-WaitDone");
    printf("  ext_trig 汇总: pre=%u → post-CTRL=%u → post-Done=%u\n",
           (unsigned)trig_pre, (unsigned)trig_post_ctrl,
           (unsigned)trig_post_done);

    SmartFifoDumpSelect("post-send");
    dump_regs("post-send");
    check("TRIG 后 SEL 仍为 0xC8", SmartFifoGetSelect() == SEL_TARGET);
    return 0;
}

static int do_recv(const uint8_t *tx)
{
    uint8_t rx[64];
    uint16_t cmd = 0;
    uint32_t rd0, rd1;
    uint16_t st;
    int nrecv;
    int i;

    printf("\n======== C. 表60 短报接收 ========\n");
    rd0 = FpgaRegRead(P_RD_FIFO1_WR_NUM);
    check("轮询前 SEL=0xC8", SmartFifoSetNcShort(1) == 0);
    if (SmartNcWaitRdFifo(1, 2000) != 0)
        printf("  [INFO] RD/FC 超时未变\n");

    rd1 = FpgaRegRead(P_RD_FIFO1_WR_NUM);
    st = JlkRegRead(JLK_REG_SMARTNC1_STATUS);
    printf("  RD %u→%u  ST=%04X fail=%u\n",
           (unsigned)rd0, (unsigned)rd1, st, (st >> 4) & 0xF);

    if (rd1 == rd0) {
        printf("  [FUNC FAIL] 无 SmartNT 侧数据 (RD 不变)\n");
        if (st & 0x8000)
            printf("  [INFO] 仍交换组忙(bit15), 单次交换 bit14=%u\n",
                   (st >> 14) & 1);
        return -1;
    }

    memset(rx, 0, sizeof(rx));
    nrecv = SmartNtShortMsgRecv(1, rx, sizeof(rx), &cmd);
    SmartFifoSetNcShort(1); /* Recv 内会改 SEL, 恢复手册短报 SEL */
    printf("  ShortMsgRecv ret=%d cmd=0x%04X\n", nrecv, cmd);
    if (nrecv > 0)
        dump_bytes("RX: ", rx, nrecv > 32 ? 32 : nrecv);

    if (nrecv < PAYLOAD_LEN) {
        printf("  [FUNC FAIL] 长度不足\n");
        return -1;
    }
    for (i = 0; i < PAYLOAD_LEN; i++) {
        if (rx[i] != tx[i]) {
            printf("  [FUNC FAIL] 数据不一致 @%d\n", i);
            return -1;
        }
    }
    printf("  [FUNC PASS] 载荷一致\n");
    return 0;
}

int main(int argc, char **argv)
{
    const char *dev = "/dev/xdma0_user";
    uint8_t tx[PAYLOAD_LEN];
    int i;

    if (argc >= 2)
        dev = argv[1];

    printf("============================================================\n");
    printf(" SmartNC1 → SmartNT1 短报 (手册 + K72 RTL)\n");
    printf(" 设备: %s\n", dev);
    printf(" SEL=C8 SNC=0400 SNT=4000 NODE=8003 WORK=0110\n");
    printf("============================================================\n");

    if (GlinkOpenPath(0, dev) != 0) {
        printf("[FATAL] 打开设备失败\n");
        return 1;
    }

    for (i = 0; i < PAYLOAD_LEN; i++)
        tx[i] = (uint8_t)(0xA0 + i);
    dump_bytes("TX: ", tx, PAYLOAD_LEN);

    if (bringup() != 0) {
        GlinkCloseAll();
        return 1;
    }
    if (do_send(tx) != 0) {
        JlkConfig(NODE_ID_DEFAULT, GLINK_ROLE_NC_NT);
        GlinkCloseAll();
        return 1;
    }
    g_func_ok = (do_recv(tx) == 0);

    JlkRegWrite(JLK_REG_SMARTNC1_STATUS, 0x1000);
    JlkConfig(NODE_ID_DEFAULT, GLINK_ROLE_NC_NT);

    printf("\n============================================================\n");
    printf(" 软件用法(手册/RTL): %s\n", g_usage_ok ? "PASS" : "FAIL");
    printf(" 环回功能:           %s\n", g_func_ok ? "PASS" : "FAIL");
    printf("============================================================\n");

    GlinkCloseAll();
    if (!g_usage_ok)
        return 1;
    if (!g_func_ok)
        return 2;
    return 0;
}
