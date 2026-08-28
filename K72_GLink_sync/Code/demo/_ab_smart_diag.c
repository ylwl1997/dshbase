#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>
#include <stdlib.h>
#include "../api/glink_api.h"
#include "../api/glink_regs.h"

static void dump(const char *tag)
{
    uint16_t st = JlkRegRead(JLK_REG_SMARTNC1_STATUS);
    printf("[%s] NODE=%04X MODE=%04X CHEN=%04X "
           "SNC=%04X SNT=%04X ST=%04X(fail=%u busy14=%u busy15=%u) SP=%04X "
           "FC61=%04X FC62=%04X SEL=%02X WD=%u RD=%u RC=%u "
           "LKA=%d LKB=%d DBG=%08X\n",
           tag,
           JlkRegRead(JLK_REG_NODE_ID),
           JlkRegRead(JLK_REG_WORK_MODE),
           JlkRegRead(JLK_REG_CHANNEL_EN),
           JlkRegRead(JLK_REG_SMARTNC1_CONFIG),
           JlkRegRead(JLK_REG_SMARTNT1_CONFIG),
           st, (st >> 4) & 0xF, (st >> 14) & 1, (st >> 15) & 1,
           SmartNcGetCurrentSp(1),
           JlkRegRead(0x61), JlkRegRead(0x62),
           (unsigned)(FpgaRegRead(P_FIFO_SELECT_REGISTER) & 0xFF),
           (unsigned)FpgaRegRead(P_WD_FIFO1_WR_NUM),
           (unsigned)FpgaRegRead(P_RD_FIFO1_WR_NUM),
           (unsigned)FpgaRegRead(P_RC_FIFO1_WR_NUM),
           GlinkGetLinkStatus(0), GlinkGetLinkStatus(1),
           FpgaGetDebug());
}

static void dump_desc(uint16_t base)
{
    printf("  MEM@%04X:", base);
    for (int i = 0; i < 16; i++)
        printf(" %04X", JlkMemRead(base + i));
    printf("\n");
}

/* variant:
 *  0 = 旧路径: ShortMsgSend默认NT=0x06, single_ch=1, ConfigChannel(ch=1)
 *  1 = 修ID: NT=0x03, pair_ch=0, single_ch=1
 *  2 = 修ID+双通道: single_ch=0 (AB回环关键)
 *  3 = 同2 + stack_en=0
 *  4 = 同2 + 目标类型 CtrlNT(4) 对照
 */
