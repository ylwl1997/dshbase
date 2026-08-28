/*============================================================
 * K72 GLink API 实现 (L1 封装层)
 *
 * 架构:
 *   L0 设备层: /dev/xdma0_user 或 sysfs resource0
 *   L1 封装层: 本文件 (Xdma* -> Emif* -> Fpga/Jlk)
 *   L2 测试层: test_glink_api.c
 *
 * 数据流:
 *   GlinkOpen -> mmap XDMA BAR
 *   XdmaWrite(EF_AR_ADDR, addr) -> XdmaWrite(EF_WR_ADDR, data)
 *       -> XdmaWrite(EF_ST_ADDR, EF_WR_EN) -> 写入完成
 *   XdmaWrite(EF_AR_ADDR, addr) -> XdmaWrite(EF_ST_ADDR, EF_RD_EN)
 *       -> 轮询 EF_ST_RX_EMPTY -> XdmaWrite(EF_ST_ADDR, EF_FIFO_RD_EN)
 *       -> XdmaRead(EF_RD_ADDR, &data) -> 读出数据
 *============================================================*/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <errno.h>
#include <time.h>

#include "glink_api.h"
#include "glink_regs.h"

#ifndef GLINK_MAX_DEV
#define GLINK_MAX_DEV 4
#endif

/*----------------- 全局变量 (多卡上下文) ---------------------------*/
typedef struct {
    volatile uint32_t *base;
    int fd;
    int initialized;
    uint8_t current_ce;
    char path[128];
} glink_dev_t;

static glink_dev_t g_devs[GLINK_MAX_DEV];
static glink_dev_t *g = &g_devs[0];
static int g_cur_idx = 0;

/*----------------- 微秒延时 -----------------------------------------*/
static void delay_us(int us) {
    struct timespec ts;
    ts.tv_sec  = us / 1000000;
    ts.tv_nsec = (us % 1000000) * 1000;
    nanosleep(&ts, NULL);
}

/*----------------- L0: 设备开关 ------------------------------------*/
int GlinkBind(int idx) {
    if (idx < 0 || idx >= GLINK_MAX_DEV || !g_devs[idx].initialized)
        return -1;
    g = &g_devs[idx];
    g_cur_idx = idx;
    return 0;
}

int GlinkCurrent(void) {
    return (g && g->initialized) ? g_cur_idx : -1;
}

int GlinkOpenPath(int idx, const char *path) {
    glink_dev_t *d;
    if (idx < 0 || idx >= GLINK_MAX_DEV || !path || !path[0])
        return -1;
    d = &g_devs[idx];
    if (d->initialized) {
        g = d;
        g_cur_idx = idx;
        return 0;
    }

    d->fd = open(path, O_RDWR | O_SYNC);
    if (d->fd < 0) {
        perror("[错误] 无法打开设备");
        printf("  path=%s\n", path);
        return -1;
    }

    d->base = mmap(NULL, XDMA_MAP_SIZE, PROT_READ | PROT_WRITE,
                   MAP_SHARED, d->fd, 0);
    if (d->base == MAP_FAILED) {
        perror("[错误] mmap 映射失败");
        close(d->fd);
        d->fd = -1;
        d->base = NULL;
        return -1;
    }

    d->base[EF_BRIDGE_RST / 4] = BRIDGE_RST_RELEASE;
    delay_us(1000);

    strncpy(d->path, path, sizeof(d->path) - 1);
    d->path[sizeof(d->path) - 1] = '\0';
    d->initialized = 1;
    d->current_ce = 0xFF;
    g = d;
    g_cur_idx = idx;
    printf("[驱动] 设备[%d] 打开成功 path=%s fd=%d\n", idx, path, d->fd);
    return 0;
}

int GlinkOpen(void) {
    if (g_devs[0].initialized) {
        g = &g_devs[0];
        g_cur_idx = 0;
        return 0;
    }

    if (GlinkOpenPath(0, XDMA_USER_DEV) == 0)
        return 0;

    printf("[驱动] %s 不可用, 尝试 sysfs...\n", XDMA_USER_DEV);
    if (GlinkOpenPath(0, XDMA_SYSFS_DEV) == 0)
        return 0;

    fprintf(stderr, "[错误] 无法打开 XDMA/sysfs 设备\n");
    return -1;
}

void GlinkClose(void) {
    if (!g || !g->initialized)
        return;
    if (g->base && g->base != MAP_FAILED) {
        munmap((void *)g->base, XDMA_MAP_SIZE);
        g->base = NULL;
    }
    if (g->fd >= 0) {
        close(g->fd);
        g->fd = -1;
    }
    g->initialized = 0;
    g->current_ce = 0xFF;
    g->path[0] = '\0';
}

void GlinkCloseAll(void) {
    int i;
    for (i = 0; i < GLINK_MAX_DEV; i++) {
        if (!g_devs[i].initialized)
            continue;
        g = &g_devs[i];
        g_cur_idx = i;
        GlinkClose();
    }
    g = &g_devs[0];
    g_cur_idx = 0;
}

/*----------------- L0: XDMA 寄存器直接读写 -------------------------*/
int XdmaWrite(uint32_t addr, uint32_t val) {
    if (!g || !g->base) {
        fprintf(stderr, "XdmaWrite: 设备未打开\n");
        return -1;
    }
    g->base[addr / 4] = val;
    return 0;
}

int XdmaRead(uint32_t addr, uint32_t *val) {
    if (!g || !g->base) {
        fprintf(stderr, "XdmaRead: 设备未打开\n");
        return -1;
    }
    *val = g->base[addr / 4];
    return 0;
}

/*----------------- L1: BRIDGE 控制 ---------------------------------*/
int BridgeRelease(void) {
    return XdmaWrite(EF_BRIDGE_RST, BRIDGE_RST_RELEASE);
}

int BridgeReset(void) {
    int ret = XdmaWrite(EF_BRIDGE_RST, BRIDGE_RST_PULL);
    delay_us(10000);
    return ret;
}

/*----------------- L1: EMIF 片选切换 --------------------------------*/
int EmifSetCeN(uint8_t ce_n) {
    if (ce_n == g->current_ce) return 0;
    /* BIT3=1 才能写 BIT4-7: 即 (1<<3) | (ce_n << 4) */
    uint32_t val = EF_CE_N_WE | ((ce_n & 0xF) << 4);
    XdmaWrite(EF_ST_ADDR, val);
    delay_us(100);
    g->current_ce = ce_n;
    return 0;
}

int EmifSelectFpga(void) {
    return EmifSetCeN(CE_N_FPGA);
}

int EmifSelectJlk(void) {
    return EmifSetCeN(CE_N_JLK1263);
}

/*----------------- L1: EMIF 间接读写 (核心) ------------------------*/
int EmifWrite(uint32_t emif_addr, uint32_t wdata) {
    uint32_t st = 0;
    /* 1. 写入 19位 EMIF 地址 */
    XdmaWrite(EF_AR_ADDR, emif_addr & 0x7FFFF);
    /* 2. 写入数据 */
    XdmaWrite(EF_WR_ADDR, wdata);
    /* 3. 触发写: BIT0=1 */
    XdmaWrite(EF_ST_ADDR, EF_WR_EN | (g->current_ce << 4) | EF_CE_N_WE);
    /* 4. 等待写完成 (WR_EMPTY=1) */
    int retry = 100;
    while (retry-- > 0) {
        XdmaRead(EF_ST_ADDR, &st);
        if (st & EF_ST_WR_EMPTY) break;
        delay_us(10);
    }
    return 0;
}

int EmifRead(uint32_t emif_addr, uint32_t *rddata) {
    uint32_t st = 0;
    /* 1. 写入地址 */
    XdmaWrite(EF_AR_ADDR, emif_addr & 0x7FFFF);
    /* 2. 触发读: BIT1=1 */
    XdmaWrite(EF_ST_ADDR, EF_RD_EN | (g->current_ce << 4) | EF_CE_N_WE);
    /* 3. 等待 RX FIFO 非空 */
    int retry = 200;
    while (retry-- > 0) {
        XdmaRead(EF_ST_ADDR, &st);
        if (!(st & EF_ST_RX_EMPTY)) break;
        delay_us(10);
    }
    if (retry <= 0) {
        *rddata = 0xDEADBEEF;
        return -1;
    }
    /* 4. 读 FIFO: BIT8=1 */
    XdmaWrite(EF_ST_ADDR, EF_FIFO_RD_EN | (g->current_ce << 4) | EF_CE_N_WE);
    delay_us(50);
    /* 5. 读出数据 */
    XdmaRead(EF_RD_ADDR, rddata);
    return 0;
}

/*----------------- L1: FPGA 寄存器读写 (CE_N=0x7) ------------------*/
int FpgaRegWrite(uint32_t reg, uint32_t val) {
    EmifSelectFpga();
    return EmifWrite(REG_ADDR(reg), val);
}

uint32_t FpgaRegRead(uint32_t reg) {
    uint32_t val = 0;
    EmifSelectFpga();
    EmifRead(REG_ADDR(reg), &val);
    return val;
}

/*----------------- L1: JLK1263 REG 读写 (CE_N=0xB, bit18=0) ---------*/
int JlkRegWrite(uint32_t reg, uint16_t val) {
    EmifSelectJlk();
    return EmifWrite(REG_ADDR(reg), (uint32_t)val);
}

uint16_t JlkRegRead(uint32_t reg) {
    uint32_t val = 0;
    EmifSelectJlk();
    EmifRead(REG_ADDR(reg), &val);
    return (uint16_t)(val & 0xFFFF);
}

/*----------------- L1: JLK1263 MEM 读写 (CE_N=0xB, bit18=1) --------*/
int JlkMemWrite(uint32_t mem_off, uint16_t val) {
    EmifSelectJlk();
    return EmifWrite(MEM_ADDR(mem_off), (uint32_t)val);
}

uint16_t JlkMemRead(uint32_t mem_off) {
    uint32_t val = 0;
    EmifSelectJlk();
    EmifRead(MEM_ADDR(mem_off), &val);
    return (uint16_t)(val & 0xFFFF);
}

/*----------------- L2: 高级配置接口 --------------------------------*/
int K72Reset(void) {
    /* FIFO 复位 */
    FpgaRegWrite(P_FIFO_RESET_REGISTER, 0x1);
    delay_us(1000);
    FpgaRegWrite(P_FIFO_RESET_REGISTER, 0x0);
    /* JLK1263 复位 */
    FpgaRegWrite(P_JLK_RESET_REGISTER, 0x0);
    delay_us(10000);
    FpgaRegWrite(P_JLK_RESET_REGISTER, 0x1);
    delay_us(500000);  /* JLK1263 需要较长复位恢复时间 */
    printf("[复位] K72 (FPGA+JLK+FIFO) 完成\n");
    return 0;
}

