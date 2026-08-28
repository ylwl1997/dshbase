/*============================================================================
 * Smart 卡 busy (STATUS=0x8000) 诊断
 *
 * 现象: TRIG 后 ST=0x8000 (bit15 交换组忙), fail_cnt=0, RD 不变, WaitDone 超时
 * 目的: 区分
 *   A) FPGA 未把 WD 灌进 JLK (WD 计数不降 / 一直 AFULL)
 *   B) JLK 已启动但等响应/超时不触发 (busy 久驻, 最终 fail++)
 *   C) STACK_EN(0x0440) 导致交换组挂起 (对比 0x0400)
 *
 * 运行: ./test_smart_busy_diag
 *============================================================================*/

#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <stdint.h>
#include "glink_api.h"
#include "glink_regs.h"

static void dump_line(const char *tag)
{
    uint16_t st = JlkRegRead(JLK_REG_SMARTNC1_STATUS);
    printf("  %-18s ST=%04X fail=%u b14=%u b15=%u blkAB=%u ovf=%u sus=%u "
           "WD1=%u RD1=%u RC1=%u SEL=%02X PSTAT=%08X DBG=%08X\n",
           tag, st, (st >> 4) & 0xF, (st >> 14) & 1, (st >> 15) & 1,
           (st >> 8) & 7, (st >> 11) & 1, (st >> 12) & 1,
           (unsigned)FpgaRegRead(P_WD_FIFO1_WR_NUM),
           (unsigned)FpgaRegRead(P_RD_FIFO1_WR_NUM),
           (unsigned)FpgaRegRead(P_RC_FIFO1_WR_NUM),
           (unsigned)SmartFifoGetSelect(),
           FpgaRegRead(P_STATUS_REGISTER),
           FpgaGetDebug());
}

static void vendor_base_init(uint16_t snc_cfg)
{
    K72Reset();
    FpgaRegWrite(P_GC_MODE_REGISTER, 1);
    GlinkSetRate(GLINK_RATE_2G5);
    FpgaFifoReset();
    SmartFifoSetNcShort(1);

    JlkRegWrite(0x01, 0x0001);
    usleep(1000);
    JlkRegWrite(0x01, 0x0000);

    JlkRegWrite(JLK_REG_NODE_ID, 0x0001);
    JlkRegWrite(JLK_REG_CHANNEL_EN, 0x00C3);
    JlkRegWrite(JLK_REG_SMARTNC1_TIMEOUT, 0x3000);
    JlkRegWrite(JLK_REG_TIMESTAMP, 0x0005);
    JlkRegWrite(JLK_REG_INT_MODE, 0x0002);
    JlkRegWrite(JLK_REG_SMARTNC1_CONFIG, snc_cfg);
    JlkMemWrite(MEM_SMARTNC1_SP, MEM_SMARTNC1_STACK_BASE);
    JlkRegWrite(JLK_REG_SMARTNT1_CONFIG, 0x4003);
    JlkRegWrite(JLK_REG_WORK_MODE, 0x0110);

    printf("  init SNC=0x%04X NODE=%04X CHEN=%04X TO=%04X SNT=%04X WORK=%04X\n",
           JlkRegRead(JLK_REG_SMARTNC1_CONFIG),
           JlkRegRead(JLK_REG_NODE_ID),
           JlkRegRead(JLK_REG_CHANNEL_EN),
           JlkRegRead(JLK_REG_SMARTNC1_TIMEOUT),
           JlkRegRead(JLK_REG_SMARTNT1_CONFIG),
           JlkRegRead(JLK_REG_WORK_MODE));
}

static int wait_link(void)
{
    if (GlinkWaitLinkUp(GLINK_CH_A, 15000) != 0 ||
        GlinkWaitLinkUp(GLINK_CH_B, 5000) != 0)
        return -1;
    return (GlinkGetLinkStatus(GLINK_CH_A) && GlinkGetLinkStatus(GLINK_CH_B))
           ? 0 : -1;
}