static int run_variant(int variant)
{
    uint8_t tx[16], rx[128];
    smartnc_config_t snc;
    smartnt_config_t snt;
    uint16_t cmd = 0, raw;
    int i, n, wait_rc;
    uint32_t rd0, rd1;
    uint16_t nt_id = (variant == 0) ? 0x0006 : 0x0003;
    uint8_t nt_type = (variant == 4) ? 4 : 0;

    printf("\n############ VARIANT %d "
           "(nt_id=0x%02X type=%u single_ch=%d) ############\n",
           variant, nt_id, nt_type, variant < 2);

    if (K72Reset() != 0)
        return -1;
    FpgaRegWrite(P_GC_MODE_REGISTER, 1);
    GlinkSetRate(GLINK_RATE_2G5);
    FpgaFifoReset();
    JlkRegWrite(JLK_REG_NODE_ID, NODE_ID_DEFAULT);
    JlkRegWrite(JLK_REG_CHANNEL_EN, CHANNEL_EN_AB);
    JlkRegWrite(JLK_REG_INT_MODE, 0x0002);
    JlkRegWrite(JLK_REG_TIMESTAMP, 0xFFFF);
    JlkRegWrite(JLK_REG_WORK_MODE, (uint16_t)(MODE_SMARTNC1 | MODE_SMARTNT1));
    MemorySpaceInit();

    for (i = 0; i < 50; i++) {
        if (GlinkGetLinkStatus(0) && GlinkGetLinkStatus(1))
            break;
        usleep(100000);
    }
    printf("LINK A=%d B=%d\n", GlinkGetLinkStatus(0), GlinkGetLinkStatus(1));
    if (!GlinkGetLinkStatus(0) || !GlinkGetLinkStatus(1)) {
        printf("AB not both up, abort variant\n");
        return -1;
    }

    memset(&snt, 0, sizeof(snt));
    snt.pair_nc_id = 0x03;
    snt.pair_nc_ch = 0;
    snt.short_msg_mode = 1;
    SmartNtInit(1, &snt);
    if (variant == 0)
        SmartNtConfigChannel(1, 0x03, 1, 1); /* 旧测试: pair ch=1 */
    else
        SmartNtConfigChannel(1, 0x03, 0, 1); /* pair SmartNC1 */

    memset(&snc, 0, sizeof(snc));
    snc.timeout = 0xFFFF;
    snc.payload_size = 3;
    snc.stack_en = (variant == 3) ? 0 : 1;
    snc.short_msg_mode = 1;
    snc.single_channel = (variant < 2) ? 1 : 0;
    snc.use_ch_b = 0;
    SmartNcInit(1, &snc);
    SmartNcSetStackPtr(1, MEM_SMARTNC1_STACK_BASE);

    dump("pre");
    for (i = 0; i < 16; i++)
        tx[i] = (uint8_t)(0xA0 + i);
    memset(rx, 0, sizeof(rx));

    rd0 = FpgaRegRead(P_RD_FIFO1_WR_NUM);
    printf("SEND nt_id=0x%02X...\n", nt_id);
    if (variant == 0) {
        if (SmartNcShortMsgSend(1, tx, 16) != 0) {
            printf("send fail\n");
            return -1;
        }
    } else {
        if (SmartNcShortMsgSendEx(1, 0x0001, nt_id, nt_type, tx, 16, 1) != 0) {
            printf("sendex fail\n");
            return -1;
        }
    }
    usleep(20000);
    dump("post-send-20ms");
    SmartNcWaitDone(1, 3000);
    raw = JlkRegRead(JLK_REG_SMARTNC1_STATUS);
    printf("WaitDone done, STATUS=0x%04X\n", raw);
    dump("post-wait");
    dump_desc(MEM_SMARTNC1_STACK_BASE);

    wait_rc = SmartNtWaitRecv(1, 1500);
    rd1 = FpgaRegRead(P_RD_FIFO1_WR_NUM);
    printf("WaitRecv=%d  RD delta %u -> %u\n", wait_rc, (unsigned)rd0, (unsigned)rd1);
    dump("post-waitrecv");

    /* 仅当 RD 计数变化才认为有数据, 否则强制不读避免假数据 */
    if (rd1 != rd0) {
        n = SmartNtShortMsgRecv(1, rx, sizeof(rx), &cmd);
        printf("RECV n=%d cmd=%04X |", n, cmd);
        for (i = 0; i < (n > 24 ? 24 : n); i++)
            printf(" %02X", rx[i]);
        printf("\n");
        if (n >= 16 && memcmp(tx, rx, 16) == 0)
            printf("*** DATA MATCH PASS ***\n");
        else
            printf("*** DATA MISMATCH ***\n");
    } else {
        printf("RECV skipped: RD_FIFO count unchanged (no real RX). "
               "If ShortMsgRecv forced: would fake-read SEL-like garbage.\n");
        /* still show what forced read would get */
        n = SmartNtShortMsgRecv(1, rx, sizeof(rx), &cmd);
        printf("forced-read n=%d cmd=%04X first=%02X%02X (likely garbage)\n",
               n, cmd, rx[0], rx[1]);
    }

    /* clear hang */
    JlkRegWrite(JLK_REG_SMARTNC1_STATUS, 0x1000);
    return 0;
}

int main(void)
{
    if (GlinkOpenPath(0, "/dev/xdma0_user") != 0) {
        printf("open fail\n");
        return 1;
    }
    printf("=== AB Smart diagnose on /dev/xdma0_user ===\n");
    for (int v = 0; v <= 3; v++)
        run_variant(v);
    GlinkCloseAll();
    return 0;
}