int JlkConfig(uint16_t node_id, glink_role_t role) {
    uint16_t work_mode;
    uint16_t int_mask;
    switch (role) {
        case GLINK_ROLE_NC:    work_mode = MODE_CTRLNC1; int_mask = 0x0004; break;
        case GLINK_ROLE_NT:    work_mode = MODE_CTRLNT;  int_mask = 0x0800; break;
        /* NC+NT 自环: 同时使能 ctrlNC1 结束中断(bit2) + ctrlNT 接收中断(bit11) */
        case GLINK_ROLE_NC_NT: work_mode = MODE_CTRLNC1 | MODE_CTRLNT; int_mask = 0x0804; break;
        default: return -1;
    }

    JlkRegWrite(JLK_REG_NODE_ID,    node_id);
    JlkRegWrite(JLK_REG_CHANNEL_EN, CHANNEL_EN_AB);
    JlkRegWrite(JLK_REG_INT_MODE,   0x0002);
    JlkRegWrite(JLK_REG_INT_MASK,   int_mask);
    JlkRegWrite(JLK_REG_TIMESTAMP,  DEFAULT_TIMESTAMP);
    JlkRegWrite(JLK_REG_CTRLNC1_RETRY, DEFAULT_CTRLNC1_RETRY);
    JlkRegWrite(JLK_REG_WORK_MODE,  work_mode);

    /* ctrlNT 模式需要配置 REG(0x24)/REG(0x25) (来自 CtrlNT.c demo) */
    if (role == GLINK_ROLE_NT || role == GLINK_ROLE_NC_NT) {
        JlkRegWrite(0x24, 0xA0);
        JlkRegWrite(0x25, 0x1C);
    }

    printf("[配置] JLK1263 ID=0x%04X, mode=0x%04X, int_mask=0x%04X\n",
           node_id, work_mode, int_mask);
    return 0;
}

int MemorySpaceInit(void) {
    for (int i = 0; i < 256; i++) {
        JlkMemWrite(i, 0xFFFF);
    }
    return 0;
}

int NcMemoryMapInit(uint16_t stack_addr, uint16_t mem_addr) {
    JlkMemWrite(MEM_NC1_EXCH_COUNT, 0x0001);
    JlkMemWrite(MEM_NC1_ID,         0x0001);
    JlkMemWrite(MEM_NC1_STACK_L,    stack_addr);
    JlkMemWrite(MEM_NC1_MEM_L,      mem_addr);
    JlkMemWrite(MEM_NC1_STACK_H,    0x0000);
    JlkMemWrite(MEM_NC1_MEM_H,      0x0000);
    return 0;
}

int NtChannelMap(int ch, uint16_t nc_id) {
    if (ch < 0 || ch > 3) return -1;
    JlkMemWrite(MEM_NT_CH1 + ch, nc_id | 0x8000);
    return 0;
}

int GlinkGetLinkStatus(glink_channel_t ch) {
    uint32_t reg;
    switch (ch) {
        case GLINK_CH_A: reg = JLK_REG_CH_A_STATUS; break;
        case GLINK_CH_B: reg = JLK_REG_CH_B_STATUS; break;
        case GLINK_CH_C: reg = JLK_REG_CH_C_STATUS; break;
        case GLINK_CH_D: reg = JLK_REG_CH_D_STATUS; break;
        default: return 0;
    }
    uint16_t val = JlkRegRead(reg);
    return ((val & (LINK_ACTIVE | LINK_UP)) == (LINK_ACTIVE | LINK_UP)) ? 1 : 0;
}

int GlinkWaitLinkUp(glink_channel_t ch, int timeout_ms) {
    int retry = timeout_ms / 100;
    while (retry-- > 0) {
        if (GlinkGetLinkStatus(ch)) return 0;
        delay_us(100000);
    }
    return -1;
}

/*----------------- L2: 数据传输接口 --------------------------------*/
int FpgaFifoWrite(int ch, const uint16_t *data, int count) {
    uint32_t fifo_wr_reg   = (ch == 0) ? P_FIFO1_WRITE_REGISTER : P_FIFO2_WRITE_REGISTER;
    uint32_t fifo_send_reg = (ch == 0) ? P_FIFO1_SEND_RAM_WRITE : P_FIFO2_SEND_RAM_WRITE;

    /* 写数据到 FIFO */
    for (int i = 0; i < count; i++) {
        FpgaRegWrite(fifo_wr_reg, data[i]);
    }
    /* 触发发送 RAM 写 */
    FpgaRegWrite(fifo_send_reg, 0x1);
    return count;
}

int NcTriggerSend(int ch, uint32_t send_num) {
    if (ch < 1 || ch > 4) return -1;
    /* 设置发送数量 */
    uint32_t num_reg = P_NC1_SEND_NUM + (ch - 1) * 4;
    FpgaRegWrite(num_reg, send_num);
    /* 触发对应 NC 发送 */
    uint32_t trig_bit = 1 << (ch - 1);
    FpgaRegWrite(P_CTRL_REGISTER, trig_bit);
    return 0;
}

int NcWaitDone(int ch, int timeout_ms) {
    if (ch < 1 || ch > 4) return -1;
    uint32_t done_bit = 1 << (ch - 1);
    int retry = timeout_ms / 10;
    while (retry-- > 0) {
        uint32_t status = FpgaRegRead(P_STATUS_REGISTER);
        if (status & done_bit) {
            /* 清除完成标志 */
            FpgaRegWrite(P_STATUS_REGISTER, done_bit);
            return 0;
        }
        delay_us(10000);
    }
    return -1;
}

uint32_t RxFifoGetCount(int ch) {
    /* RC: 数据由JLK1263收到后写入 RC_FIFO, 然后搬到 RD_FIFO */
    uint32_t rc_reg = (ch == 0) ? P_RC_FIFO1_WR_NUM : P_RC_FIFO2_WR_NUM;
    uint32_t rd_reg = (ch == 0) ? P_RD_FIFO1_WR_NUM : P_RD_FIFO2_WR_NUM;
    uint32_t rc_num = FpgaRegRead(rc_reg);
    uint32_t rd_num = FpgaRegRead(rd_reg);
    return (rd_num > 0) ? rd_num : rc_num;
}

int RxFifoRead(int ch, uint16_t *buf, int count) {
    int read_count = 0;
    for (int i = 0; i < count; i++) {
        uint32_t val = FpgaRegRead(P_DATA_READ_REGISTER);
        if (val == 0 && i > 0) break;  /* FIFO 空 */
        buf[i] = (uint16_t)(val & 0xFFFF);
        read_count++;
    }
    return read_count;
}

/*----------------- L2: 调试与诊断 ----------------------------------*/
uint32_t FpgaGetDebug(void) {
    return FpgaRegRead(P_DEBUG_REGISTER);
}

void JlkDumpAll(void) {
    printf("  JLK1263 寄存器:\n");
    for (int i = 0; i < 16; i++) {
        uint16_t val = JlkRegRead(i);
        const char *name = "";
        switch (i) {
            case 0x00: name = "节点ID"; break;
            case 0x02: name = "工作模式"; break;
            case 0x03: name = "通道使能"; break;
            case 0x07: name = "时间戳"; break;
            case 0x08: name = "产品ID(只读)"; break;
            case 0x09: name = "版本(只读)"; break;
            case 0x0A: name = "A通道状态"; break;
            case 0x0B: name = "B通道状态"; break;
            case 0x0C: name = "C通道状态"; break;
            case 0x0D: name = "D通道状态"; break;
            default: name = ""; break;
        }
        printf("    REG(0x%02X) = 0x%04X  %s\n", i, val, name);
    }
}

void FpgaDumpStatus(void) {
    uint32_t status = FpgaRegRead(P_STATUS_REGISTER);
    uint32_t dbg = FpgaRegRead(P_DEBUG_REGISTER);
    uint32_t clk = FpgaRegRead(P_CLK_FREQ_SEL_REGISTER);
    printf("  FPGA 状态:\n");
    printf("    STATUS(0x0004) = 0x%08X\n", status);
    printf("    DEBUG (0xF000) = 0x%08X\n", dbg);
    printf("    CLK_FREQ(0x4008) = 0x%X (SerDes速率选择)\n", clk & 0xF);
    printf("    A通道: %s  B通道: %s\n",
           GlinkGetLinkStatus(GLINK_CH_A) ? "UP" : "DOWN",
           GlinkGetLinkStatus(GLINK_CH_B) ? "UP" : "DOWN");
}

/*----------------- L2: ctrlNC 协议接口 ----------------------------**/
/* 参照 CtrlNC-NT-demo/JLK1263.c 实现, 所有数据走 MEM 空间 */

int CtrlNcMemoryMap(uint16_t stack_addr, uint16_t mem_addr, uint16_t exch_count) {
    /* MEM(0x102)=stack_addr, MEM(0x103)=0xFFFF-exch_count
     * MEM(stack+4)=0, MEM(stack+6/7)=mem_addr(低/高16位) */
    JlkMemWrite(0x102, stack_addr);
    JlkMemWrite(0x103, 0xFFFF - exch_count);
    JlkMemWrite(stack_addr + 0x4, 0x0000);
    JlkMemWrite(stack_addr + 0x6, mem_addr & 0xFFFF);
    JlkMemWrite(stack_addr + 0x7, (mem_addr >> 16) & 0xFFFF);
    return 0;
}