static void send_frame(const uint16_t *w, int n)
{
    int i;
    SmartFifoSetNcShort(1);
    printf("  TX words:");
    for (i = 0; i < n; i++)
        printf(" %04X", w[i]);
    printf(" (N=%d)\n", n);
    for (i = 0; i < n; i++)
        FpgaRegWrite(P_FIFO1_WRITE_REGISTER, w[i]);
    FpgaRegWrite(P_NC1_SEND_NUM, (uint32_t)n);
    FpgaRegWrite(P_CTRL_REGISTER, CTRL_NC1_TX);
}

static void poll_busy(int ms_total, int step_ms)
{
    int t;
    for (t = 0; t <= ms_total; t += step_ms) {
        char tag[32];
        snprintf(tag, sizeof(tag), "t=%4dms", t);
        dump_line(tag);
        if (t == 0)
            usleep((useconds_t)step_ms * 1000);
        else if (t < ms_total)
            usleep((useconds_t)step_ms * 1000);
        {
            uint16_t st = JlkRegRead(JLK_REG_SMARTNC1_STATUS);
            /* 已空闲且有 fail 或已空闲 → 提前结束长轮询中的成功/失败收敛 */
            if (t >= 500 && !(st & 0xC000))
                break;
        }
    }
}

static void case_run(const char *name, uint16_t snc_cfg,
                     const uint16_t *frame, int nwords)
{
    printf("\n######## %s ########\n", name);
    vendor_base_init(snc_cfg);
    if (wait_link() != 0) {
        printf("  [FAIL] LINK\n");
        return;
    }
    dump_line("pre-send");
    JlkRegWrite(JLK_REG_SMARTNC1_STATUS, 0x1000);
    usleep(500);

    send_frame(frame, nwords);
    poll_busy(5000, 250);

    dump_line("end");
    JlkRegWrite(JLK_REG_SMARTNC1_STATUS, 0x1000);
    JlkRegWrite(JLK_REG_WORK_MODE, 0);
    usleep(1000);
}

int main(void)
{
    /* 对齐帧 len=2 */
    const uint16_t f_ok[] = { 0x0001, 0x1002, 0x0001, 0x5555 };
    /* 厂家原帧 len=0→512 (易挂) */
    const uint16_t f_512[] = { 0x0001, 0x1000, 0x0001, 0x5555 };
    /* 短超时 + 无堆栈 */
    const uint16_t f_ok2[] = { 0x0001, 0x1002, 0x0001, 0x5555 };

    if (GlinkOpenPath(0, "/dev/xdma0_user") != 0)
        return 1;

    printf("============================================================\n");
    printf(" Smart busy-hang 诊断 (STATUS bit15=交换组忙 / bit14=单次交换忙)\n");
    printf("============================================================\n");

    /* C1: 厂家 SNC=0440 + 正确 len=2 */
    case_run("C1 SNC=0440 stack+short, frame 1002", 0x0440, f_ok, 4);

    /* C2: 无堆栈 0400 + 正确 len=2 */
    case_run("C2 SNC=0400 short-only, frame 1002", 0x0400, f_ok, 4);

    /* C3: 厂家 0440 + 错误 len=512 只写1字载荷 */
    case_run("C3 SNC=0440, frame 1000(512) starved", 0x0440, f_512, 4);

    /* C4: 无堆栈 + 极短超时, 看会否变成 fail_cnt */
    printf("\n######## C4 SNC=0400 TO=0x0100 frame 1002 ########\n");
    vendor_base_init(0x0400);
    JlkRegWrite(JLK_REG_SMARTNC1_TIMEOUT, 0x0100);
    if (wait_link() == 0) {
        dump_line("pre-send");
        JlkRegWrite(JLK_REG_SMARTNC1_STATUS, 0x1000);
        send_frame(f_ok2, 4);
        poll_busy(5000, 250);
        dump_line("end");
    }
    JlkConfig(NODE_ID_DEFAULT, GLINK_ROLE_NC_NT);
    GlinkCloseAll();
    return 0;
}