int CtrlNcConfigDescriptor(uint16_t mem_addr,
                           uint16_t nt1_id, uint16_t nt2_id,
                           uint16_t nt3_id, uint16_t nt4_id,
                           uint16_t subaddress, uint8_t tr,
                           uint16_t byte_count) {
    /* 发送描述符布局 (8字):
     *   +0: NT1_ID, +1: NT2_ID, +2: NT3_ID, +3: NT4_ID
     *   +4: subaddress, +5: byte_count
     *   +6: TR|mode|state|INT|retry|prior|one_chanel|CH_B|NT_num
     *   +7: NT1_type|NT2_type|NT3_type|NT4_type
     * 默认: mode=0, state=0, INT=1, retry_en=1, prior=0,
     *       one_chanel=1, CH_B=0, NT_num=1, NT_type=0(ctrlNC1) */
    uint16_t ctrl_word = (uint16_t)(tr |
        (0 << 1)  |  /* mode */
        (0 << 2)  |  /* state */
        (1 << 3)  |  /* INT */
        (1 << 4)  |  /* retry_en */
        (0 << 5)  |  /* prior */
        (1 << 6)  |  /* one_chanel */
        (0 << 7)  |  /* CH_B */
        (1 << 8));   /* NT_num=1 */
    JlkMemWrite(mem_addr + 0x0, nt1_id);
    JlkMemWrite(mem_addr + 0x1, nt2_id);
    JlkMemWrite(mem_addr + 0x2, nt3_id);
    JlkMemWrite(mem_addr + 0x3, nt4_id);
    JlkMemWrite(mem_addr + 0x4, subaddress);
    JlkMemWrite(mem_addr + 0x5, byte_count);
    JlkMemWrite(mem_addr + 0x6, ctrl_word);
    JlkMemWrite(mem_addr + 0x7, 0x0000);   /* NT_type 全为 ctrlNC1=0 */
    return 0;
}

int CtrlNcSendData(uint16_t mem_addr, const uint16_t *data, int word_count) {
    /* demo: MEM(memory_address + 0x8 + i) = Data[i] */
    for (int i = 0; i < word_count; i++) {
        JlkMemWrite(mem_addr + 0x8 + i, data[i]);
    }
    return 0;
}

int CtrlNcStartXmit(int ctrlnc1, int ctrlnc2) {
    /* demo: REG(0x01) = soft_reset | (ctrlnc1_send<<4) | (ctrlnc2_send<<7) */
    uint16_t val = (uint16_t)((ctrlnc1 << 4) | (ctrlnc2 << 7));
    JlkRegWrite(0x01, val);
    return 0;
}

int CtrlNcWaitDone(uint16_t stack_addr, int timeout_ms) {
    /* demo: 等 MEM(stack_addr) 的 bit15 (EOE=1) */
    int retry = timeout_ms / 10;
    while (retry-- > 0) {
        uint16_t st = JlkMemRead(stack_addr);
        if (st & 0x8000) return 0;
        delay_us(10000);
    }
    return -1;
}

/*----------------- L2: ctrlNT 协议接口 ----------------------------**/

int CtrlNtSetStackPtr(uint16_t stack_addr) {
    /* demo: MEM(GLINK_NT_SP=0x110) = stack_address */
    JlkMemWrite(0x110, stack_addr);
    return 0;
}

int CtrlNtChannelMap(int ch, uint16_t nc_type, uint16_t nc_id) {
    /* demo: MEM(0x120 + chanel-1) = ctrlNC_ID | 0x8000 | (NC_type<<12) */
    JlkMemWrite(0x120 + (ch - 1), (nc_id & 0x0FFF) | 0x8000 | ((nc_type & 0xF) << 12));
    return 0;
}

int CtrlNtConfigRecvMemory(int ch, uint16_t subaddress, uint16_t recv_addr) {
    /* 完整版 (对齐 CtrlNT.c demo config_recv_ctrlnt_memory):
     *   MEM(0x200*ch)                    = area (默认0)
     *   MEM(0x200*ch + 1)                = service (默认0)
     *   MEM(0x200*ch + 0x40 + subaddress) = contrl_word (0x200)
     *   MEM(0x200*ch + 0x82 + sub*2-2)   = recv_addr_low
     *   MEM(0x200*ch + 0x83 + sub*2-2)   = recv_addr_high */
    uint16_t base = 0x200 * ch;
    JlkMemWrite(base,                     0x0000);   /* area */
    JlkMemWrite(base + 0x1,               0x0000);   /* service */
    JlkMemWrite(base + 0x40 + subaddress, 0x0200);   /* contrl_word */
    JlkMemWrite(base + 0x82 + subaddress * 2 - 2, recv_addr & 0xFFFF);
    JlkMemWrite(base + 0x83 + subaddress * 2 - 2, (recv_addr >> 16) & 0xFFFF);
    return 0;
}

uint16_t JlkGetIntStatus(void) {
    /* demo: REG(0x06) */
    return JlkRegRead(0x06);
}

int CtrlNtWaitInterrupt(int timeout_ms) {
    /* demo: 等 REG(0x06) == 0x800 (ctrlNT 接收中断) */
    int retry = timeout_ms / 10;
    while (retry-- > 0) {
        if (JlkRegRead(0x06) & 0x0800) return 0;
        delay_us(10000);
    }
    return -1;
}

int CtrlNtWaitRecv(uint16_t initial_sp, int timeout_ms) {
    /* 轮询 MEM(0x110) NT 栈指针变化, 适用于自环模式 (中断会自动清除) */
    int retry = timeout_ms / 5;
    while (retry-- > 0) {
        uint16_t sp = JlkMemRead(0x110);
        if (sp != initial_sp) return 0;
        delay_us(5000);
    }
    return -1;
}

uint16_t CtrlNtGetRecvBlock(uint16_t *nc_id, uint16_t *tr,
                             uint16_t *subaddress, uint16_t *bytes_len) {
    /* demo: 读 NT 栈指针 MEM(0x110), 然后从栈中获取描述符 */
    uint16_t current_sp = JlkMemRead(0x110) - 8;   /* 每条记录8字 */
    *nc_id      = JlkMemRead(current_sp + 1) & 0x0FFF;
    uint16_t w4 = JlkMemRead(current_sp + 4);
    *tr         = (w4 & 0x100) >> 8;
    *subaddress = w4 & 0x1F;
    *bytes_len  = JlkMemRead(current_sp + 5);
    uint16_t lo = JlkMemRead(current_sp + 6);
    uint16_t hi = JlkMemRead(current_sp + 7);
    return lo | (hi << 16);
}

uint16_t CtrlNtGetCurrentSp(void) {
    /* demo: MEM(GLINK_NT_SP) */
    return JlkMemRead(0x110);
}

uint16_t CtrlNtGetSpTargetNcId(uint16_t current_sp, uint16_t *nc_id,
                                uint16_t *tr, uint16_t *subaddress,
                                uint16_t *bytes_len) {
    /* demo: 从指定栈指针处读取接收信息 */
    *nc_id      = JlkMemRead(current_sp + 1) & 0x0FFF;
    uint16_t w4 = JlkMemRead(current_sp + 4);
    *tr         = (w4 & 0x100) >> 8;
    *subaddress = w4 & 0x1F;
    *bytes_len  = JlkMemRead(current_sp + 5);
    uint16_t lo = JlkMemRead(current_sp + 6);
    uint16_t hi = JlkMemRead(current_sp + 7);
    return lo | (hi << 16);
}

int CtrlNtConfigRecvMemoryFull(int ch, uint16_t area, uint16_t service,
                                uint16_t contrl_word, uint16_t subaddress,
                                uint16_t recv_addr) {
    /* demo: config_recv_ctrlnt_memory 完整版 */
    uint16_t base = 0x200 * ch;
    JlkMemWrite(base,                     area);
    JlkMemWrite(base + 0x1,               service);
    JlkMemWrite(base + 0x40 + subaddress, contrl_word);
    JlkMemWrite(base + 0x82 + subaddress * 2 - 2, recv_addr & 0xFFFF);
    JlkMemWrite(base + 0x83 + subaddress * 2 - 2, (recv_addr >> 16) & 0xFFFF);
    return 0;
}

int CtrlNtConfigSendMemory(int ch, uint16_t subaddress, uint16_t send_addr) {
    /* demo: config_send_ctrlnt_memory */
    uint16_t base = 0x200 * ch;
    JlkMemWrite(base + 0xc0 + subaddress * 2,     send_addr & 0xFFFF);
    JlkMemWrite(base + 0xc1 + subaddress * 2,     (send_addr >> 16) & 0xFFFF);
    return 0;
}

int CtrlNtInitUnusedChannel(uint16_t unused_begin_chanel) {
    /* demo: InitUnusedctrlNTchanel - 剩余15路置0 */
    uint16_t i;
    for (i = unused_begin_chanel; i < 15; i++) {
        JlkMemWrite(0x120 + i, 0x0000);
    }
    return 0;
}

int CtrlNtConfigBusyTable(uint16_t ch, uint16_t tr, uint16_t busy_subaddress) {
    /* demo: config_busy_table */
    uint16_t base = 0x200 * ch;
    if (tr == 0) {  /* 接收子地址 */
        if (busy_subaddress < 16) {
            JlkMemWrite(base + 0x30, 1 << busy_subaddress);
        } else {
            JlkMemWrite(base + 0x31, 1 << (busy_subaddress - 16));
        }
    } else {        /* 发送子地址 */
        if (busy_subaddress < 16) {
            JlkMemWrite(base + 0x32, 1 << busy_subaddress);
        } else {
            JlkMemWrite(base + 0x33, 1 << (busy_subaddress - 16));
        }
    }
    return 0;
}

/*----------------- L2: SmartNC/SmartNT 协议 -----------------------**/

int SmartNc1ConfigTimeout(uint16_t time_out) {
    /* demo: REG(0x29) = time_out */
    JlkRegWrite(0x29, time_out);
    return 0;
}

int SmartNc1Config(uint16_t reg) {
    /* demo: REG(0x2a) = reg */
    JlkRegWrite(0x2a, reg);
    return 0;
}

int SmartNtConfigChannel(uint16_t smartnt_chanel, uint16_t smartnc_id,
                          uint16_t smartnc_chanel, uint16_t long_short_mode) {
    /* demo: REG(0x3c..0x3f) = smartncID | (smartncchanel<<12) | (long_short_mode<<14) */
    uint16_t val = (smartnc_id & 0x0FFF) | ((smartnc_chanel & 0xF) << 12) | ((long_short_mode & 0x1) << 14);
    uint16_t reg_addr;
    switch (smartnt_chanel) {
        case 1: reg_addr = 0x3c; break;
        case 2: reg_addr = 0x3d; break;
        case 3: reg_addr = 0x3e; break;
        case 4: reg_addr = 0x3f; break;
        default: return -1;
    }
    JlkRegWrite(reg_addr, val);
    return 0;
}

int SmartNcStartXmit(int soft_reset) {
    /*
     * 手册 REG(0x01) bit5 是 CtrlNC1「交换组停止」, 不是 Smart 触发。
     * SmartNC 的 TRIG 在芯片管脚侧; K72 上由 FPGA 在写 FIFO/CTRL 时脉冲。
     * 这里对 JLK 仅可选软复位 bit0; 真正触发见 SmartNcShortMsgSendEx /
     * FpgaRegWrite(P_CTRL_REGISTER, CTRL_NCx_TX)。
     */
    if (soft_reset)
        JlkRegWrite(0x01, 0x0001);
    return 0;
}

/*----------------- L2: 完整版 NC/NT 配置 --------------------------**/

int CtrlNcMemoryMapGroup(uint16_t stack_addr, uint16_t gap_time_us,
                         uint16_t mem_addr, uint16_t exch_count) {
    /* demo: configNC_Memory_Map_Group - 支持多交换块, 每块带间隔 */
    uint16_t i;
    JlkMemWrite(0x102, stack_addr);
    JlkMemWrite(0x103, 0xFFFF - exch_count);
    for (i = 0; i < exch_count; i++) {
        JlkMemWrite(stack_addr + 0x4 + 8 * i, gap_time_us);
        JlkMemWrite(stack_addr + 0x6 + 8 * i, mem_addr & 0xFFFF);
        JlkMemWrite(stack_addr + 0x7 + 8 * i, (mem_addr >> 16) & 0xFFFF);
    }
    return 0;
}

int CtrlNcConfigDescriptorFull(uint16_t mem_addr,
                               uint16_t nt1_id, uint16_t nt2_id,
                               uint16_t nt3_id, uint16_t nt4_id,
                               uint16_t subaddress, uint8_t tr,
                               uint8_t mode, uint8_t state,
                               uint8_t int_en, uint8_t retry_en,
                               uint8_t prior, uint8_t one_chanel,
                               uint8_t ch_b, uint16_t nt_num,
                               uint16_t nt1_type, uint16_t nt2_type,
                               uint16_t nt3_type, uint16_t nt4_type,
                               uint16_t byte_count) {
    /* demo: ConfigctrlNC_TargetNT 完整版 */
    uint16_t ctrl_word = (uint16_t)((tr & 0x1) |
        ((mode & 0x1) << 1) |
        ((state & 0x1) << 2) |
        ((int_en & 0x1) << 3) |
        ((retry_en & 0x1) << 4) |
        ((prior & 0x1) << 5) |
        ((one_chanel & 0x1) << 6) |
        ((ch_b & 0x1) << 7) |
        ((nt_num & 0xF) << 8));
    uint16_t nt_type_word = (uint16_t)((nt1_type & 0xF) |
        ((nt2_type & 0xF) << 4) |
        ((nt3_type & 0xF) << 8) |
        ((nt4_type & 0xF) << 12));

    JlkMemWrite(mem_addr + 0x0, nt1_id);
    JlkMemWrite(mem_addr + 0x1, nt2_id);
    JlkMemWrite(mem_addr + 0x2, nt3_id);
    JlkMemWrite(mem_addr + 0x3, nt4_id);
    JlkMemWrite(mem_addr + 0x4, subaddress);
    JlkMemWrite(mem_addr + 0x5, byte_count);
    JlkMemWrite(mem_addr + 0x6, ctrl_word);
    JlkMemWrite(mem_addr + 0x7, nt_type_word);
    return 0;
}

int CtrlNcStartXmitFull(int soft_reset, int ctrlnc1, int ctrlnc2) {
    /* demo: startctrlxmit - REG(0x01) = soft_reset | (ctrlnc1<<4) | (ctrlnc2<<7) */
    uint16_t val = (uint16_t)((soft_reset & 0x1) | ((ctrlnc1 & 0x1) << 4) | ((ctrlnc2 & 0x1) << 7));
    JlkRegWrite(0x01, val);
    return 0;
}

uint16_t CtrlNcGetExchangeBlockStatus(uint16_t stack_addr) {
    /* demo: get_exchangeblock_status */
    return JlkMemRead(stack_addr);
}

int CtrlNc1ConfigRetry(uint16_t retry, uint16_t retry_num) {
    /* demo: config_ctrlnc1_retry - REG(0x18) = (retry<<10) | (retry_num<<15) | (1<<6) */
    JlkRegWrite(0x18, (uint16_t)((retry << 10) | (retry_num << 15) | (1 << 6)));
    JlkRegWrite(0x19, 0);
    return 0;
}

int CtrlNc1ConfigRetryGroup(uint16_t retry, uint16_t retry_num, uint16_t gap_enable) {
    /* demo: config_ctrlnc1_retry_group */
    JlkRegWrite(0x18, (uint16_t)((retry << 10) | (retry_num << 15) | (1 << 6) | (gap_enable << 8)));
    JlkRegWrite(0x19, 0);
    return 0;
}

int CtrlNtConfig(uint16_t reg1, uint16_t reg2) {
    /* demo: configctrlNT - REG(0x24)/REG(0x25) */
    JlkRegWrite(0x24, reg1);
    JlkRegWrite(0x25, reg2);
    return 0;
}

/*----------------- L2: 通道状态查询 (阻塞/非阻塞) -----------------**/

int GlinkCheckChannelStatus(char ch) {
    /* demo: check_chanel_status - 死等 LINK UP */
    while (1) {
        if (GlinkGetChannelStatus(ch)) return 0;
        delay_us(10000);
    }
    return -1;
}

int GlinkGetChannelStatus(char ch) {
    /* demo: get_chanel_status - (REG(0x0A or 0x0B) & 0x03) == 0x3 */
    uint16_t temp;
    if (ch == 'A' || ch == 'a') {
        temp = JlkRegRead(0x0A) & 0x03;
    } else if (ch == 'B' || ch == 'b') {
        temp = JlkRegRead(0x0B) & 0x03;
    } else {
        return 0;
    }
    return (temp == 0x3) ? 1 : 0;
}

/*----------------- L2: 设备能力/硬件信息 --------------------------**/

int GlinkGetCapability(glink_capability_t *cap) {
    if (!cap) return -1;
    cap->fpga_version = FpgaRegRead(0x0000);
    cap->channel_num  = 2;   /* A/B 双通道 */
    cap->port_num     = 2;
    cap->bank_num     = 1;
    cap->jlK1263_reg_0a = JlkRegRead(0x0A);
    cap->jlK1263_reg_0b = JlkRegRead(0x0B);
    return 0;
}

int GlinkGetHardWareInfo(uint32_t *fpga_version, uint16_t *jlK1263_id) {
    if (fpga_version) *fpga_version = FpgaRegRead(0x0000);
    if (jlK1263_id)   *jlK1263_id   = JlkRegRead(0x00);
    return 0;
}

int GlinkResetPort(int port) {
    /* 端口复位: 通过 JLK1263 软复位 + 重新配置通道使能 */
    uint16_t cur = JlkRegRead(0x03);
    uint16_t mask = (port == 0) ? 0x0001 : 0x0002;
    JlkRegWrite(0x03, cur & ~mask);   /* 禁用 */
    delay_us(10000);
    JlkRegWrite(0x03, cur | mask);    /* 重新使能 */
    return 0;
}

/*----------------- L2: 速率配置 --------------------------------**/

int GlinkSetRate(glink_rate_t rate) {
    /* FPGA 0x4008 寄存器选择 SerDes 速率 */
    FpgaRegWrite(P_CLK_FREQ_SEL_REGISTER, (uint32_t)rate);
    return 0;
}

glink_rate_t GlinkGetRate(void) {
    uint32_t val = FpgaRegRead(P_CLK_FREQ_SEL_REGISTER) & 0xF;
    return (glink_rate_t)val;
}

/*----------------- L2: NC/NT 启停控制 ----------------------------**/

int NcStart(void) {
    /* 启动 NC: 设置工作模式 (ctrlNC1) */
    uint16_t cur = JlkRegRead(0x02);
    JlkRegWrite(0x02, cur | 0x0001);
    return 0;
}

int NcStop(void) {
    uint16_t cur = JlkRegRead(0x02);
    JlkRegWrite(0x02, cur & ~0x0001);
    return 0;
}

int NtStart(void) {
    uint16_t cur = JlkRegRead(0x02);
    JlkRegWrite(0x02, cur | 0x0002);
    return 0;
}

int NtStop(void) {
    uint16_t cur = JlkRegRead(0x02);
    JlkRegWrite(0x02, cur & ~0x0002);
    return 0;
}

int NcAperiodicRun(int msg_index, int high_priority) {
    /* 触发非周期消息发送 (用 ctrlNC1 描述符索引=msg_index+1) */
    uint16_t val = (uint16_t)((1 << 4) | (high_priority ? 0x40 : 0));
    JlkRegWrite(0x01, val);
    return 0;
}

/*----------------- L2: SA 级数据收发 (类WGLK220接口) -------------**/
/* 简化实现: 通过 ctrlNC 描述符 + MEM 写入 */

int NcSaFillData(uint16_t nc_id, uint16_t nt_id, uint16_t sa,
                  const uint8_t *data, int len) {
    /* 将数据写到 NC 发送内存区 (mem_addr + 0x8 + i) */
    uint16_t mem_addr = 0x5000 + (nt_id & 0xF) * 0x100;   /* 简单映射 */
    int word_count = (len + 1) / 2;
    for (int i = 0; i < word_count; i++) {
        uint16_t w = data[i * 2] | (data[i * 2 + 1] << 8);
        JlkMemWrite(mem_addr + 0x8 + i, w);
    }
    return 0;
}

int NcSaReadData(uint16_t nc_id, uint16_t nt_id, uint16_t sa,
                  uint8_t *buf, int buf_len) {
    /* 从 NC 接收内存读数据 */
    uint16_t mem_addr = 0x6000 + (nc_id & 0xF) * 0x100;
    int word_count = buf_len / 2;
    for (int i = 0; i < word_count; i++) {
        uint16_t w = JlkMemRead(mem_addr + i);
        buf[i * 2]     = w & 0xFF;
        buf[i * 2 + 1] = (w >> 8) & 0xFF;
    }
    return buf_len;
}

int NtAddSa(int ch, uint16_t nc_id, uint16_t subaddress,
             int enable_tx, int enable_rx) {
    /* NT 添加 SA: 配置接收/发送内存 */
    if (enable_rx) {
        uint16_t recv_addr = 0x6000 + ch * 0x400;
        CtrlNtConfigRecvMemoryFull(ch, 0, 0, 0x0200, subaddress, recv_addr);
    }
    if (enable_tx) {
        uint16_t send_addr = 0x7000 + ch * 0x400;
        CtrlNtConfigSendMemory(ch, subaddress, send_addr);
    }
    return 0;
}

int NtSaReadData(int ch, uint16_t subaddress, uint8_t *buf, int buf_len) {
    /* 从 NT 接收内存读数据 */
    uint16_t recv_addr = 0x6000 + ch * 0x400;
    int word_count = buf_len / 2;
    for (int i = 0; i < word_count; i++) {
        uint16_t w = JlkMemRead(recv_addr + i);
        buf[i * 2]     = w & 0xFF;
        buf[i * 2 + 1] = (w >> 8) & 0xFF;
    }
    return buf_len;
}

/*----------------- L2: 消息管理 (类WGLK220接口) ------------------**/
/* 用本地数组保存消息配置, 实际发送时通过 ctrlNC 描述符 */

static glink_msg_t s_msg_buf[GLINK_MAX_MSG_NUM];
static int s_msg_count = 0;

int NcAllocMsgBuf(int periodic_num, int aperiodic_num) {
    int total = periodic_num + aperiodic_num;
    if (total > GLINK_MAX_MSG_NUM) return -1;
    s_msg_count = total;
    for (int i = 0; i < total; i++) {
        memset(&s_msg_buf[i], 0, sizeof(glink_msg_t));
    }
    return 0;
}

int NcSetMsg(int msg_index, const glink_msg_t *msg) {
    if (msg_index < 0 || msg_index >= s_msg_count) return -1;
    s_msg_buf[msg_index] = *msg;
    return 0;
}

int NcGetMsg(int msg_index, glink_msg_t *msg) {
    if (msg_index < 0 || msg_index >= s_msg_count) return -1;
    *msg = s_msg_buf[msg_index];
    return 0;
}

/*----------------- L2: 增强功能 (P2) -----------------------------**/

int NcConfigMulticast(int ch, int enable) {
    /* 多播配置: NT to NT 转发, 通过 NC 描述符的 NT_num>1 实现 */
    /* 简化: 配置描述符 ctrl_word bit6 (one_chanel) = 0 表示多播 */
    (void)ch; (void)enable;
    return 0;
}

int NcConfigMonitor(int ch, int enable) {
    /* NC Monitor: 监听 NT to NT, 通过工作模式 monitor 位 */
    uint16_t cur = JlkRegRead(0x02);
    if (enable) {
        JlkRegWrite(0x02, cur | (1 << 13));
    } else {
        JlkRegWrite(0x02, cur & ~(1 << 13));
    }
    (void)ch;
    return 0;
}

int GlinkSetRedunMode(int enable) {
    /* A/B 冗余模式: 同时使能两个通道 */
    uint16_t cur = JlkRegRead(0x03);
    if (enable) {
        JlkRegWrite(0x03, cur | 0x03);   /* A+B 都使能 */
    } else {
        JlkRegWrite(0x03, cur & ~0x02);  /* 只保留 A */
    }
    return 0;
}

int GlinkSetTimeSyn(uint32_t timesynvalue, uint32_t synerrorvalue, uint32_t triggermode) {
    /* 时间同步: 通过 JLK1263 timestamp 寄存器 */
    (void)synerrorvalue; (void)triggermode;
    JlkRegWrite(0x07, (uint16_t)(timesynvalue & 0xFFFF));
    return 0;
}

/*----------------- L2: loopback 自检 -----------------------------**/

int GlinkLoopbackTest(void) {
    /* JLK1263 内部自检:
     * 1. 检查 A/B 通道状态
     * 2. MEM 读写测试
     * 3. REG 读写测试 */
    printf("[loopback] 1. 检查通道状态...\n");
    uint16_t reg_0a = JlkRegRead(0x0A);
    uint16_t reg_0b = JlkRegRead(0x0B);
    printf("  A通道(0x0A)=0x%04X, B通道(0x0B)=0x%04X\n", reg_0a, reg_0b);
    if ((reg_0a & 0x03) != 0x03) {
        printf("  [失败] A通道 LINK DOWN\n");
        return -1;
    }
    if ((reg_0b & 0x03) != 0x03) {
        printf("  [失败] B通道 LINK DOWN\n");
        return -1;
    }

    printf("[loopback] 2. MEM 读写测试...\n");
    JlkMemWrite(0x100, 0x55AA);
    uint16_t rd = JlkMemRead(0x100);
    if (rd != 0x55AA) {
        printf("  [失败] MEM 读写不一致 (写0x55AA, 读0x%04X)\n", rd);
        return -1;
    }
    printf("  [通过] MEM 读写一致 (0x%04X)\n", rd);

    printf("[loopback] 3. REG 读写测试...\n");
    JlkRegWrite(0x00, 0x8003);
    rd = JlkRegRead(0x00);
    if (rd != 0x8003) {
        printf("  [失败] REG 读写不一致 (写0x8003, 读0x%04X)\n", rd);
        return -1;
    }
    printf("  [通过] REG 读写一致 (0x%04X)\n", rd);

    printf("[loopback] 全部通过!\n");
    return 0;
}

int FpgaFifoReset(void) {
    /* demo: reset_fpga_fifo - 必须脉冲后拉低, 否则 FIFO 一直停在复位 */
    FpgaRegWrite(P_FIFO_RESET_REGISTER, 0x1);
    delay_us(1000);
    FpgaRegWrite(P_FIFO_RESET_REGISTER, 0x0);
    delay_us(1000);
    return 0;
}

/*================= SmartNC 完整数据传输 (6.5) =====================**/

/* SmartNC 通道对应的寄存器地址表 */
static const uint16_t SMARTNC_TIMEOUT_REG[4] = {
    JLK_REG_SMARTNC1_TIMEOUT, JLK_REG_SMARTNC2_TIMEOUT,
    JLK_REG_SMARTNC3_TIMEOUT, JLK_REG_SMARTNC4_TIMEOUT
};
static const uint16_t SMARTNC_CONFIG_REG[4] = {
    JLK_REG_SMARTNC1_CONFIG, JLK_REG_SMARTNC2_CONFIG,
    JLK_REG_SMARTNC3_CONFIG, JLK_REG_SMARTNC4_CONFIG
};
static const uint16_t SMARTNC_STATUS_REG[4] = {
    JLK_REG_SMARTNC1_STATUS, JLK_REG_SMARTNC2_STATUS,
    JLK_REG_SMARTNC3_STATUS, JLK_REG_SMARTNC4_STATUS
};
static const uint16_t SMARTNC_SP_MEM[4] = {
    MEM_SMARTNC1_SP, MEM_SMARTNC2_SP,
    MEM_SMARTNC3_SP, MEM_SMARTNC4_SP
};
static const uint16_t SMARTNC_STACK_BASE[4] = {
    MEM_SMARTNC1_STACK_BASE, MEM_SMARTNC2_STACK_BASE,
    MEM_SMARTNC3_STACK_BASE, MEM_SMARTNC4_STACK_BASE
};

int SmartNcInit(int ch, const smartnc_config_t *cfg) {
    if (ch < 1 || ch > 4 || !cfg) return -1;
    int idx = ch - 1;

    /* 1. 配置超时寄存器 */
    JlkRegWrite(SMARTNC_TIMEOUT_REG[idx], cfg->timeout);

    /* 2. 配置 SmartNC 配置寄存器 */
    uint16_t config = 0;
    config |= (cfg->bandwidth & 0x3);
    config |= ((cfg->payload_size & 0x3) << 2);
    config |= ((cfg->stack_depth & 0x3) << 4);
    config |= (cfg->stack_en ? SMARTNC_STACK_EN : 0);
    config |= (cfg->high_priority ? SMARTNC_HIGH_PRI : 0);
    config |= (cfg->short_msg_mode ? SMARTNC_SHORT_MSG : 0);
    config |= (cfg->single_channel ? SMARTNC_SINGLE_CH : 0);
    config |= (cfg->use_ch_b ? SMARTNC_CH_B : 0);
    JlkRegWrite(SMARTNC_CONFIG_REG[idx], config);

    return 0;
}

int SmartNcSetStackPtr(int ch, uint16_t stack_addr) {
    if (ch < 1 || ch > 4) return -1;
    JlkMemWrite(SMARTNC_SP_MEM[ch - 1], stack_addr);
    return 0;
}

uint16_t SmartNcGetCurrentSp(int ch) {
    if (ch < 1 || ch > 4) return 0;
    return JlkMemRead(SMARTNC_SP_MEM[ch - 1]);
}

/* FPGA FIFO 通路: SmartNC1/2->FIFO1, SmartNC3/4->FIFO2 */
static int smart_fifo_index(int ch) { return (ch <= 2) ? 0 : 1; }

/*
 * 短报 SmartNCx→SmartNTx (厂家 FPGA 确认):
 *   WR_SEL = NCx (写发数), RD_SEL = NTx (读对端接收)
 * ch1 → F1_WR=00 F1_RD=10 → 低4位 0x8, 典型整字节 0xC8 (复位默认)
 */
static uint32_t smart_fifo_select_nc_wr_nt_rd(int ch)
{
    uint32_t cur = FpgaRegRead(P_FIFO_SELECT_REGISTER) & 0xFFu;
    int fifo_idx = smart_fifo_index(ch);
    uint32_t lane = (uint32_t)((ch == 2 || ch == 4) ? 1 : 0);
    uint32_t wr = lane;        /* 00/01 = NCx */
    uint32_t rd = 0x2u | lane; /* 10/11 = NTx */
    if (fifo_idx == 0)
        return (cur & 0xF0u) | wr | (rd << 2);
    return (cur & 0x0Fu) | (wr << 4) | (rd << 6);
}

uint32_t SmartFifoGetSelect(void)
{
    return FpgaRegRead(P_FIFO_SELECT_REGISTER) & 0xFFu;
}

int SmartFifoSetNcShort(int ch)
{
    uint32_t want;
    uint32_t got;
    if (ch < 1 || ch > 4)
        return -1;
    want = smart_fifo_select_nc_wr_nt_rd(ch);
    FpgaRegWrite(P_FIFO_SELECT_REGISTER, want);
    delay_us(50);
    got = SmartFifoGetSelect();
    if (got != want) {
        printf("[SEL] 写 0x%02X 读回 0x%02X 不一致 (ch=%d)\n", want, got, ch);
        return -1;
    }
    return 0;
}

void SmartFifoDumpSelect(const char *tag)
{
    uint32_t s = SmartFifoGetSelect();
    printf("[SEL %s] 0x%02X  F1_WR=%u F1_RD=%u F2_WR=%u F2_RD=%u",
           tag ? tag : "?", s,
           (unsigned)(s & 3u), (unsigned)((s >> 2) & 3u),
           (unsigned)((s >> 4) & 3u), (unsigned)((s >> 6) & 3u));
    if ((s & 0x0Fu) == 0x08u)
        printf("  (F1 NC1/NT1, 短报 NC→NT 目标)\n");
    else if ((s & 0x0Fu) == 0x00u)
        printf("  (F1 NC1/NC1, 旧手册 0xC0)\n");
    else
        printf("\n");
}

int SmartNcWaitRdFifo(int ch, int timeout_ms)
{
    int fifo_idx;
    uint32_t rd0, rc0;
    uint16_t fc0_lo, fc0_hi;
    int retry;
    if (ch < 1 || ch > 4)
        return -1;
    fifo_idx = smart_fifo_index(ch);
    SmartFifoSetNcShort(ch);
    rd0 = FpgaRegRead(fifo_idx == 0 ? P_RD_FIFO1_WR_NUM : P_RD_FIFO2_WR_NUM);
    rc0 = FpgaRegRead(fifo_idx == 0 ? P_RC_FIFO1_WR_NUM : P_RC_FIFO2_WR_NUM);
    fc0_lo = JlkRegRead(0x61);
    fc0_hi = JlkRegRead(0x62);
    retry = timeout_ms / 5;
    while (retry-- > 0) {
        uint32_t rd = FpgaRegRead(fifo_idx == 0 ? P_RD_FIFO1_WR_NUM : P_RD_FIFO2_WR_NUM);
        uint32_t rc = FpgaRegRead(fifo_idx == 0 ? P_RC_FIFO1_WR_NUM : P_RC_FIFO2_WR_NUM);
        uint16_t fc_lo = JlkRegRead(0x61);
        uint16_t fc_hi = JlkRegRead(0x62);
        if (rd != rd0 || rc != rc0 || fc_lo != fc0_lo || fc_hi != fc0_hi)
            return 0;
        delay_us(5000);
    }
    return -1;
}

/*
 * P_FIFO_SELECT (EMIF_IF.v / 硬件指南):
 *   [1:0]=FIFO1_WR_SEL  [3:2]=FIFO1_RD_SEL
 *   [5:4]=FIFO2_WR_SEL  [7:6]=FIFO2_RD_SEL
 * JLK: 00=NCx奇数, 01=NCx偶数, 10=NTx奇数, 11=NTx偶数.
 *
 * 短报 SmartNC→SmartNT (厂家确认): WR=NCx, RD=NTx (复位默认 0xC8).
 * 旧软件指南 6.5.8 写 WR=RD=NC(0xC0) 与 FPGA 实际连线不符, 已弃用.
 */
static uint32_t smart_fifo_select_pack(int ch, int is_nt)
{
    uint32_t cur = FpgaRegRead(P_FIFO_SELECT_REGISTER) & 0xFFu;
    int fifo_idx = smart_fifo_index(ch);
    uint32_t lane = (uint32_t)((ch == 2 || ch == 4) ? 1 : 0);
    uint32_t code = is_nt ? (0x2u | lane) : lane;
    if (fifo_idx == 0) {
        cur = (cur & 0xF0u) | code | (code << 2); /* F1 WR+RD */
    } else {
        cur = (cur & 0x0Fu) | (code << 4) | (code << 6); /* F2 WR+RD */
    }
    return cur;
}

static void smart_fifo_select(int ch, int is_nt)
{
    FpgaRegWrite(P_FIFO_SELECT_REGISTER, smart_fifo_select_pack(ch, is_nt));
}

static uint32_t smart_ctrl_tx_bit(int ch)
{
    switch (ch) {
    case 1: return CTRL_NC1_TX;
    case 2: return CTRL_NC2_TX;
    case 3: return CTRL_NC3_TX;
    case 4: return CTRL_NC4_TX;
    default: return 0;
    }
}

static int smart_fifo_write_words(int ch, int is_nt, const uint16_t *words, int count)
{
    int fifo_idx = smart_fifo_index(ch);
    uint32_t wr = (fifo_idx == 0) ? P_FIFO1_WRITE_REGISTER : P_FIFO2_WRITE_REGISTER;
    int i;
    /* Smart 同步 FIFO: 只需 WD 口; 不要脉冲 SEND_RAM (那是 Ctrl 发送 RAM 路径) */
    if (is_nt)
        smart_fifo_select(ch, 1);
    else if (SmartFifoSetNcShort(ch) != 0)
        smart_fifo_select(ch, 0); /* 读回失败仍尝试打包写入 */
    for (i = 0; i < count; i++)
        FpgaRegWrite(wr, words[i]);
    return count;
}

int SmartNcLongMsgSend(int ch, const uint8_t *data, uint32_t byte_count) {
    if (ch < 1 || ch > 4 || !data || byte_count == 0) return -1;

    uint16_t tmp[256];
    uint32_t word_count = (byte_count + 1) / 2;
    uint32_t i, chunk, off = 0;

    while (off < word_count) {
        chunk = word_count - off;
        if (chunk > 256) chunk = 256;
        for (i = 0; i < chunk; i++) {
            uint32_t bi = (off + i) * 2;
            uint16_t lo = data[bi];
            uint16_t hi = (bi + 1 < byte_count) ? data[bi + 1] : 0;
            /* 手册表54/60: 第1字节在高位, 如 01,02 → 0x0102 */
            tmp[i] = (uint16_t)((lo << 8) | hi);
        }
        smart_fifo_write_words(ch, 0, tmp, (int)chunk);
        off += chunk;
    }
    FpgaRegWrite(P_CTRL_REGISTER, smart_ctrl_tx_bit(ch));
    return 0;
}

int SmartNcShortMsgSendEx(int ch, uint16_t offset_or_sa,
                          uint16_t nt_id, uint8_t nt_type,
                          const uint8_t *data, uint16_t byte_count,
                          int retry_en)
{
    uint16_t words[3 + 256];
    uint16_t len_field;
    uint16_t ctrl;
    int n = 0;
    int i;

    if (ch < 1 || ch > 4) return -1;
    if (byte_count > 512) return -1;
    if (byte_count > 0 && !data) return -1;

    SmartFifoDumpSelect("SendEx-pre");
    if (SmartFifoSetNcShort(ch) != 0)
        printf("[SEL] SendEx: SetNcShort 读回失败, 仍继续发数\n");

    /* 表54: len bit[8:0], 0 表示 512 */
    len_field = (byte_count == 512) ? 0 : (byte_count & 0x1FF);

    /* word0: 偏移/子地址 */
    words[n++] = offset_or_sa;
    /* word1: bit15=0(NT收), bit13:12=01(1个NT), bit10=retry, bit8:0=len */
    ctrl = (uint16_t)(0x1000 | (retry_en ? 0x0400 : 0) | len_field);
    words[n++] = ctrl;
    /* word2: NT_ID | (type<<12) */
    words[n++] = (uint16_t)((nt_id & 0x0FFF) | ((nt_type & 0x7) << 12));

    if (byte_count > 0) {
        int wc = (byte_count + 1) / 2;
        for (i = 0; i < wc; i++) {
            uint16_t lo = data[i * 2];
            uint16_t hi = (i * 2 + 1 < byte_count) ? data[i * 2 + 1] : 0;
            /* 手册表54: 先发字节在高 8 位 */
            words[n++] = (uint16_t)((lo << 8) | hi);
        }
    }

    smart_fifo_write_words(ch, 0 /*SmartNC*/, words, n);
    SmartFifoDumpSelect("SendEx-post-WD");
    /* FPGA: SEND_NUM + CTRL -> WC_FIFO -> SMARTNCx_TRIG -> 抽 WD 到 JLK FIFO */
    FpgaRegWrite(P_NC1_SEND_NUM + (ch - 1) * 4, (uint32_t)n);
    FpgaRegWrite(P_CTRL_REGISTER, smart_ctrl_tx_bit(ch));
    SmartFifoDumpSelect("SendEx-post-TRIG");
    return 0;
}

int SmartNcShortMsgSend(int ch, const uint8_t *data, uint16_t byte_count) {
    /* 表54: type 000=SmartNT1; 本节点默认 ID=0x003 */
    return SmartNcShortMsgSendEx(ch, 0x0001, 0x0003, 0 /*SmartNT1*/,
                                 data, byte_count, 0);
}

int SmartNcWaitDone(int ch, int timeout_ms) {
    if (ch < 1 || ch > 4) return -1;
    int idx = ch - 1;
    int retry = timeout_ms / 5;
    int saw_busy = 0;
    while (retry-- > 0) {
        uint16_t status = JlkRegRead(SMARTNC_STATUS_REG[idx]);
        /* bit14=单交换忙, bit15=交换组忙 (手册 5.2.11) */
        if (status & 0xC000)
            saw_busy = 1;
        if (saw_busy && !(status & 0xC000))
            return 0;
        /* 失败计数 bit[7:4] 增加且已空闲也视为结束 */
        if (saw_busy == 0 && (status & 0x00F0) && !(status & 0xC000) &&
            retry < (timeout_ms / 5 - 2))
            return 0;
        delay_us(5000);
    }
    /* 超时前若从未见忙, 仍检查是否已空闲(可能极短交换) */
    {
        uint16_t status = JlkRegRead(SMARTNC_STATUS_REG[idx]);
        if (!(status & 0xC000)) return 0;
    }
    return -1;
}

uint16_t SmartNcGetStatus(int ch, smartnc_status_t *status) {
    if (ch < 1 || ch > 4) return 0;
    int idx = ch - 1;
    uint16_t raw = JlkRegRead(SMARTNC_STATUS_REG[idx]);
    if (status) {
        /* 软件指南 5.2.11 REG 0x2B: 非描述块状态字 */
        status->version_err = 0; /* 描述块字段, 状态寄存器无此位 */
        status->rx_timeout  = 0;
        status->exch_err    = 0;
        status->busy         = (raw >> 11) & 0x1; /* bit11: FIFO写溢出(NC1) */
        status->error        = (raw >> 12) & 0x1; /* bit12: 运行挂起 */
        status->work_mode    = 0;
        status->soe          = (raw >> 14) & 0x1; /* bit14: 交换运行忙 */
        status->eoe          = (raw >> 15) & 0x1; /* bit15: 传输业务忙 */
    }
    return raw;
}

int SmartNcGetDescBlock(int ch, uint16_t sp, uint16_t *status_word,
                         uint16_t *resp_time, uint16_t *soe_time,
                         uint16_t *eoe_time, uint16_t *nt_id,
                         uint16_t *exch_len) {
    if (ch < 1 || ch > 4) return -1;

    /* SmartNC 描述块格式 (每块16字 = 32字节):
     * [0]: 块状态字
     * [1]: 响应时间
     * [2-3]: SOE时间戳
     * [4-5]: EOE时间戳
     * [6]: NT_ID | NT_TYPE
     * [7]: 交换字节长度
     */
    if (status_word) *status_word = JlkMemRead(sp + 0);
    if (resp_time)   *resp_time   = JlkMemRead(sp + 1);
    if (soe_time)    *soe_time    = JlkMemRead(sp + 2);
    if (eoe_time)    *eoe_time    = JlkMemRead(sp + 4);
    if (nt_id)       *nt_id       = JlkMemRead(sp + 6);
    if (exch_len)    *exch_len    = JlkMemRead(sp + 7);
    return 0;
}

/*================= SmartNT 完整数据接收 (6.6) =====================**/

static const uint16_t SMARTNT_CONFIG_REG[4] = {
    JLK_REG_SMARTNT1_CONFIG, JLK_REG_SMARTNT2_CONFIG,
    JLK_REG_SMARTNT3_CONFIG, JLK_REG_SMARTNT4_CONFIG
};

int SmartNtInit(int ch, const smartnt_config_t *cfg) {
    if (ch < 1 || ch > 4 || !cfg) return -1;
    int idx = ch - 1;

    uint16_t config = 0;
    config |= (cfg->pair_nc_id & 0x0FFF);
    config |= ((cfg->pair_nc_ch & 0x3) << 12);
    config |= (cfg->short_msg_mode ? SMARTNT_SHORT_MSG : 0);
    JlkRegWrite(SMARTNT_CONFIG_REG[idx], config);
    /* 勿改 FIFO_SEL; 短报发数前由 SmartFifoSetNcShort 统一设 WR=NC RD=NT */
    return 0;
}

int SmartNtLongMsgRecv(int ch, uint8_t *buf, int buf_len,
                        uint16_t *src_nc_id, uint8_t *src_nc_type) {
    if (ch < 1 || ch > 4 || !buf || buf_len < 4) return -1;

    uint16_t w0, w1, w2;
    uint32_t total_bytes;
    uint32_t word_count;
    uint32_t i;

    smart_fifo_select(ch, 1 /*SmartNT*/);

    /* 经 RD_FIFO (0x3000) 读, 不是写口 0x1000 */
    w0 = (uint16_t)(FpgaRegRead(P_DATA_READ_REGISTER) & 0xFFFF);
    w1 = (uint16_t)(FpgaRegRead(P_DATA_READ_REGISTER) & 0xFFFF);
    w2 = (uint16_t)(FpgaRegRead(P_DATA_READ_REGISTER) & 0xFFFF);
    if (src_nc_id)   *src_nc_id = w0 & 0x0FFF;
    if (src_nc_type) *src_nc_type = (uint8_t)((w0 >> 12) & 0x7);
    total_bytes = ((uint32_t)w1 << 16) | w2;
    if (total_bytes > (uint32_t)buf_len) total_bytes = (uint32_t)buf_len;

    word_count = (total_bytes + 1) / 2;
    for (i = 0; i < word_count; i++) {
        uint16_t w = (uint16_t)(FpgaRegRead(P_DATA_READ_REGISTER) & 0xFFFF);
        if (i * 2 < (uint32_t)buf_len) buf[i * 2] = (uint8_t)((w >> 8) & 0xFF);
        if (i * 2 + 1 < (uint32_t)buf_len) buf[i * 2 + 1] = (uint8_t)(w & 0xFF);
    }
    return (int)total_bytes;
}

int SmartNtShortMsgRecv(int ch, uint8_t *buf, int buf_len, uint16_t *cmd) {
    if (ch < 1 || ch > 4 || !buf || buf_len < 1) return -1;

    uint16_t w0, w1, w2;
    int data_len;
    int is_recv_cmd;
    int wc, i, got = 0;

    smart_fifo_select(ch, 1 /*SmartNT*/);

    /*
     * 表60 FIFOx_RDATA:
     *  w0: 源 NC_ID | type
     *  w1: 偏移/命令编码
     *  w2: bit15=方向(1=NT应发送, 0=NT接收), bit8:0=长度
     *  w3..: 载荷 (接收指令时)
     */
    w0 = (uint16_t)(FpgaRegRead(P_DATA_READ_REGISTER) & 0xFFFF);
    w1 = (uint16_t)(FpgaRegRead(P_DATA_READ_REGISTER) & 0xFFFF);
    w2 = (uint16_t)(FpgaRegRead(P_DATA_READ_REGISTER) & 0xFFFF);
    (void)w0;
    if (cmd) *cmd = w1;

    data_len = w2 & 0x1FF;
    if (data_len == 0) data_len = 512;
    is_recv_cmd = ((w2 >> 15) & 1) == 0;

    if (!is_recv_cmd) {
        /* NT 发送指令: 无下行载荷, 仅返回 0; 上层应写 ShortMsgSend */
        return 0;
    }

    if (data_len > buf_len) data_len = buf_len;
    wc = (data_len + 1) / 2;
    for (i = 0; i < wc; i++) {
        uint16_t w = (uint16_t)(FpgaRegRead(P_DATA_READ_REGISTER) & 0xFFFF);
        if (got < buf_len) buf[got++] = (uint8_t)((w >> 8) & 0xFF);
        if (got < buf_len) buf[got++] = (uint8_t)(w & 0xFF);
    }
    return data_len;
}

int SmartNtShortMsgSend(int ch, const uint8_t *data, uint16_t byte_count) {
    if (ch < 1 || ch > 4 || !data || byte_count == 0 || byte_count > 512) return -1;

    uint16_t tmp[256];
    int wc = (byte_count + 1) / 2;
    int i;

    for (i = 0; i < wc; i++) {
        uint16_t lo = data[i * 2];
        uint16_t hi = (i * 2 + 1 < byte_count) ? data[i * 2 + 1] : 0;
        tmp[i] = (uint16_t)((lo << 8) | hi);
    }
    smart_fifo_write_words(ch, 1 /*SmartNT*/, tmp, wc);
    /* ACK/触发: 用对应 NT 发送位 */
    {
        uint32_t bit = CTRL_NT1_TX << (ch - 1);
        FpgaRegWrite(P_CTRL_REGISTER, bit);
    }
    return 0;
}

int SmartNtWaitRecv(int ch, int timeout_ms) {
    if (ch < 1 || ch > 4) return -1;
    int fifo_idx = smart_fifo_index(ch);
    /* 必须在 FPGA 抽 JLK RDATA 之前把 RD_SEL 指到本路 SmartNT */
    smart_fifo_select(ch, 1 /*SmartNT*/);
    uint32_t rd0 = FpgaRegRead(fifo_idx == 0 ? P_RD_FIFO1_WR_NUM : P_RD_FIFO2_WR_NUM);
    uint32_t rc0 = FpgaRegRead(fifo_idx == 0 ? P_RC_FIFO1_WR_NUM : P_RC_FIFO2_WR_NUM);
    uint16_t fc0_lo = JlkRegRead(0x61);
    uint16_t fc0_hi = JlkRegRead(0x62);
    int retry = timeout_ms / 5;

    while (retry-- > 0) {
        uint32_t rd = FpgaRegRead(fifo_idx == 0 ? P_RD_FIFO1_WR_NUM : P_RD_FIFO2_WR_NUM);
        uint32_t rc = FpgaRegRead(fifo_idx == 0 ? P_RC_FIFO1_WR_NUM : P_RC_FIFO2_WR_NUM);
        uint16_t fc_lo = JlkRegRead(0x61);
        uint16_t fc_hi = JlkRegRead(0x62);
        if (rd != rd0 || rc != rc0 || fc_lo != fc0_lo || fc_hi != fc0_hi)
            return 0;
        delay_us(5000);
    }
    return -1;
}

/*================= CtrlNT 高级功能 ================================**/

int CtrlNtModeCodeProcess(int ch, uint16_t mode_code) {
    /* CtrlNT 模式码处理: 配置 MEM 空间模式码区域 */
    uint16_t addr = CTRLNT_MODE_CODE_BASE + (ch - 1) * 0x10;
    JlkMemWrite(addr, mode_code);
    return 0;
}

int CtrlNtEnhanceModeCode(int ch, uint16_t enhance_mode) {
    /* 增强型模式码处理 */
    uint16_t addr = CTRLNT_ENHANCE_MODE_BASE + (ch - 1) * 0x10;
    JlkMemWrite(addr, enhance_mode);
    return 0;
}

int CtrlNtIllegalCmdConfig(int ch, uint16_t illegal_cmd) {
    /* 命令非法配置 */
    uint16_t addr = CTRLNT_ILLEGAL_CFG_BASE + (ch - 1) * 0x10;
    JlkMemWrite(addr, illegal_cmd);
    return 0;
}

/*================= 16个双向IO口 (标准模式) ========================**/

int GpioSetDirection(uint16_t mask) {
    JlkMemWrite(GPIO_REG_DIRECTION, mask);
    return 0;
}

int GpioSetOutput(uint16_t value) {
    JlkMemWrite(GPIO_REG_OUTPUT, value);
    return 0;
}

uint16_t GpioReadback(void) {
    return JlkMemRead(GPIO_REG_READBACK);
}

/*================= 监听模式 NM (第7章) ===========================**/

int NmInit(const nm_config_t *cfg) {
    if (!cfg) return -1;

    /* 1. 配置终端ID */
    JlkRegWrite(JLK_REG_NODE_ID, cfg->node_id | 0x8000);

    /* 2. 配置功能寄存器 */
    uint16_t func = cfg->channel_en & 0x03;  /* A/B 通道使能 */
    if (cfg->ring_enable)      func |= (1 << 2);
    if (cfg->bandwidth_stats) func |= (1 << 3);
    if (cfg->fault_detect)    func |= (1 << 9);
    JlkRegWrite(JLK_REG_CHANNEL_EN, func);

    /* 3. 配置工作模式 (监听模式) */
    uint16_t mode = MODE_MONITOR;  /* 监听使能 */
    JlkRegWrite(JLK_REG_WORK_MODE, mode);

    /* 4. 初始化 NM 监听记录区 */
    for (int i = 0; i < MEM_NM_RECORD_SIZE; i++) {
        JlkMemWrite(MEM_NM_RECORD_BASE + i, 0);
    }

    return 0;
}

int NmReadRecord(uint8_t *buf, int buf_len, uint32_t *timestamp) {
    if (!buf || buf_len < 4) return -1;

    /* NM 监听帧格式:
     * [0-1]: 帧头 (源ID + 帧类型)
     * [2-3]: 时间戳
     * [4..]: 帧数据
     */
    uint16_t header = JlkMemRead(MEM_NM_RECORD_BASE);
    uint16_t ts_l = JlkMemRead(MEM_NM_RECORD_BASE + 1);
    uint16_t ts_h = JlkMemRead(MEM_NM_RECORD_BASE + 2);

    if (timestamp) *timestamp = ((uint32_t)ts_h << 16) | ts_l;

    buf[0] = header & 0xFF;
    buf[1] = (header >> 8) & 0xFF;
    buf[2] = ts_l & 0xFF;
    buf[3] = (ts_l >> 8) & 0xFF;

    int read_bytes = 4;
    for (int i = 2; i < buf_len / 2 && read_bytes < buf_len; i++) {
        uint16_t w = JlkMemRead(MEM_NM_RECORD_BASE + i);
        buf[read_bytes++] = w & 0xFF;
        if (read_bytes < buf_len) {
            buf[read_bytes++] = (w >> 8) & 0xFF;
        }
    }

    return read_bytes;
}

uint16_t NmGetStatus(void) {
    return JlkRegRead(NM_REG_NM_STATUS);
}

/*================= IO模式 (第8章) =================================**/

int IoModeInit(const io_mode_config_t *cfg) {
    if (!cfg) return -1;

    /* 1. 配置芯片ID */
    JlkMemWrite(IO_REG_CHIP_ID, cfg->chip_id);

    /* 2. 配置控制源ID */
    JlkMemWrite(IO_REG_CTRL_SRC1_ID, cfg->ctrl_src_id[0]);
    JlkMemWrite(IO_REG_CTRL_SRC2_ID, cfg->ctrl_src_id[1]);
    JlkMemWrite(IO_REG_CTRL_SRC3_ID, cfg->ctrl_src_id[2]);

    /* 3. 配置安全模式和冗余模式 */
    uint16_t safe_cfg = 0;
    if (cfg->safe_mode)    safe_cfg |= 0x01;
    if (cfg->redun_mode)   safe_cfg |= 0x02;
    if (cfg->ring_node_mode) safe_cfg |= 0x04;
    JlkMemWrite(IO_REG_WHITELIST_SAFE, safe_cfg);

    /* 4. 配置IO输出默认值 */
    JlkMemWrite(IO_REG_OUTPUT_LEVEL, cfg->default_output);

    return 0;
}

int IoPwmOutput(int channel, uint8_t duty_cycle, uint16_t period) {
    if (channel < 0 || channel >= 64) return -1;

    /* PWM配置: 每个IO通道可以配置为PWM输出 */
    uint16_t pwm_addr = IO_REG_PWM_CFG + (channel / 4) * 3;
    uint16_t duty_addr = pwm_addr + 1;
    uint16_t period_addr = pwm_addr + 2;

    JlkMemWrite(pwm_addr, (uint16_t)(channel & 0x03));
    JlkMemWrite(duty_addr, (uint16_t)(duty_cycle));
    JlkMemWrite(period_addr, period);
    return 0;
}

int IoLevelOutput(int channel, int level) {
    if (channel < 0 || channel >= 64) return -1;

    /* 电平输出: 修改IO输出寄存器对应位 */
    uint16_t cur = JlkMemRead(IO_REG_OUTPUT_LEVEL);
    if (channel < 16) {
        if (level) cur |= (1 << channel);
        else       cur &= ~(1 << channel);
        JlkMemWrite(IO_REG_OUTPUT_LEVEL, cur);
    } else {
        /* 扩展IO (16-63) 通过智能接口配置 */
        uint16_t ext_addr = IO_REG_OUTPUT_LEVEL + (channel / 16);
        uint16_t cur_ext = JlkMemRead(ext_addr);
        if (level) cur_ext |= (1 << (channel % 16));
        else       cur_ext &= ~(1 << (channel % 16));
        JlkMemWrite(ext_addr, cur_ext);
    }
    return 0;
}

int IoReadback(int channel) {
    if (channel < 0 || channel >= 32) return -1;

    /* IO回读: 读取回读寄存器对应位 */
    uint16_t data = JlkMemRead(IO_REG_READBACK_DATA);
    return (data >> (channel % 16)) & 0x01;
}

int IoReadbackAutoSend(int channel, int enable) {
    if (channel < 0 || channel >= 32) return -1;

    /* 配置IO回读主动发送 */
    uint16_t cur = JlkMemRead(IO_REG_IO_READBACK_CFG);
    if (enable) cur |= (1 << (channel % 16));
    else        cur &= ~(1 << (channel % 16));
    JlkMemWrite(IO_REG_IO_READBACK_CFG, cur);
    return 0;
}

int SmartInterfaceConfig(uint16_t cmd, const uint8_t *data, int len) {
    /* 智能接口配置: 写指令和数据到智能接口寄存器 */
    JlkMemWrite(IO_REG_SMART_INTF_CFG, cmd);
    for (int i = 0; i < len / 2; i++) {
        uint16_t word = data[i * 2] | (data[i * 2 + 1] << 8);
        JlkMemWrite(IO_REG_SMART_INTF_TX_FIFO, word);
    }
    return 0;
}

int SmartInterfaceTriggerCpu(void) {
    /* 触发CPU: 配置寄存器 bit0=1 */
    uint16_t cur = JlkMemRead(IO_REG_SMART_INTF_CFG);
    JlkMemWrite(IO_REG_SMART_INTF_CFG, cur | 0x0001);
    return 0;
}

int SmartInterfaceResetCpu(void) {
    /* 复位CPU: 配置寄存器 bit1=1 */
    uint16_t cur = JlkMemRead(IO_REG_SMART_INTF_CFG);
    JlkMemWrite(IO_REG_SMART_INTF_CFG, cur | 0x0002);
    return 0;
}

int SmartInterfaceClearFifo(void) {
    /* 清空FIFO: 配置寄存器 bit2=1 */
    uint16_t cur = JlkMemRead(IO_REG_SMART_INTF_CFG);
    JlkMemWrite(IO_REG_SMART_INTF_CFG, cur | 0x0004);
    return 0;
}

/*================= 中继器配置 (5.4) ==============================**/

int RepeaterInit(const repeater_config_t *cfg) {
    if (!cfg) return -1;

    /* 1. 配置中继器编号 (bit0-3: 编号, bit15: 奇校验位) */
    uint16_t num = cfg->repeater_num & 0x0F;
    /* 计算奇校验 */
    uint8_t parity = 1;
    for (int i = 0; i < 4; i++) {
        if ((num >> i) & 1) parity ^= 1;
    }
    num |= (parity << 15);
    JlkMemWrite(IO_REPEATER_NUM, num);

    /* 2. 配置中继器功能 */
    uint16_t func = 0;
    if (cfg->ch_c_enable)      func |= 0x01;
    if (cfg->ch_d_enable)      func |= 0x02;
    if (cfg->ring_mode)        func |= 0x04;
    if (cfg->bandwidth_stats)  func |= 0x08;
    if (cfg->mark_primitive)   func |= (1 << 9);
    JlkMemWrite(IO_REPEATER_FUNC, func);

    return 0;
}

int RepeaterReset(void) {
    /* 中继器软复位: bit0=1 */
    JlkMemWrite(IO_REPEATER_RESET, 0x01);
    delay_us(10000);
    JlkMemWrite(IO_REPEATER_RESET, 0x00);
    return 0;
}

uint16_t RepeaterGetChCStatus(void) {
    return JlkMemRead(REPEATER_REG_CHC_STATUS);
}

uint16_t RepeaterGetChDStatus(void) {
    return JlkMemRead(REPEATER_REG_CHD_STATUS);
}

uint16_t RepeaterGetVersion(void) {
    return JlkMemRead(REPEATER_REG_VERSION);
}

/*================= 帧记录功能 (5.2.13) ============================**/

int FrameRecordEnable(int filter_en, int record_en) {
    uint16_t cfg = 0;
    if (filter_en) cfg |= 0x01;
    if (record_en) cfg |= 0x02;
    JlkRegWrite(JLK_REG_FRAME_RECORD_CFG, cfg);
    return 0;
}

int FrameRecordSetFilter(uint8_t nc_nt_type, uint16_t terminal_id) {
    uint16_t filter = (nc_nt_type & 0x0F) | ((terminal_id & 0x0FFF) << 4);
    JlkRegWrite(JLK_REG_FRAME_FILTER_DSID, filter);
    return 0;
}

int FrameRecordRead(int index, uint16_t frame_info[8]) {
    if (index < 0 || index >= 256 || !frame_info) return -1;

    uint16_t base = MEM_FRAME_RECORD_BASE + index * 8;
    for (int i = 0; i < 8; i++) {
        frame_info[i] = JlkMemRead(base + i);
    }
    return 0;
}

/*================= 运行状态查询 ==================================**/

uint16_t GlinkGetARunStatus(void) {
    return JlkRegRead(JLK_REG_A_RUN_STATUS);
}

uint16_t GlinkGetBRunStatus(void) {
    return JlkRegRead(JLK_REG_B_RUN_STATUS);
}

/*================= 环网络功能 ====================================**/

int GlinkEnableRing(int enable) {
    uint16_t cur = JlkRegRead(JLK_REG_CHANNEL_EN);
    if (enable) {
        JlkRegWrite(JLK_REG_CHANNEL_EN, cur | (1 << 2));
    } else {
        JlkRegWrite(JLK_REG_CHANNEL_EN, cur & ~(1 << 2));
    }
    return 0;
}

int GlinkConfigRingBandwidth(uint8_t bandwidth) {
    uint16_t cur = JlkRegRead(JLK_REG_CHANNEL_EN);
    cur &= ~(0x03 << 4);
    cur |= ((bandwidth & 0x03) << 4);
    JlkRegWrite(JLK_REG_CHANNEL_EN, cur);
    return 0;
}

int GlinkConfigFrameTimeout(uint8_t timeout) {
    uint16_t cur = JlkRegRead(JLK_REG_CHANNEL_EN);
    cur &= ~(0x03 << 6);
    cur |= ((timeout & 0x03) << 6);
    JlkRegWrite(JLK_REG_CHANNEL_EN, cur);
    return 0;
}
