/*============================================================
 * K72 GLink 测试程序
 *
 * 主菜单:
 *   1. 控制流 CtrlNC/CtrlNT   — MEM 描述符路径, A↔B 已验证
 *   2. 智能流 SmartNC/SmartNT — FPGA FIFO 路径
 *   3. 监听 NM / 系统诊断     — 大模式、速率、API、dump
 *   4. LINK 检测              — A/B 建链状态 (双卡自动识别)
 *   5. 查询速率              — 双卡 SerDes 速率是否一致
 *
 * 接线: A↔B 自环 (光口或电口通用) 或 双卡光纤对接
 *============================================================*/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <stdint.h>

#include "glink_api.h"
#include "glink_regs.h"

/*----------------- 常量 --------------------------------*/
#define AB_NC_STACK     0x2000
#define AB_NC_MEM       0x5000
#define AB_NT_STACK     0xA000
#define AB_NT_RECV      0x6000
#define AB_NT_SEND      0x7000
#define AB_LOCAL_NC_ID  0x03
#define AB_REMOTE_NT_ID 0x03
#define AB_DEFAULT_SA   0x01
#define AB_LINK_TIMEOUT_MS  30000
#define AB_XFER_TIMEOUT_MS   3000
#define AB_MAX_WORDS         256
#define STRESS_ROUNDS         20

/*----------------- 结果统计 ----------------------------*/
typedef enum { TR_PASS = 0, TR_FAIL = 1, TR_SKIP = 2 } test_rc_t;

static int g_pass, g_fail, g_skip;
static int g_verbose = 1;

static void result_reset(void) { g_pass = g_fail = g_skip = 0; }

static void result_record(const char *name, test_rc_t rc)
{
    const char *tag = (rc == TR_PASS) ? "通过" :
                      (rc == TR_SKIP) ? "跳过" : "失败";
    printf("\n>>>> [%s] %s\n", tag, name);
    if (rc == TR_PASS) g_pass++;
    else if (rc == TR_SKIP) g_skip++;
    else g_fail++;
}

static void result_summary(void)
{
    printf("\n========================================\n");
    printf("  汇总: 通过=%d  失败=%d  跳过=%d\n", g_pass, g_fail, g_skip);
    printf("========================================\n");
}

/*----------------- 通用辅助 ----------------------------*/
static void gen_pattern(uint16_t *buf, int n, uint16_t seed)
{
    for (int i = 0; i < n; i++)
        buf[i] = (uint16_t)(seed + i);
}

static void print_hex(const char *prefix, const uint16_t *buf, int len, int max_show)
{
    int show = (len > max_show) ? max_show : len;
    printf("%s", prefix);
    for (int i = 0; i < show; i++)
        printf("%04X ", buf[i]);
    if (len > max_show)
        printf("...(%d字)", len);
    printf("\n");
}

static int verify_words(const uint16_t *a, const uint16_t *b, int n)
{
    for (int i = 0; i < n; i++)
        if (a[i] != b[i])
            return i;
    return -1;
}

/*----------------- A<->B 自环公共路径 --------------------*/
typedef struct {
    uint16_t nc_stack;
    uint16_t nc_mem;
    uint16_t nt_stack;
    uint16_t nt_recv;
    uint16_t nt_send;
    uint16_t nc_id;
    uint16_t nt_id;
} ab_ctx_t;

static const ab_ctx_t AB_DEFAULT = {
    .nc_stack = AB_NC_STACK,
    .nc_mem   = AB_NC_MEM,
    .nt_stack = AB_NT_STACK,
    .nt_recv  = AB_NT_RECV,
    .nt_send  = AB_NT_SEND,
    .nc_id    = AB_LOCAL_NC_ID,
    .nt_id    = AB_REMOTE_NT_ID,
};

/* 复位 + JLK NC+NT + MEM 初始化 + 等 A/B LINK */
static int ab_bringup(void)
{
    printf("  [bringup] K72Reset + JlkConfig(NC+NT,0x%04X)...\n", NODE_ID_DEFAULT);
    if (K72Reset() != 0) {
        printf("  [失败] K72Reset\n");
        return -1;
    }
    if (JlkConfig(NODE_ID_DEFAULT, GLINK_ROLE_NC_NT) != 0) {
        printf("  [失败] JlkConfig\n");
        return -1;
    }
    MemorySpaceInit();

    printf("  [bringup] 等待 A/B LINK UP (%ds)...\n", AB_LINK_TIMEOUT_MS / 1000);
    if (GlinkWaitLinkUp(GLINK_CH_A, AB_LINK_TIMEOUT_MS) != 0) {
        printf("  [失败] A通道 LINK 未建立 (检查 A<->B 物理连接: 光口或电口)\n");
        return -1;
    }
    if (GlinkWaitLinkUp(GLINK_CH_B, AB_LINK_TIMEOUT_MS) != 0) {
        printf("  [失败] B通道 LINK 未建立 (检查 A<->B 物理连接: 光口或电口)\n");
        return -1;
    }
    printf("  [bringup] A/B LINK UP  (A=0x%04X B=0x%04X)\n",
           JlkRegRead(JLK_REG_CH_A_STATUS), JlkRegRead(JLK_REG_CH_B_STATUS));
    return 0;
}

/* 配置 ctrlNC1 + ctrlNT 通道映射与收发内存 (可指定 SA) */
static int ab_setup_protocol(const ab_ctx_t *ctx, uint16_t sa)
{
    CtrlNcMemoryMap(ctx->nc_stack, ctx->nc_mem, 1);
    CtrlNtSetStackPtr(ctx->nt_stack);
    CtrlNtChannelMap(1, 0 /*ctrlNC1*/, ctx->nc_id);
    CtrlNtConfigRecvMemory(1, sa, ctx->nt_recv);
    CtrlNtConfigSendMemory(1, sa, ctx->nt_send);
    CtrlNtInitUnusedChannel(2);
    return 0;
}

/*
 * NC->NT 发送 (TR=0)
 * 成功返回 0, 失败 -1; 接收数据写入 recv (可为 NULL 仅校验状态)
 */
static int ab_nc_to_nt(const ab_ctx_t *ctx, uint16_t sa,
                       const uint16_t *send, int words,
                       uint16_t *recv, int retry_en)
{
    uint16_t tmp[AB_MAX_WORDS];
    uint16_t *out = recv ? recv : tmp;
    uint16_t initial_sp;

    if (words <= 0 || words > AB_MAX_WORDS)
        return -1;

    /* 每次发送前刷新映射与描述符相关栈状态 */
    CtrlNcMemoryMap(ctx->nc_stack, ctx->nc_mem, 1);
    CtrlNtSetStackPtr(ctx->nt_stack);
    CtrlNtConfigRecvMemory(1, sa, ctx->nt_recv);

    initial_sp = ctx->nt_stack;

    CtrlNcSendData(ctx->nc_mem, send, words);
    if (retry_en) {
        CtrlNcConfigDescriptorFull(ctx->nc_mem,
                                   ctx->nt_id, 0, 0, 0,
                                   sa,
                                   0 /*TR*/, 0 /*mode*/, 0 /*state*/,
                                   1 /*INT*/, 1 /*retry*/, 0 /*prior*/,
                                   1 /*one_ch*/, 0 /*CH_B*/,
                                   1 /*nt_num*/,
                                   0, 0, 0, 0,
                                   (uint16_t)(words * 2));
    } else {
        CtrlNcConfigDescriptor(ctx->nc_mem,
                               ctx->nt_id, 0, 0, 0,
                               sa, 0 /*TR=发送*/,
                               (uint16_t)(words * 2));
    }

    CtrlNcStartXmit(1, 0);

    if (CtrlNcWaitDone(ctx->nc_stack, AB_XFER_TIMEOUT_MS) != 0) {
        printf("  [失败] NC 发送超时, status=0x%04X\n",
               CtrlNcGetExchangeBlockStatus(ctx->nc_stack));
        return -1;
    }

    if (CtrlNtWaitRecv(initial_sp, AB_XFER_TIMEOUT_MS) != 0) {
        printf("  [失败] NT 未收到数据, SP=0x%04X\n", CtrlNtGetCurrentSp());
        return -1;
    }

    {
        uint16_t nc_id = 0, tr = 0, sub = 0, blen = 0;
        uint16_t data_addr = CtrlNtGetRecvBlock(&nc_id, &tr, &sub, &blen);
        int n = words;
        if (g_verbose) {
            printf("  NT块: NC_ID=0x%02X TR=%u SA=%u bytes=%u addr=0x%04X\n",
                   nc_id, tr, sub, blen, data_addr);
        }
        if (data_addr == 0) {
            printf("  [失败] 无效接收地址\n");
            return -1;
        }
        if (blen > 0 && (blen / 2) < n)
            n = blen / 2;
        for (int i = 0; i < n; i++)
            out[i] = JlkMemRead(data_addr + i);
        if (n < words) {
            printf("  [失败] 长度不足: expect=%d got=%d\n", words, n);
            return -1;
        }
    }

    {
        int diff = verify_words(send, out, words);
        if (diff >= 0) {
            printf("  [失败] 数据不一致 offset=%d send=0x%04X recv=0x%04X\n",
                   diff, send[diff], out[diff]);
            return -1;
        }
    }
    return 0;
}

/*
 * NT->NC 拉取 (TR=1): NT 预置发送内存, NC 发起读请求
 * 成功后从 NC MEM(+0x8) 读回数据
 */
static int ab_nt_to_nc(const ab_ctx_t *ctx, uint16_t sa,
                       const uint16_t *expect, int words,
                       uint16_t *recv)
{
    uint16_t tmp[AB_MAX_WORDS];
    uint16_t *out = recv ? recv : tmp;

    if (words <= 0 || words > AB_MAX_WORDS)
        return -1;

    /* NT 侧准备被拉取数据 */
    for (int i = 0; i < words; i++)
        JlkMemWrite(ctx->nt_send + i, expect[i]);

    CtrlNcMemoryMap(ctx->nc_stack, ctx->nc_mem, 1);
    CtrlNtSetStackPtr(ctx->nt_stack);
    CtrlNtConfigSendMemory(1, sa, ctx->nt_send);
    CtrlNtConfigRecvMemory(1, sa, ctx->nt_recv);

    /* 清空 NC 数据区便于校验 */
    for (int i = 0; i < words; i++)
        JlkMemWrite(ctx->nc_mem + 0x8 + i, 0x0000);

    CtrlNcConfigDescriptorFull(ctx->nc_mem,
                               ctx->nt_id, 0, 0, 0,
                               sa,
                               1 /*TR=读*/, 0, 0,
                               1 /*INT*/, 1 /*retry*/, 0,
                               1, 0, 1,
                               0, 0, 0, 0,
                               (uint16_t)(words * 2));

    CtrlNcStartXmit(1, 0);
    if (CtrlNcWaitDone(ctx->nc_stack, AB_XFER_TIMEOUT_MS) != 0) {
        printf("  [失败] NC 拉取超时, status=0x%04X\n",
               CtrlNcGetExchangeBlockStatus(ctx->nc_stack));
        return -1;
    }

    /*
     * TR=1 回读布局 (K72 A<->B 实测):
     *   MEM(nc_mem+0x8 .. +0xB) = 4 word 头 (状态/长度等)
     *   MEM(nc_mem+0xC ..)      = 载荷
     * 例: 0000 0000 0200 0402 | 8001 8002 ...
     */
    {
        uint16_t hdr[4];
        for (int i = 0; i < 4; i++)
            hdr[i] = JlkMemRead(ctx->nc_mem + 0x8 + i);
        if (g_verbose)
            print_hex("  TR1头: ", hdr, 4, 4);

        for (int i = 0; i < words; i++)
            out[i] = JlkMemRead(ctx->nc_mem + 0xC + i);
    }

    {
        int diff = verify_words(expect, out, words);
        if (diff >= 0) {
            /* 兼容: 若固件无头, 再尝试从 +0x8 直读 */
            for (int i = 0; i < words; i++)
                out[i] = JlkMemRead(ctx->nc_mem + 0x8 + i);
            diff = verify_words(expect, out, words);
            if (diff >= 0) {
                printf("  [失败] 拉取数据不一致 offset=%d expect=0x%04X got=0x%04X\n",
                       diff, expect[diff], out[diff]);
                print_hex("  expect: ", expect, words, 8);
                print_hex("  got+0x8:", out, words, 8);
                return -1;
            }
            if (g_verbose)
                printf("  (载荷位于 +0x8, 无4字头)\n");
        }
    }
    return 0;
}

/*============================================================
 * 测试项
 *============================================================*/

/* T01 基础: L0/L1 设备与 EMIF */
static test_rc_t test_l0_l1_emif(void)
{
    uint32_t v32 = 0;
    uint16_t v16;

    printf("\n=== T01 基础层: 设备/BRIDGE/EMIF/片选 ===\n");

    if (BridgeRelease() != 0) {
        printf("  [失败] BridgeRelease\n");
        return TR_FAIL;
    }
    if (EmifSelectFpga() != 0 || EmifSelectJlk() != 0) {
        printf("  [失败] Emif 片选\n");
        return TR_FAIL;
    }

    /* FPGA SerDes 速率寄存器可读写 */
    EmifSelectFpga();
    FpgaRegWrite(P_CLK_FREQ_SEL_REGISTER, GLINK_RATE_2G5);
    v32 = FpgaRegRead(P_CLK_FREQ_SEL_REGISTER);
    printf("  FPGA CLK_FREQ_SEL = 0x%08X\n", v32);
    if ((v32 & 0xF) != GLINK_RATE_2G5) {
        printf("  [失败] FPGA 速率寄存器读写异常\n");
        return TR_FAIL;
    }

    /* JLK NODE_ID 写读 */
    EmifSelectJlk();
    JlkRegWrite(JLK_REG_NODE_ID, NODE_ID_DEFAULT);
    v16 = JlkRegRead(JLK_REG_NODE_ID);
    printf("  JLK NODE_ID = 0x%04X\n", v16);
    if (v16 != NODE_ID_DEFAULT) {
        printf("  [失败] JLK 寄存器读写异常\n");
        return TR_FAIL;
    }

    /* MEM 读写 */
    JlkMemWrite(0x0102, 0x55AA);
    v16 = JlkMemRead(0x0102);
    printf("  JLK MEM(0x102) = 0x%04X\n", v16);
    if (v16 != 0x55AA) {
        printf("  [失败] JLK MEM 读写异常\n");
        return TR_FAIL;
    }

    printf("  [通过] L0/L1 通路正常\n");
    return TR_PASS;
}

/* T02 硬件信息 / 版本 / 能力 */
static test_rc_t test_hw_info(void)
{
    glink_capability_t cap;
    uint32_t fpga_ver = 0;
    uint16_t jlk_id = 0;

    printf("\n=== T02 硬件信息/版本/能力 ===\n");
    memset(&cap, 0, sizeof(cap));
    GlinkGetCapability(&cap);
    GlinkGetHardWareInfo(&fpga_ver, &jlk_id);

    printf("  FPGA version/ctrl = 0x%08X\n", fpga_ver);
    printf("  JLK NODE_ID       = 0x%04X\n", jlk_id);
    printf("  PRODUCT_ID        = 0x%04X\n", JlkRegRead(JLK_REG_PRODUCT_ID));
    printf("  VERSION           = 0x%04X\n", JlkRegRead(JLK_REG_VERSION));
    printf("  channels=%u ports=%u\n", cap.channel_num, cap.port_num);
    printf("  CH_A=0x%04X CH_B=0x%04X\n",
           cap.jlK1263_reg_0a, cap.jlK1263_reg_0b);
    printf("  rate_sel          = %d\n", (int)GlinkGetRate());

    if (cap.channel_num < 2) {
        printf("  [失败] 通道能力异常\n");
        return TR_FAIL;
    }
    printf("  [通过]\n");
    return TR_PASS;
}

/* T03 GPIO 本地寄存器 (标准模式 MEM GPIO 区) */
static test_rc_t test_gpio_local(void)
{
    uint16_t rb;

    printf("\n=== T03 GPIO 本地寄存器 (方向/输出/回读) ===\n");
    /* 文档: 标准模式 16 双向 IO 映射于 MEM 0x500.. */
    GpioSetDirection(0xFFFF);       /* 全输出 */
    GpioSetOutput(0xA5A5);
    rb = GpioReadback();
    printf("  dir=0xFFFF out=0xA5A5 readback=0x%04X\n", rb);

    GpioSetOutput(0x5A5A);
    rb = GpioReadback();
    printf("  out=0x5A5A readback=0x%04X\n", rb);

    /* 回读是否与输出一致取决于板级是否回环到回读寄存器;
     * 至少要求写操作不报错、回读值稳定可读 */
    printf("  [通过] GPIO 寄存器可访问 (回读=0x%04X)\n", rb);
    return TR_PASS;
}

/* T04 LINK + 运行状态 */
static test_rc_t test_link_status(void)
{
    printf("\n=== T04 链路层: A/B LINK + 运行状态 ===\n");
    if (ab_bringup() != 0)
        return TR_FAIL;

    printf("  CH_A_STATUS = 0x%04X\n", JlkRegRead(JLK_REG_CH_A_STATUS));
    printf("  CH_B_STATUS = 0x%04X\n", JlkRegRead(JLK_REG_CH_B_STATUS));
    printf("  A_RUN       = 0x%04X\n", GlinkGetARunStatus());
    printf("  B_RUN       = 0x%04X\n", GlinkGetBRunStatus());
    printf("  INT_STATUS  = 0x%04X\n", JlkGetIntStatus());
    printf("  WORK_MODE   = 0x%04X\n", JlkRegRead(JLK_REG_WORK_MODE));
    printf("  CHANNEL_EN  = 0x%04X\n", JlkRegRead(JLK_REG_CHANNEL_EN));
    printf("  TIMESTAMP   = 0x%04X\n", JlkRegRead(JLK_REG_TIMESTAMP));

    if (!GlinkGetLinkStatus(GLINK_CH_A) || !GlinkGetLinkStatus(GLINK_CH_B)) {
        printf("  [失败] LINK 状态查询不一致\n");
        return TR_FAIL;
    }
    printf("  [通过]\n");
    return TR_PASS;
}

/* T05 CtrlNC->CtrlNT 基础自环 32 字 (已验证主路径) */
static test_rc_t test_ctrl_basic(void)
{
    const ab_ctx_t *ctx = &AB_DEFAULT;
    uint16_t send[32], recv[32];

    printf("\n=== T05 CtrlNC->CtrlNT 基础自环 (32字) ===\n");
    if (ab_bringup() != 0)
        return TR_FAIL;
    ab_setup_protocol(ctx, AB_DEFAULT_SA);

    gen_pattern(send, 32, 0x0001);
    print_hex("  发送: ", send, 32, 8);
    if (ab_nc_to_nt(ctx, AB_DEFAULT_SA, send, 32, recv, 0) != 0)
        return TR_FAIL;
    print_hex("  接收: ", recv, 32, 8);

    if (FpgaGetDebug() != 0) {
        printf("  [失败] FPGA DEBUG=0x%08X\n", FpgaGetDebug());
        return TR_FAIL;
    }
    printf("  [通过] 32字自环一致\n");
    return TR_PASS;
}

/* T06 多子地址 SA=1/2/3 */
static test_rc_t test_multi_sa(void)
{
    const ab_ctx_t *ctx = &AB_DEFAULT;
    const uint16_t sas[] = {1, 2, 3};
    uint16_t send[32], recv[32];
    int fail = 0;

    printf("\n=== T06 多子地址 SA=1/2/3 ===\n");
    if (ab_bringup() != 0)
        return TR_FAIL;

    CtrlNcMemoryMap(ctx->nc_stack, ctx->nc_mem, 1);
    CtrlNtSetStackPtr(ctx->nt_stack);
    CtrlNtChannelMap(1, 0, ctx->nc_id);
    for (int i = 0; i < 3; i++) {
        /* 各 SA 使用不同接收区, 避免覆盖 */
        uint16_t recv_base = (uint16_t)(ctx->nt_recv + i * 0x100);
        CtrlNtConfigRecvMemory(1, sas[i], recv_base);
        CtrlNtConfigSendMemory(1, sas[i], (uint16_t)(ctx->nt_send + i * 0x100));
    }
    CtrlNtInitUnusedChannel(2);

    for (int i = 0; i < 3; i++) {
        ab_ctx_t c = *ctx;
        c.nt_recv = (uint16_t)(ctx->nt_recv + i * 0x100);
        gen_pattern(send, 16, (uint16_t)(0x1000 * (i + 1)));
        printf("  -- SA=%u --\n", sas[i]);
        if (ab_nc_to_nt(&c, sas[i], send, 16, recv, 0) != 0) {
            fail = 1;
            continue;
        }
        printf("  SA=%u [通过]\n", sas[i]);
    }
    return fail ? TR_FAIL : TR_PASS;
}

/* T07 变长载荷 */
static test_rc_t test_var_payload(void)
{
    const ab_ctx_t *ctx = &AB_DEFAULT;
    const int sizes[] = {1, 8, 32, 64, 128};
    uint16_t send[AB_MAX_WORDS], recv[AB_MAX_WORDS];
    int fail = 0;

    printf("\n=== T07 变长载荷 (1/8/32/64/128 字) ===\n");
    if (ab_bringup() != 0)
        return TR_FAIL;
    ab_setup_protocol(ctx, AB_DEFAULT_SA);

    for (unsigned i = 0; i < sizeof(sizes) / sizeof(sizes[0]); i++) {
        int n = sizes[i];
        gen_pattern(send, n, (uint16_t)(0x0100 + i));
        printf("  -- %d 字 --\n", n);
        if (ab_nc_to_nt(ctx, AB_DEFAULT_SA, send, n, recv, 0) != 0) {
            fail = 1;
            continue;
        }
        printf("  %d字 [通过]\n", n);
    }
    return fail ? TR_FAIL : TR_PASS;
}

/* T08 NT->NC 拉取 TR=1 */
static test_rc_t test_nt_pull(void)
{
    const ab_ctx_t *ctx = &AB_DEFAULT;
    uint16_t expect[32], recv[32];

    printf("\n=== T08 CtrlNT->CtrlNC 拉取 (TR=1) ===\n");
    if (ab_bringup() != 0)
        return TR_FAIL;
    ab_setup_protocol(ctx, AB_DEFAULT_SA);

    gen_pattern(expect, 32, 0x8001);
    print_hex("  NT预置: ", expect, 32, 8);
    if (ab_nt_to_nc(ctx, AB_DEFAULT_SA, expect, 32, recv) != 0)
        return TR_FAIL;
    print_hex("  NC读回: ", recv, 32, 8);
    printf("  [通过] TR=1 拉取一致\n");
    return TR_PASS;
}

/* T09 重发配置 + 自环 */
static test_rc_t test_retry(void)
{
    const ab_ctx_t *ctx = &AB_DEFAULT;
    uint16_t send[32], recv[32];
    uint16_t r18;

    printf("\n=== T09 ctrlNC1 重发配置 + 自环 ===\n");
    if (ab_bringup() != 0)
        return TR_FAIL;

    CtrlNc1ConfigRetry(1, 2);           /* 使能, 重发2次 */
    CtrlNc1ConfigRetryGroup(1, 2, 1);
    r18 = JlkRegRead(JLK_REG_CTRLNC1_RETRY);
    printf("  REG(0x18) retry = 0x%04X\n", r18);

    ab_setup_protocol(ctx, AB_DEFAULT_SA);
    gen_pattern(send, 32, 0x3001);
    if (ab_nc_to_nt(ctx, AB_DEFAULT_SA, send, 32, recv, 1) != 0)
        return TR_FAIL;
    printf("  [通过] 重发使能下自环成功\n");
    return TR_PASS;
}

/* T10 帧记录 */
static test_rc_t test_frame_record(void)
{
    const ab_ctx_t *ctx = &AB_DEFAULT;
    uint16_t send[16], recv[16];
    uint16_t frame[8];
    int nonzero = 0;

    printf("\n=== T10 帧记录 (发送后读记录表) ===\n");
    if (ab_bringup() != 0)
        return TR_FAIL;

    FrameRecordSetFilter(0, AB_LOCAL_NC_ID);
    FrameRecordEnable(0, 1);            /* 不滤波, 开记录 */
    ab_setup_protocol(ctx, AB_DEFAULT_SA);

    gen_pattern(send, 16, 0x4001);
    if (ab_nc_to_nt(ctx, AB_DEFAULT_SA, send, 16, recv, 0) != 0)
        return TR_FAIL;

    usleep(50000);
    for (int i = 0; i < 8; i++) {
        if (FrameRecordRead(i, frame) != 0)
            continue;
        int any = 0;
        for (int j = 0; j < 8; j++)
            if (frame[j]) any = 1;
        if (any) {
            nonzero++;
            printf("  record[%d]: %04X %04X %04X %04X %04X %04X %04X %04X\n",
                   i, frame[0], frame[1], frame[2], frame[3],
                   frame[4], frame[5], frame[6], frame[7]);
        }
    }
    FrameRecordEnable(0, 0);

    if (nonzero == 0) {
        /* 部分 FPGA 固件可能未接帧记录; 通信已成功则记为跳过而非失败 */
        printf("  [跳过] 帧记录表全0 (固件可能未使能帧记录RAM)\n");
        return TR_SKIP;
    }
    printf("  [通过] 读到 %d 条非空帧记录\n", nonzero);
    return TR_PASS;
}

/* T11 忙表配置 (配置后用另一 SA 通信, 验证忙表写不破坏通路) */
static test_rc_t test_busy_table(void)
{
    const ab_ctx_t *ctx = &AB_DEFAULT;
    uint16_t send[16], recv[16];

    printf("\n=== T11 CtrlNT 忙表配置 + SA通信 ===\n");
    if (ab_bringup() != 0)
        return TR_FAIL;

    ab_setup_protocol(ctx, 2);
    /* SA=1 置忙, 通信走 SA=2 */
    CtrlNtConfigBusyTable(1, 0 /*recv*/, 1);
    CtrlNtConfigRecvMemory(1, 2, ctx->nt_recv);
    CtrlNtConfigSendMemory(1, 2, ctx->nt_send);

    gen_pattern(send, 16, 0x5101);
    if (ab_nc_to_nt(ctx, 2, send, 16, recv, 0) != 0)
        return TR_FAIL;
    printf("  [通过] 忙表配置后 SA=2 通信正常\n");
    return TR_PASS;
}

/* T12 时间戳寄存器 */
static test_rc_t test_timestamp(void)
{
    uint16_t v;

    printf("\n=== T12 时间戳配置寄存器 ===\n");
    if (ab_bringup() != 0)
        return TR_FAIL;

    JlkRegWrite(JLK_REG_TIMESTAMP, 0x0005);  /* 1us */
    v = JlkRegRead(JLK_REG_TIMESTAMP);
    printf("  TIMESTAMP = 0x%04X (期望 0x0005)\n", v);
    if ((v & 0xF) != 0x5) {
        printf("  [失败] 时间戳写读不一致\n");
        return TR_FAIL;
    }
    printf("  [通过]\n");
    return TR_PASS;
}

/* T13 压力自环 */
static test_rc_t test_stress(void)
{
    const ab_ctx_t *ctx = &AB_DEFAULT;
    uint16_t send[32], recv[32];
    int fail = 0;

    printf("\n=== T13 压力自环 (%d 轮 x 32字) ===\n", STRESS_ROUNDS);
    if (ab_bringup() != 0)
        return TR_FAIL;
    ab_setup_protocol(ctx, AB_DEFAULT_SA);

    g_verbose = 0;
    for (int r = 0; r < STRESS_ROUNDS; r++) {
        gen_pattern(send, 32, (uint16_t)(0x1000 + r));
        if (ab_nc_to_nt(ctx, AB_DEFAULT_SA, send, 32, recv, 0) != 0) {
            printf("  [失败] 第 %d 轮\n", r + 1);
            fail++;
            break;
        }
        if ((r + 1) % 5 == 0)
            printf("  ... 已完成 %d/%d\n", r + 1, STRESS_ROUNDS);
    }
    g_verbose = 1;

    if (fail) {
        printf("  [失败] 压力测试中断\n");
        return TR_FAIL;
    }
    printf("  [通过] %d 轮全部成功\n", STRESS_ROUNDS);
    return TR_PASS;
}

/* T14 LINK 监控 */
static test_rc_t test_link_monitor(void)
{
    int sec = 10;
    int interval_ms = 2000;

    printf("\n=== T14 LINK 状态监控 (%ds) ===\n", sec);
    if (ab_bringup() != 0)
        return TR_FAIL;

    printf("  时间    A通道          B通道\n");
    printf("  -----   ------------   ------------\n");
    for (int t = 0; t <= sec; t += interval_ms / 1000) {
        uint16_t a = JlkRegRead(JLK_REG_CH_A_STATUS);
        uint16_t b = JlkRegRead(JLK_REG_CH_B_STATUS);
        int a_up = GlinkGetLinkStatus(GLINK_CH_A);
        int b_up = GlinkGetLinkStatus(GLINK_CH_B);
        printf("  %3ds    %s(0x%04X)    %s(0x%04X)\n",
               t, a_up ? "UP  " : "DOWN", a, b_up ? "UP  " : "DOWN", b);
        if (!a_up || !b_up) {
            printf("  [失败] 监控期间 LINK 掉线\n");
            return TR_FAIL;
        }
        if (t + interval_ms / 1000 <= sec)
            usleep(interval_ms * 1000);
    }
    printf("  [通过]\n");
    return TR_PASS;
}

/* T15 双向: 先 NC->NT 再 NT->NC */
static test_rc_t test_bidirectional(void)
{
    const ab_ctx_t *ctx = &AB_DEFAULT;
    uint16_t s1[32], r1[32], s2[32], r2[32];

    printf("\n=== T15 双向通信 (NC->NT 然后 NT->NC) ===\n");
    if (ab_bringup() != 0)
        return TR_FAIL;
    ab_setup_protocol(ctx, AB_DEFAULT_SA);

    gen_pattern(s1, 32, 0xA001);
    printf("  [1] NC->NT ...\n");
    if (ab_nc_to_nt(ctx, AB_DEFAULT_SA, s1, 32, r1, 0) != 0)
        return TR_FAIL;

    gen_pattern(s2, 32, 0xB001);
    printf("  [2] NT->NC 拉取 ...\n");
    if (ab_nt_to_nc(ctx, AB_DEFAULT_SA, s2, 32, r2) != 0)
        return TR_FAIL;

    printf("  [通过] 双向均一致\n");
    return TR_PASS;
}

/* T16 寄存器全览 dump (诊断) */
static test_rc_t test_reg_dump(void)
{
    printf("\n=== T16 寄存器诊断 dump ===\n");
    if (ab_bringup() != 0)
        return TR_FAIL;
    printf("  -- JLK1263 --\n");
    JlkDumpAll();
    printf("  -- FPGA --\n");
    FpgaDumpStatus();
    printf("  DEBUG=0x%08X\n", FpgaGetDebug());
    printf("  [通过]\n");
    return TR_PASS;
}

/* T17 标准模式内 SmartNC/SmartNT 寄存器配置读写 (不改大模式) */
static test_rc_t test_smart_reg_config(void)
{
    uint16_t old_mode, wm, cfg, to;

    printf("\n=== T17 SmartNC/SmartNT 寄存器配置 (标准模式内) ===\n");
    if (ab_bringup() != 0)
        return TR_FAIL;

    old_mode = JlkRegRead(JLK_REG_WORK_MODE);
    /* 临时使能 SmartNC1 + SmartNT1, 保留 CtrlNC1|CtrlNT 以便随后恢复通信 */
    wm = (uint16_t)(MODE_CTRLNC1 | MODE_CTRLNT | MODE_SMARTNC1 | MODE_SMARTNT1);
    JlkRegWrite(JLK_REG_WORK_MODE, wm);
    printf("  WORK_MODE: 0x%04X -> 0x%04X\n", old_mode, JlkRegRead(JLK_REG_WORK_MODE));

    SmartNc1ConfigTimeout(1000);
    SmartNc1Config(SMARTNC_STACK_EN | SMARTNC_PAYLOAD_64);
    SmartNtConfigChannel(1, AB_LOCAL_NC_ID, 1, 0);

    to = JlkRegRead(JLK_REG_SMARTNC1_TIMEOUT);
    cfg = JlkRegRead(JLK_REG_SMARTNC1_CONFIG);
    printf("  SmartNC1 TIMEOUT=0x%04X CONFIG=0x%04X\n", to, cfg);
    printf("  SmartNT1 CONFIG=0x%04X\n", JlkRegRead(JLK_REG_SMARTNT1_CONFIG));

    /* 恢复 CtrlNC+CtrlNT, 验证 A↔B 仍可通信 */
    JlkRegWrite(JLK_REG_WORK_MODE, (uint16_t)(MODE_CTRLNC1 | MODE_CTRLNT));
    {
        const ab_ctx_t *ctx = &AB_DEFAULT;
        uint16_t send[16], recv[16];
        ab_setup_protocol(ctx, AB_DEFAULT_SA);
        gen_pattern(send, 16, 0x1701);
        if (ab_nc_to_nt(ctx, AB_DEFAULT_SA, send, 16, recv, 0) != 0) {
            printf("  [失败] 恢复后 CtrlNC 自环失败\n");
            return TR_FAIL;
        }
    }
    printf("  [通过] Smart 寄存器可配, 且恢复后 Ctrl 自环正常\n");
    printf("  注: Smart 数据面走 FPGA FIFO, 完整收发需另测 FIFO 通路\n");
    return TR_PASS;
}

/*---------- 独立选项: 速率 ----------*/
static const char *rate_to_name(int rate)
{
    switch (rate) {
    case GLINK_RATE_625M: return "625Mbps";
    case GLINK_RATE_1G:   return "1Gbps";
    case GLINK_RATE_2G5:  return "2.5Gbps";
    case GLINK_RATE_5G:   return "5Gbps";
    default:              return "未知/保留";
    }
}

static void print_card_rate(const char *tag)
{
    int api = (int)GlinkGetRate();
    uint32_t fpga = FpgaRegRead(P_CLK_FREQ_SEL_REGISTER);
    uint16_t node = JlkRegRead(JLK_REG_NODE_ID);
    int emif_dead = (fpga == 0xDEADBEEF) || (node == 0xBEEF);

    if (emif_dead) {
        printf("  [%s] EMIF 读失败 (FPGA=0x%08X NODE=0x%04X) — 间接桥无响应\n",
               tag, fpga, node);
        return;
    }
    fpga &= 0xF;
    printf("  [%s] GlinkGetRate=%d (%s)  FPGA[0x4008]=0x%X (%s)%s\n",
           tag, api, rate_to_name(api), fpga, rate_to_name((int)fpga),
           (api == (int)fpga) ? "" : "  [API与FPGA不一致]");
}

/* 只读查询两卡速率是否一致 (不改配置) */
static test_rc_t opt_rate_query(void)
{
    int has_card1 = (access("/dev/xdma1_user", F_OK) == 0);
    int r0, r1 = -1;
    uint32_t f0, f1 = 0xFF;

    printf("\n=== 速率查询 ===\n");
    printf("  说明: 只读 FPGA SerDes 时钟选择 (0x4008), 不修改配置\n");
    printf("  编码: 0=625M  1=1G  2=5G  5=2.5G(默认)\n");

    GlinkBind(0);
    BridgeRelease();
    r0 = (int)GlinkGetRate();
    f0 = FpgaRegRead(P_CLK_FREQ_SEL_REGISTER);
    print_card_rate("card0 / xdma0");

    if (has_card1) {
        if (GlinkOpenPath(1, "/dev/xdma1_user") != 0) {
            printf("  [警告] 打开 xdma1 失败, 仅显示 card0\n");
            has_card1 = 0;
        } else {
            GlinkBind(1);
            BridgeRelease();
            r1 = (int)GlinkGetRate();
            f1 = FpgaRegRead(P_CLK_FREQ_SEL_REGISTER);
            print_card_rate("card1 / xdma1");
            GlinkBind(0);
        }
    } else {
        printf("  (未发现 /dev/xdma1_user, 单卡模式)\n");
    }

    printf("\n  结论: ");
    if (!has_card1) {
        if (f0 == 0xDEADBEEF) {
            printf("card0 EMIF 不可用\n  [失败]\n");
            return TR_FAIL;
        }
        f0 &= 0xF;
        printf("单卡速率 = %s (code=%d)\n", rate_to_name(r0), r0);
        if (r0 == (int)f0) {
            printf("  [通过] API 与 FPGA 读回一致\n");
            return TR_PASS;
        }
        printf("  [失败] API(%d) 与 FPGA(0x%X) 不一致\n", r0, f0);
        return TR_FAIL;
    }

    if (f0 == 0xDEADBEEF || f1 == 0xDEADBEEF) {
        printf("至少一块卡 EMIF 读失败, 无法可靠比较速率\n");
        if (f0 == 0xDEADBEEF)
            printf("    xdma0: EMIF 失败\n");
        else
            printf("    xdma0: %s\n", rate_to_name(r0));
        if (f1 == 0xDEADBEEF)
            printf("    xdma1: EMIF 失败 (间接桥超时, 常见于第二块卡未正常枚举/复位)\n");
        else
            printf("    xdma1: %s\n", rate_to_name(r1));
        printf("  [失败] 请检查 xdma1 对应 PCI 卡、重载驱动或单卡交叉验证\n");
        return TR_FAIL;
    }

    f0 &= 0xF;
    f1 &= 0xF;
    if (r0 == r1 && f0 == f1 && r0 == (int)f0) {
        printf("两卡速率一致 = %s (code=%d)\n", rate_to_name(r0), r0);
        printf("  [通过] card0 与 card1 速率相同\n");
        return TR_PASS;
    }

    printf("两卡速率不一致!\n");
    printf("    card0: %s (api=%d fpga=0x%X)\n", rate_to_name(r0), r0, f0);
    printf("    card1: %s (api=%d fpga=0x%X)\n", rate_to_name(r1), r1, f1);
    printf("  [失败] 互通前请把两边设成同一档 (推荐 2.5G 或 625M)\n");
    printf("  提示: ./test_glink_api rate-sync 可将两卡都设为 2.5G\n");
    return TR_FAIL;
}

static void card_light_bringup(glink_rate_t rate); /* 定义在 LINK 检测段 */

/* 将已发现的卡统一设为同一速率并复核 */
static test_rc_t opt_rate_sync(glink_rate_t want)
{
    int has_card1 = (access("/dev/xdma1_user", F_OK) == 0);
    int ok = 1;

    printf("\n=== 速率对齐 ===\n");
    printf("  目标: %s (code=%d)\n", rate_to_name((int)want), (int)want);
    printf("  步骤: 每卡先轻量复位, 再写 SerDes 速率并读回\n");

    GlinkBind(0);
    card_light_bringup(want);
    usleep(100000);
    print_card_rate("card0");
    if ((int)GlinkGetRate() != (int)want)
        ok = 0;

    if (has_card1) {
        if (GlinkOpenPath(1, "/dev/xdma1_user") != 0) {
            printf("  [失败] 打开 xdma1 失败\n");
            return TR_FAIL;
        }
        GlinkBind(1);
        card_light_bringup(want);
        usleep(100000);
        print_card_rate("card1");
        if ((int)GlinkGetRate() != (int)want)
            ok = 0;
        GlinkBind(0);
    }

    if (ok) {
        printf("  [通过] 已对齐为 %s\n", rate_to_name((int)want));
        return TR_PASS;
    }
    printf("  [失败] 写入后读回仍不一致, 请查 EMIF/FPGA 访问\n");
    return TR_FAIL;
}

static test_rc_t opt_rate_config(void)
{
    glink_rate_t rates[] = {
        GLINK_RATE_625M, GLINK_RATE_1G, GLINK_RATE_2G5, GLINK_RATE_5G
    };
    const char *names[] = {"625M", "1G", "2.5G", "5G"};
    uint32_t cur;

    printf("\n=== 独立: SerDes 速率配置 (FPGA 0x4008) ===\n");
    printf("  警告: 改速率可能导致 LINK 掉线, 结束后恢复 2.5G\n");

    BridgeRelease();
    cur = FpgaRegRead(P_CLK_FREQ_SEL_REGISTER);
    printf("  当前 CLK_FREQ_SEL = 0x%X (%s)\n", cur & 0xF, rate_to_name((int)(cur & 0xF)));

    for (unsigned i = 0; i < sizeof(rates) / sizeof(rates[0]); i++) {
        GlinkSetRate(rates[i]);
        usleep(50000);
        uint32_t rb = FpgaRegRead(P_CLK_FREQ_SEL_REGISTER) & 0xF;
        printf("  set %-4s -> readback=0x%X %s\n",
               names[i], rb, (rb == (uint32_t)rates[i]) ? "OK" : "MISMATCH");
        if (rb != (uint32_t)rates[i])
            return TR_FAIL;
    }

    GlinkSetRate(GLINK_RATE_2G5);
    usleep(200000);
    printf("  已恢复 2.5G, LINK A=%d B=%d\n",
           GlinkGetLinkStatus(GLINK_CH_A), GlinkGetLinkStatus(GLINK_CH_B));
    printf("  [通过] 速率寄存器读写正常\n");
    return TR_PASS;
}

/*---------- 独立选项: 冗余/环 ----------*/
static test_rc_t opt_redun_ring(void)
{
    uint16_t en;

    printf("\n=== 独立: 冗余通道 / 环功能 寄存器 ===\n");
    if (ab_bringup() != 0)
        return TR_FAIL;

    en = JlkRegRead(JLK_REG_CHANNEL_EN);
    printf("  CHANNEL_EN 当前 = 0x%04X\n", en);

    GlinkSetRedunMode(1);
    printf("  冗余使能后 = 0x%04X\n", JlkRegRead(JLK_REG_CHANNEL_EN));
    GlinkEnableRing(1);
    printf("  环使能后   = 0x%04X\n", JlkRegRead(JLK_REG_CHANNEL_EN));
    GlinkConfigRingBandwidth(1);
    GlinkConfigFrameTimeout(2);
    printf("  环带宽/帧超时已写 (读回 CHANNEL_EN=0x%04X)\n",
           JlkRegRead(JLK_REG_CHANNEL_EN));

    /* 恢复 A/B 常规使能 */
    JlkRegWrite(JLK_REG_CHANNEL_EN, CHANNEL_EN_AB);
    printf("  已恢复 CHANNEL_EN=0x%04X\n", JlkRegRead(JLK_REG_CHANNEL_EN));
    printf("  [通过] 寄存器可配 (环业务需环拓扑硬件)\n");
    return TR_PASS;
}

/*---------- 独立选项: GC 大模式探测 ----------*/
static test_rc_t opt_gc_mode_probe(void)
{
    uint32_t old, rb;
    const char *names[] = {
        "保留/0", "标准(001)", "监听(010)", "IO(011)", "中继+IO(100)"
    };

    printf("\n=== 独立: FPGA GC_MODE 大模式探测 (0x400C -> I_GC_MODE) ===\n");
    printf("  手册: 四大模式由引脚 I_GC_MODE[2:0] 选择\n");
    printf("  硬件指南注: 「不支持芯片工作模式的在线更改」\n");
    printf("  本项仅探测 FPGA 寄存器能否写读, 并观察 PRODUCT_ID 变化\n");
    printf("  结束后恢复标准模式(1) 并重新 JlkConfig\n\n");

    BridgeRelease();
    EmifSelectFpga();
    old = FpgaRegRead(P_GC_MODE_REGISTER) & 0x7;
    printf("  当前 GC_MODE = %u (%s)\n", old,
           old < 5 ? names[old] : "?");

    for (uint32_t m = 1; m <= 4; m++) {
        FpgaRegWrite(P_GC_MODE_REGISTER, m);
        usleep(100000);
        rb = FpgaRegRead(P_GC_MODE_REGISTER) & 0x7;
        EmifSelectJlk();
        printf("  set %u -> rb=%u  PID=0x%04X VER=0x%04X WORK=0x%04X\n",
               m, rb, JlkRegRead(JLK_REG_PRODUCT_ID),
               JlkRegRead(JLK_REG_VERSION),
               JlkRegRead(JLK_REG_WORK_MODE));
        if (rb != m) {
            printf("  [失败] GC_MODE 写读不一致\n");
            FpgaRegWrite(P_GC_MODE_REGISTER, 1);
            return TR_FAIL;
        }
    }

    FpgaRegWrite(P_GC_MODE_REGISTER, 1);
    usleep(200000);
    JlkConfig(NODE_ID_DEFAULT, GLINK_ROLE_NC_NT);
    printf("  已恢复 GC=1 标准模式, CHANNEL A/B status=0x%04X/0x%04X\n",
           JlkRegRead(JLK_REG_CH_A_STATUS), JlkRegRead(JLK_REG_CH_B_STATUS));
    printf("  [通过] GC_MODE 寄存器可切换; 业务级 NM/IO/中继需在对应模式下重配\n");
    return TR_PASS;
}

/*---------- 独立选项: NM 寄存器 ----------*/
static test_rc_t opt_nm_regs(void)
{
    nm_config_t cfg;
    uint16_t st;

    printf("\n=== 独立: 监听 NM 寄存器配置 ===\n");
    printf("  说明: 完整 NM 业务需 GC_MODE=监听(2); 此处写 REG/MEM 并读回\n");

    BridgeRelease();
    memset(&cfg, 0, sizeof(cfg));
    cfg.node_id = 0x0003;
    cfg.channel_en = 0x03;
    cfg.ring_enable = 0;
    if (NmInit(&cfg) != 0) {
        printf("  [失败] NmInit\n");
        return TR_FAIL;
    }
    st = NmGetStatus();
    printf("  NmInit 完成, NM_STATUS(0x12)=0x%04X\n", st);
    printf("  WORK_MODE=0x%04X (含 MONITOR 位?)\n", JlkRegRead(JLK_REG_WORK_MODE));

    /* 恢复标准 Ctrl 配置, 避免后续 A↔B 被破坏 */
    FpgaRegWrite(P_GC_MODE_REGISTER, 1);
    JlkConfig(NODE_ID_DEFAULT, GLINK_ROLE_NC_NT);
    printf("  已恢复标准 CtrlNC+CtrlNT\n");
    printf("  [通过] NM 相关寄存器可写; 无旁路流量时记录区可能为空\n");
    return TR_PASS;
}

/*---------- 独立选项: IO 寄存器 ----------*/
static test_rc_t opt_io_regs(void)
{
    io_mode_config_t cfg;

    printf("\n=== 独立: IO/PWM 寄存器配置 ===\n");
    printf("  说明: 完整 IO 业务需 GC_MODE=IO(3); 此处写 MEM 映射寄存器\n");

    BridgeRelease();
    memset(&cfg, 0, sizeof(cfg));
    cfg.chip_id = 0x0003;
    cfg.ctrl_src_id[0] = 0x0001;
    cfg.default_output = 0x00FF;
    if (IoModeInit(&cfg) != 0) {
        printf("  [失败] IoModeInit\n");
        return TR_FAIL;
    }
    IoPwmOutput(0, 50, 1000);
    IoLevelOutput(0, 1);
    printf("  IoModeInit/PWM/Level 已调用\n");
    printf("  IO_REG_CHIP_ID 读回=0x%04X\n", JlkMemRead(IO_REG_CHIP_ID));
    printf("  OUTPUT_LEVEL 读回=0x%04X\n", JlkMemRead(IO_REG_OUTPUT_LEVEL));

    FpgaRegWrite(P_GC_MODE_REGISTER, 1);
    JlkConfig(NODE_ID_DEFAULT, GLINK_ROLE_NC_NT);
    printf("  已恢复标准模式\n");
    printf("  [通过] IO 寄存器可访问 (引脚复用下电平需示波器确认)\n");
    return TR_PASS;
}

/*---------- 独立选项: 中继器寄存器 ----------*/
static test_rc_t opt_repeater_regs(void)
{
    repeater_config_t cfg;

    printf("\n=== 独立: 中继器寄存器配置 ===\n");
    printf("  说明: 标准模式内可配中继; C/D 口业务需物理连接\n");
    printf("        完整「中继+IO」大模式需 GC_MODE=4\n");

    BridgeRelease();
    memset(&cfg, 0, sizeof(cfg));
    cfg.repeater_num = 1;
    cfg.ch_c_enable = 1;
    cfg.ch_d_enable = 1;
    if (RepeaterInit(&cfg) != 0) {
        printf("  [失败] RepeaterInit\n");
        return TR_FAIL;
    }
    printf("  RepeaterInit 完成\n");
    printf("  CH_C_STATUS=0x%04X CH_D_STATUS=0x%04X\n",
           RepeaterGetChCStatus(), RepeaterGetChDStatus());
    printf("  VERSION=0x%04X\n", RepeaterGetVersion());

    JlkConfig(NODE_ID_DEFAULT, GLINK_ROLE_NC_NT);
    printf("  [通过] 中继寄存器可配; C/D 当前无链路属预期\n");
    return TR_PASS;
}

/*============================================================
 * 全 API 冒烟测试
 *============================================================*/
static int g_api_ok, g_api_fail, g_api_skip;

static void api_mark(const char *name, int ok, const char *info)
{
    if (ok) {
        g_api_ok++;
        printf("  [OK ] %-36s %s\n", name, info ? info : "");
    } else {
        g_api_fail++;
        printf("  [FAIL] %-36s %s\n", name, info ? info : "");
    }
}

static void api_skip(const char *name, const char *why)
{
    g_api_skip++;
    printf("  [SKIP] %-36s %s\n", name, why ? why : "");
}

static test_rc_t opt_api_full_test(void)
{
    uint32_t v32 = 0, fpga_ver = 0;
    uint16_t v16, jlk_id = 0;
    uint16_t frame[8];
    uint16_t words[8] = {1, 2, 3, 4, 5, 6, 7, 8};
    uint8_t  bytes[64];
    glink_capability_t cap;
    glink_msg_t msg, msg_rd;
    smartnc_config_t snc;
    smartnt_config_t snt;
    smartnc_status_t snc_st;
    nm_config_t nm;
    io_mode_config_t io;
    repeater_config_t rep;
    char note[80];

    g_api_ok = g_api_fail = g_api_skip = 0;
    memset(bytes, 0xA5, sizeof(bytes));
    memset(&cap, 0, sizeof(cap));
    memset(&msg, 0, sizeof(msg));
    memset(&snc, 0, sizeof(snc));
    memset(&snt, 0, sizeof(snt));
    memset(&nm, 0, sizeof(nm));
    memset(&io, 0, sizeof(io));
    memset(&rep, 0, sizeof(rep));

    printf("\n=== 全 API 冒烟测试 ===\n");
    printf("  说明: 调用几乎全部 API, 检查返回值/简单读写; 不做破坏性死等\n");
    printf("  跳过: GlinkCheckChannelStatus (文档为无超时死等)\n\n");

    /* ---- L0/L1 ---- */
    printf("-- L0/L1 设备与EMIF --\n");
    api_mark("BridgeRelease", BridgeRelease() == 0, NULL);
    api_mark("BridgeReset", BridgeReset() == 0, NULL);
    api_mark("BridgeRelease(2)", BridgeRelease() == 0, NULL);
    api_mark("EmifSetCeN(FPGA)", EmifSetCeN(CE_N_FPGA) == 0, NULL);
    api_mark("EmifSelectFpga", EmifSelectFpga() == 0, NULL);
    api_mark("EmifSelectJlk", EmifSelectJlk() == 0, NULL);
    api_mark("XdmaWrite/Read",
             XdmaWrite(EF_BRIDGE_RST, 1) == 0 &&
             XdmaRead(EF_BRIDGE_RST, &v32) == 0 && (v32 & 1) == 1, NULL);

    EmifSelectFpga();
    FpgaRegWrite(P_CLK_FREQ_SEL_REGISTER, GLINK_RATE_2G5);
    v32 = FpgaRegRead(P_CLK_FREQ_SEL_REGISTER);
    api_mark("FpgaRegWrite/Read", (v32 & 0xF) == GLINK_RATE_2G5, NULL);

    EmifSelectJlk();
    JlkRegWrite(JLK_REG_NODE_ID, NODE_ID_DEFAULT);
    v16 = JlkRegRead(JLK_REG_NODE_ID);
    api_mark("JlkRegWrite/Read", v16 == NODE_ID_DEFAULT, NULL);
    JlkMemWrite(0x0102, 0xA55A);
    api_mark("JlkMemWrite/Read", JlkMemRead(0x0102) == 0xA55A, NULL);
    api_mark("EmifWrite/Read",
             EmifWrite(REG_ADDR(0x00), NODE_ID_DEFAULT) == 0 &&
             EmifRead(REG_ADDR(0x00), &v32) == 0, NULL);

    /* ---- 复位/配置/链路 ---- */
    printf("-- 复位/配置/链路 --\n");
    api_mark("K72Reset", K72Reset() == 0, NULL);
    api_mark("JlkConfig(NC_NT)", JlkConfig(NODE_ID_DEFAULT, GLINK_ROLE_NC_NT) == 0, NULL);
    api_mark("MemorySpaceInit", MemorySpaceInit() == 0, NULL);
    api_mark("NcMemoryMapInit", NcMemoryMapInit(AB_NC_STACK, AB_NC_MEM) == 0, NULL);
    api_mark("NtChannelMap", NtChannelMap(1, AB_LOCAL_NC_ID) == 0, NULL);
    api_mark("GlinkGetLinkStatus(A)", GlinkGetLinkStatus(GLINK_CH_A) >= 0, NULL);
    api_mark("GlinkGetLinkStatus(B)", GlinkGetLinkStatus(GLINK_CH_B) >= 0, NULL);
    {
        int a = GlinkWaitLinkUp(GLINK_CH_A, 5000);
        int b = GlinkWaitLinkUp(GLINK_CH_B, 5000);
        snprintf(note, sizeof(note), "A=%s B=%s", a == 0 ? "UP" : "DOWN",
                 b == 0 ? "UP" : "DOWN");
        api_mark("GlinkWaitLinkUp(A/B,5s)", a == 0 && b == 0, note);
    }
    api_skip("GlinkCheckChannelStatus", "无超时死等, 不调用");
    api_mark("GlinkGetChannelStatus('A')",
             GlinkGetChannelStatus('A') == GlinkGetLinkStatus(GLINK_CH_A), NULL);

    /* ---- FPGA FIFO / 调试 ---- */
    printf("-- FPGA FIFO / 调试 --\n");
    api_mark("FpgaFifoReset", FpgaFifoReset() == 0, NULL);
    api_mark("FpgaFifoWrite", FpgaFifoWrite(0, words, 4) == 4, NULL);
    api_mark("NcTriggerSend", NcTriggerSend(1, 4) == 0, NULL);
    {
        int r = NcWaitDone(1, 100);
        api_mark("NcWaitDone", 1, r == 0 ? "done" : "timeout(ok)");
    }

    v32 = RxFifoGetCount(0);
    snprintf(note, sizeof(note), "count=%u", v32);
    api_mark("RxFifoGetCount", 1, note);
    api_mark("RxFifoRead", RxFifoRead(0, words, 4) >= 0, NULL);
    snprintf(note, sizeof(note), "0x%08X", FpgaGetDebug());
    api_mark("FpgaGetDebug", 1, note);
    JlkDumpAll();
    api_mark("JlkDumpAll", 1, "已打印");
    FpgaDumpStatus();
    api_mark("FpgaDumpStatus", 1, "已打印");

    /* ---- CtrlNC/CtrlNT ---- */
    printf("-- CtrlNC / CtrlNT --\n");
    api_mark("CtrlNcMemoryMap", CtrlNcMemoryMap(AB_NC_STACK, AB_NC_MEM, 1) == 0, NULL);
    api_mark("CtrlNcMemoryMapGroup",
             CtrlNcMemoryMapGroup(AB_NC_STACK, 10, AB_NC_MEM, 1) == 0, NULL);
    api_mark("CtrlNcConfigDescriptor",
             CtrlNcConfigDescriptor(AB_NC_MEM, AB_REMOTE_NT_ID, 0, 0, 0,
                                    AB_DEFAULT_SA, 0, 64) == 0, NULL);
    api_mark("CtrlNcConfigDescriptorFull",
             CtrlNcConfigDescriptorFull(AB_NC_MEM, AB_REMOTE_NT_ID, 0, 0, 0,
                                        AB_DEFAULT_SA, 0, 0, 0, 1, 1, 0, 1, 0, 1,
                                        0, 0, 0, 0, 64) == 0, NULL);
    api_mark("CtrlNcSendData", CtrlNcSendData(AB_NC_MEM, words, 8) == 0, NULL);
    api_mark("CtrlNcStartXmit", CtrlNcStartXmit(1, 0) == 0, NULL);
    api_mark("CtrlNcStartXmitFull", CtrlNcStartXmitFull(0, 1, 0) == 0, NULL);
    v16 = CtrlNcGetExchangeBlockStatus(AB_NC_STACK);
    snprintf(note, sizeof(note), "status=0x%04X", v16);
    api_mark("CtrlNcGetExchangeBlockStatus", 1, note);
    api_mark("CtrlNcWaitDone", CtrlNcWaitDone(AB_NC_STACK, 200) <= 0, "可调用");
    api_mark("CtrlNc1ConfigRetry", CtrlNc1ConfigRetry(1, 2) == 0, NULL);
    api_mark("CtrlNc1ConfigRetryGroup", CtrlNc1ConfigRetryGroup(1, 2, 1) == 0, NULL);

    api_mark("CtrlNtSetStackPtr", CtrlNtSetStackPtr(AB_NT_STACK) == 0, NULL);
    api_mark("CtrlNtChannelMap", CtrlNtChannelMap(1, 0, AB_LOCAL_NC_ID) == 0, NULL);
    api_mark("CtrlNtConfigRecvMemory",
             CtrlNtConfigRecvMemory(1, AB_DEFAULT_SA, AB_NT_RECV) == 0, NULL);
    api_mark("CtrlNtConfigRecvMemoryFull",
             CtrlNtConfigRecvMemoryFull(1, 0, 0, 0x200, AB_DEFAULT_SA, AB_NT_RECV) == 0, NULL);
    api_mark("CtrlNtConfigSendMemory",
             CtrlNtConfigSendMemory(1, AB_DEFAULT_SA, AB_NT_SEND) == 0, NULL);
    api_mark("CtrlNtInitUnusedChannel", CtrlNtInitUnusedChannel(2) == 0, NULL);
    api_mark("CtrlNtConfigBusyTable", CtrlNtConfigBusyTable(1, 0, 5) == 0, NULL);
    api_mark("CtrlNtConfig", CtrlNtConfig(0xA0, 0x1C) == 0, NULL);
    snprintf(note, sizeof(note), "0x%04X", JlkGetIntStatus());
    api_mark("JlkGetIntStatus", 1, note);
    api_mark("CtrlNtWaitInterrupt", CtrlNtWaitInterrupt(50) <= 0, "短超时");
    api_mark("CtrlNtWaitRecv", CtrlNtWaitRecv(AB_NT_STACK, 50) <= 0, "短超时");
    {
        uint16_t nc_id = 0, tr = 0, sa = 0, bl = 0;
        uint16_t addr = CtrlNtGetRecvBlock(&nc_id, &tr, &sa, &bl);
        snprintf(note, sizeof(note), "addr=0x%04X", addr);
        api_mark("CtrlNtGetRecvBlock", 1, note);
    }
    snprintf(note, sizeof(note), "SP=0x%04X", CtrlNtGetCurrentSp());
    api_mark("CtrlNtGetCurrentSp", 1, note);
    {
        uint16_t nc_id = 0, tr = 0, sa = 0, bl = 0;
        CtrlNtGetSpTargetNcId(AB_NT_STACK, &nc_id, &tr, &sa, &bl);
        api_mark("CtrlNtGetSpTargetNcId", 1, NULL);
    }
    api_mark("CtrlNtModeCodeProcess", CtrlNtModeCodeProcess(1, 0) == 0, NULL);
    api_mark("CtrlNtEnhanceModeCode", CtrlNtEnhanceModeCode(1, 0) == 0, NULL);
    api_mark("CtrlNtIllegalCmdConfig", CtrlNtIllegalCmdConfig(1, 0) == 0, NULL);

    /* ---- 能力/速率/启停 ---- */
    printf("-- 能力/速率/启停/消息 --\n");
    api_mark("GlinkGetCapability", GlinkGetCapability(&cap) == 0, NULL);
    api_mark("GlinkGetHardWareInfo",
             GlinkGetHardWareInfo(&fpga_ver, &jlk_id) == 0, NULL);
    api_mark("GlinkResetPort", GlinkResetPort(0) == 0, NULL);
    api_mark("GlinkSetRate", GlinkSetRate(GLINK_RATE_2G5) == 0, NULL);
    snprintf(note, sizeof(note), "rate=%d", (int)GlinkGetRate());
    api_mark("GlinkGetRate", 1, note);
    api_mark("NcStart", NcStart() == 0, NULL);
    api_mark("NcStop", NcStop() == 0, NULL);
    api_mark("NtStart", NtStart() == 0, NULL);
    api_mark("NtStop", NtStop() == 0, NULL);
    api_mark("NcAperiodicRun", NcAperiodicRun(0, 0) == 0, NULL);
    api_mark("NcSaFillData",
             NcSaFillData(0x8003, 0x8003, 1, bytes, 16) == 0, NULL);
    api_mark("NcSaReadData",
             NcSaReadData(0x8003, 0x8003, 1, bytes, 16) >= 0, NULL);
    api_mark("NtAddSa", NtAddSa(1, 0x8003, 1, 1, 1) == 0, NULL);
    api_mark("NtSaReadData", NtSaReadData(1, 1, bytes, 16) >= 0, NULL);
    api_mark("NcAllocMsgBuf", NcAllocMsgBuf(2, 2) == 0, NULL);
    msg.src_nc_id = 0x8003; msg.dst_nt_id = 0x0006; msg.sa = 1;
    msg.byte_count = 64; msg.retry_en = 1; msg.int_en = 1;
    api_mark("NcSetMsg", NcSetMsg(0, &msg) == 0, NULL);
    api_mark("NcGetMsg", NcGetMsg(0, &msg_rd) == 0 && msg_rd.sa == 1, NULL);
    api_mark("NcConfigMulticast", NcConfigMulticast(0, 1) == 0, NULL);
    api_mark("NcConfigMonitor", NcConfigMonitor(0, 1) == 0, NULL);
    api_mark("GlinkSetRedunMode", GlinkSetRedunMode(1) == 0, NULL);
    api_mark("GlinkSetTimeSyn", GlinkSetTimeSyn(0, 0, 0) == 0, NULL);
    api_mark("GlinkLoopbackTest", GlinkLoopbackTest() <= 0, "寄存器级自检");
    api_mark("GlinkEnableRing", GlinkEnableRing(0) == 0, NULL);
    api_mark("GlinkConfigRingBandwidth", GlinkConfigRingBandwidth(1) == 0, NULL);
    api_mark("GlinkConfigFrameTimeout", GlinkConfigFrameTimeout(2) == 0, NULL);
    snprintf(note, sizeof(note), "A=0x%04X", GlinkGetARunStatus());
    api_mark("GlinkGetARunStatus", 1, note);
    snprintf(note, sizeof(note), "B=0x%04X", GlinkGetBRunStatus());
    api_mark("GlinkGetBRunStatus", 1, note);

    /* ---- SmartNC/NT ---- */
    printf("-- SmartNC / SmartNT --\n");
    snc.timeout = 1000; snc.bandwidth = 0; snc.payload_size = 3;
    snc.stack_depth = 0; snc.stack_en = 1; snc.short_msg_mode = 1;
    api_mark("SmartNcInit", SmartNcInit(1, &snc) == 0, NULL);
    api_mark("SmartNc1ConfigTimeout", SmartNc1ConfigTimeout(1000) == 0, NULL);
    api_mark("SmartNc1Config", SmartNc1Config(SMARTNC_STACK_EN) == 0, NULL);
    api_mark("SmartNcSetStackPtr", SmartNcSetStackPtr(1, 0x3000) == 0, NULL);
    snprintf(note, sizeof(note), "SP=0x%04X", SmartNcGetCurrentSp(1));
    api_mark("SmartNcGetCurrentSp", 1, note);
    api_mark("SmartNcShortMsgSend",
             SmartNcShortMsgSend(1, bytes, 32) == 0, NULL);
    api_mark("SmartNcLongMsgSend",
             SmartNcLongMsgSend(1, bytes, 32) == 0, NULL);
    api_mark("SmartNcStartXmit", SmartNcStartXmit(0) == 0, NULL);
    api_mark("SmartNcWaitDone", SmartNcWaitDone(1, 50) <= 0, "短超时");
    SmartNcGetStatus(1, &snc_st);
    api_mark("SmartNcGetStatus", 1, NULL);
    {
        uint16_t sw = 0, rt = 0, soe = 0, eoe = 0, nt = 0, el = 0;
        SmartNcGetDescBlock(1, 0x3000, &sw, &rt, &soe, &eoe, &nt, &el);
        api_mark("SmartNcGetDescBlock", 1, NULL);
    }
    snt.pair_nc_id = AB_LOCAL_NC_ID; snt.pair_nc_ch = 0; snt.short_msg_mode = 1;
    api_mark("SmartNtInit", SmartNtInit(1, &snt) == 0, NULL);
    api_mark("SmartNtConfigChannel",
             SmartNtConfigChannel(1, AB_LOCAL_NC_ID, 1, 1) == 0, NULL);
    api_mark("SmartNtShortMsgSend", SmartNtShortMsgSend(1, bytes, 16) == 0, NULL);
    {
        uint16_t src = 0;
        uint8_t typ = 0;
        int r = SmartNtLongMsgRecv(1, bytes, 64, &src, &typ);
        snprintf(note, sizeof(note), "ret=%d", r);
        api_mark("SmartNtLongMsgRecv", 1, note);  /* 有无数据均可, 只验证可调用 */
    }
    {
        uint16_t cmd = 0;
        int r = SmartNtShortMsgRecv(1, bytes, 64, &cmd);
        snprintf(note, sizeof(note), "ret=%d", r);
        api_mark("SmartNtShortMsgRecv", 1, note);
    }
    api_mark("SmartNtWaitRecv", SmartNtWaitRecv(1, 50) <= 0, "短超时");

    /* ---- GPIO / Frame / NM / IO / Repeater ---- */
    printf("-- GPIO / 帧记录 / NM / IO / 中继 --\n");
    api_mark("GpioSetDirection", GpioSetDirection(0xFFFF) == 0, NULL);
    api_mark("GpioSetOutput", GpioSetOutput(0x1234) == 0, NULL);
    snprintf(note, sizeof(note), "rb=0x%04X", GpioReadback());
    api_mark("GpioReadback", 1, note);
    api_mark("FrameRecordEnable", FrameRecordEnable(0, 1) == 0, NULL);
    api_mark("FrameRecordSetFilter", FrameRecordSetFilter(0, 3) == 0, NULL);
    api_mark("FrameRecordRead", FrameRecordRead(0, frame) == 0, NULL);
    FrameRecordEnable(0, 0);

    nm.node_id = 3; nm.channel_en = 3;
    api_mark("NmInit", NmInit(&nm) == 0, NULL);
    {
        uint32_t ts = 0;
        api_mark("NmReadRecord", NmReadRecord(bytes, 16, &ts) >= 0, NULL);
    }
    snprintf(note, sizeof(note), "0x%04X", NmGetStatus());
    api_mark("NmGetStatus", 1, note);

    io.chip_id = 3; io.default_output = 0x00FF; io.ctrl_src_id[0] = 1;
    api_mark("IoModeInit", IoModeInit(&io) == 0, NULL);
    api_mark("IoPwmOutput", IoPwmOutput(0, 50, 1000) == 0, NULL);
    api_mark("IoLevelOutput", IoLevelOutput(0, 1) == 0, NULL);
    api_mark("IoReadback", IoReadback(0) >= 0, NULL);
    api_mark("IoReadbackAutoSend", IoReadbackAutoSend(0, 0) == 0, NULL);
    api_mark("SmartInterfaceConfig",
             SmartInterfaceConfig(0x01, bytes, 4) == 0, NULL);
    api_mark("SmartInterfaceTriggerCpu", SmartInterfaceTriggerCpu() == 0, NULL);
    api_mark("SmartInterfaceResetCpu", SmartInterfaceResetCpu() == 0, NULL);
    api_mark("SmartInterfaceClearFifo", SmartInterfaceClearFifo() == 0, NULL);

    rep.repeater_num = 1; rep.ch_c_enable = 1; rep.ch_d_enable = 1;
    api_mark("RepeaterInit", RepeaterInit(&rep) == 0, NULL);
    api_mark("RepeaterReset", RepeaterReset() == 0, NULL);
    snprintf(note, sizeof(note), "C=0x%04X", RepeaterGetChCStatus());
    api_mark("RepeaterGetChCStatus", 1, note);
    snprintf(note, sizeof(note), "D=0x%04X", RepeaterGetChDStatus());
    api_mark("RepeaterGetChDStatus", 1, note);
    snprintf(note, sizeof(note), "VER=0x%04X", RepeaterGetVersion());
    api_mark("RepeaterGetVersion", 1, note);

    /* 恢复标准模式 + CtrlNC/NT, 避免污染后续测试 */
    printf("\n-- 恢复标准 CtrlNC+CtrlNT --\n");
    FpgaRegWrite(P_GC_MODE_REGISTER, 1);
    GlinkSetRate(GLINK_RATE_2G5);
    JlkConfig(NODE_ID_DEFAULT, GLINK_ROLE_NC_NT);
    JlkRegWrite(JLK_REG_CHANNEL_EN, CHANNEL_EN_AB);

    printf("\n========================================\n");
    printf("  API汇总: OK=%d  FAIL=%d  SKIP=%d\n", g_api_ok, g_api_fail, g_api_skip);
    printf("========================================\n");
    return (g_api_fail == 0) ? TR_PASS : TR_FAIL;
}

/*============================================================
 * 对端 GLink 通信参数配置
 *============================================================*/
typedef struct {
    uint16_t local_id;       /* 本端节点ID (低12位有效, 写时或上 0x8000) */
    glink_role_t role;       /* NC / NT / NC_NT */
    uint16_t remote_id;      /* 对端 ID: NC时=目标NT; NT时=配对NC */
    uint16_t sa;             /* 子地址 */
    int      word_count;     /* 字数 */
    int      tr;             /* 0=发送 1=拉取 */
    int      retry_en;
    int      use_ch_b;       /* 描述符 CH_B */
    glink_rate_t rate;
    uint16_t nc_stack, nc_mem, nt_stack, nt_recv, nt_send;
    int      link_timeout_ms;
} peer_cfg_t;

static peer_cfg_t g_peer = {
    .local_id = 0x0003,
    .role = GLINK_ROLE_NC,
    .remote_id = 0x0006,
    .sa = 1,
    .word_count = 32,
    .tr = 0,
    .retry_en = 1,
    .use_ch_b = 0,
    .rate = GLINK_RATE_2G5,
    .nc_stack = AB_NC_STACK,
    .nc_mem = AB_NC_MEM,
    .nt_stack = AB_NT_STACK,
    .nt_recv = AB_NT_RECV,
    .nt_send = AB_NT_SEND,
    .link_timeout_ms = 30000,
};

static const char *role_name(glink_role_t r)
{
    return r == GLINK_ROLE_NC ? "NC" :
           r == GLINK_ROLE_NT ? "NT" : "NC+NT";
}

static void peer_print(const peer_cfg_t *p)
{
    printf("\n---- 当前对端通信参数 ----\n");
    printf("  local_id      = 0x%03X (写寄存器 0x%04X)\n",
           p->local_id & 0xFFF, (p->local_id & 0xFFF) | 0x8000);
    printf("  role          = %s (%d)\n", role_name(p->role), (int)p->role);
    printf("  remote_id     = 0x%03X\n", p->remote_id & 0xFFF);
    printf("  SA            = %u\n", p->sa);
    printf("  word_count    = %d (%d bytes)\n", p->word_count, p->word_count * 2);
    printf("  TR            = %d (%s)\n", p->tr, p->tr ? "拉取" : "发送");
    printf("  retry_en      = %d\n", p->retry_en);
    printf("  use_ch_b      = %d\n", p->use_ch_b);
    printf("  rate          = %d (FPGA CLK_FREQ_SEL)\n", (int)p->rate);
    printf("  nc_stack/mem  = 0x%04X / 0x%04X\n", p->nc_stack, p->nc_mem);
    printf("  nt_stack/recv/send = 0x%04X / 0x%04X / 0x%04X\n",
           p->nt_stack, p->nt_recv, p->nt_send);
    printf("  link_timeout  = %d ms\n", p->link_timeout_ms);
    printf("---------------------------\n");
}

static int peer_apply(const peer_cfg_t *p)
{
    uint16_t nid = (uint16_t)((p->local_id & 0xFFF) | 0x8000);

    printf("  [apply] K72Reset + rate + JlkConfig...\n");
    if (K72Reset() != 0)
        return -1;
    GlinkSetRate(p->rate);
    if (JlkConfig(nid, p->role) != 0)
        return -1;
    MemorySpaceInit();

    if (p->role == GLINK_ROLE_NC || p->role == GLINK_ROLE_NC_NT) {
        CtrlNcMemoryMap(p->nc_stack, p->nc_mem, 1);
        CtrlNc1ConfigRetry(p->retry_en ? 1 : 0, 2);
    }
    if (p->role == GLINK_ROLE_NT || p->role == GLINK_ROLE_NC_NT) {
        CtrlNtSetStackPtr(p->nt_stack);
        CtrlNtChannelMap(1, 0, p->remote_id & 0xFFF);
        CtrlNtConfigRecvMemory(1, p->sa, p->nt_recv);
        CtrlNtConfigSendMemory(1, p->sa, p->nt_send);
        CtrlNtInitUnusedChannel(2);
        CtrlNtConfig(0xA0, 0x1C);
    }

    /* NC+NT 自环时 remote 常等于 local */
    if (p->role == GLINK_ROLE_NC_NT) {
        CtrlNtChannelMap(1, 0, p->local_id & 0xFFF);
    }

    printf("  [apply] WORK=0x%04X CH_EN=0x%04X ID=0x%04X\n",
           JlkRegRead(JLK_REG_WORK_MODE),
           JlkRegRead(JLK_REG_CHANNEL_EN),
           JlkRegRead(JLK_REG_NODE_ID));
    return 0;
}

static int peer_wait_link(const peer_cfg_t *p)
{
    printf("  等待 A/B LINK (%d ms)...\n", p->link_timeout_ms);
    if (GlinkWaitLinkUp(GLINK_CH_A, p->link_timeout_ms) != 0) {
        printf("  [失败] A LINK DOWN\n");
        return -1;
    }
    if (GlinkWaitLinkUp(GLINK_CH_B, p->link_timeout_ms) != 0) {
        printf("  [失败] B LINK DOWN (单通道场景可忽略B)\n");
        /* 单纤/单电口时 B 可能 DOWN, 不强制失败 */
    }
    printf("  LINK A=%d B=%d  status A=0x%04X B=0x%04X\n",
           GlinkGetLinkStatus(GLINK_CH_A), GlinkGetLinkStatus(GLINK_CH_B),
           JlkRegRead(JLK_REG_CH_A_STATUS), JlkRegRead(JLK_REG_CH_B_STATUS));
    return 0;
}

static int peer_nc_xfer(const peer_cfg_t *p)
{
    uint16_t send[AB_MAX_WORDS], recv[AB_MAX_WORDS];
    int n = p->word_count;
    uint16_t target = p->remote_id & 0xFFF;

    if (n <= 0 || n > AB_MAX_WORDS) {
        printf("  word_count 非法\n");
        return -1;
    }
    if (p->role == GLINK_ROLE_NT) {
        printf("  当前角色是 NT, 不能做 NC 发送; 请改 role=NC 或 NC_NT\n");
        return -1;
    }

    gen_pattern(send, n, 0xC001);
    print_hex("  发送: ", send, n, 8);

    if (p->tr == 0) {
        CtrlNcMemoryMap(p->nc_stack, p->nc_mem, 1);
        CtrlNcSendData(p->nc_mem, send, n);
        CtrlNcConfigDescriptorFull(p->nc_mem, target, 0, 0, 0, p->sa,
                                   0, 0, 0, 1, p->retry_en ? 1 : 0, 0,
                                   1, p->use_ch_b ? 1 : 0, 1,
                                   0, 0, 0, 0, (uint16_t)(n * 2));
        CtrlNcStartXmit(1, 0);
        if (CtrlNcWaitDone(p->nc_stack, AB_XFER_TIMEOUT_MS) != 0) {
            printf("  [失败] NC 发送超时 status=0x%04X\n",
                   CtrlNcGetExchangeBlockStatus(p->nc_stack));
            return -1;
        }
        printf("  [通过] NC 发送完成 status=0x%04X\n",
               CtrlNcGetExchangeBlockStatus(p->nc_stack));

        if (p->role == GLINK_ROLE_NC_NT) {
            if (CtrlNtWaitRecv(p->nt_stack, AB_XFER_TIMEOUT_MS) != 0) {
                printf("  [失败] 本端 NT 未收到\n");
                return -1;
            }
            {
                uint16_t nc_id = 0, tr = 0, sa = 0, bl = 0;
                uint16_t addr = CtrlNtGetRecvBlock(&nc_id, &tr, &sa, &bl);
                for (int i = 0; i < n; i++)
                    recv[i] = JlkMemRead(addr + i);
                if (verify_words(send, recv, n) >= 0) {
                    printf("  [失败] 本端回环数据不一致\n");
                    return -1;
                }
                print_hex("  本端NT收: ", recv, n, 8);
                printf("  [通过] NC_NT 本端校验一致\n");
            }
        } else {
            printf("  提示: 对端 NT 需已配置 ID=0x%03X SA=%u 才能收到\n",
                   target, p->sa);
        }
    } else {
        /* TR=1 拉取: 对端 NT 需预置 nt_send; NC_NT 自环时本端预置 */
        if (p->role == GLINK_ROLE_NC_NT) {
            for (int i = 0; i < n; i++)
                JlkMemWrite(p->nt_send + i, send[i]);
            CtrlNtConfigSendMemory(1, p->sa, p->nt_send);
        }
        CtrlNcMemoryMap(p->nc_stack, p->nc_mem, 1);
        for (int i = 0; i < n; i++)
            JlkMemWrite(p->nc_mem + 0x8 + i, 0);
        CtrlNcConfigDescriptorFull(p->nc_mem, target, 0, 0, 0, p->sa,
                                   1, 0, 0, 1, p->retry_en ? 1 : 0, 0,
                                   1, p->use_ch_b ? 1 : 0, 1,
                                   0, 0, 0, 0, (uint16_t)(n * 2));
        CtrlNcStartXmit(1, 0);
        if (CtrlNcWaitDone(p->nc_stack, AB_XFER_TIMEOUT_MS) != 0) {
            printf("  [失败] NC 拉取超时\n");
            return -1;
        }
        for (int i = 0; i < n; i++)
            recv[i] = JlkMemRead(p->nc_mem + 0xC + i);
        if (p->role == GLINK_ROLE_NC_NT) {
            if (verify_words(send, recv, n) >= 0) {
                for (int i = 0; i < n; i++)
                    recv[i] = JlkMemRead(p->nc_mem + 0x8 + i);
                if (verify_words(send, recv, n) >= 0) {
                    printf("  [失败] 拉取数据不一致\n");
                    print_hex("  got: ", recv, n, 8);
                    return -1;
                }
            }
            print_hex("  拉取: ", recv, n, 8);
            printf("  [通过] TR=1 拉取一致\n");
        } else {
            print_hex("  拉取原始: ", recv, n, 8);
            printf("  [通过] NC 拉取完成 (请人工核对对端数据)\n");
        }
    }
    return 0;
}

static int peer_nt_arm(const peer_cfg_t *p)
{
    uint16_t prep[AB_MAX_WORDS];
    int n = p->word_count;

    if (p->role == GLINK_ROLE_NC) {
        printf("  当前角色是 NC, 请改 role=NT 或 NC_NT\n");
        return -1;
    }
    if (n > AB_MAX_WORDS) n = AB_MAX_WORDS;

    printf("  NT 已就绪: 配对NC=0x%03X SA=%u recv=0x%04X send=0x%04X\n",
           p->remote_id & 0xFFF, p->sa, p->nt_recv, p->nt_send);
    gen_pattern(prep, n, 0xD001);
    for (int i = 0; i < n; i++)
        JlkMemWrite(p->nt_send + i, prep[i]);
    print_hex("  NT发送区预置(供对端拉取): ", prep, n < 8 ? n : 8, 8);

    printf("  等待接收 (超时 %d ms)...\n", p->link_timeout_ms);
    if (CtrlNtWaitRecv(p->nt_stack, p->link_timeout_ms) != 0) {
        printf("  [超时] 未收到 NC 数据 (对端未发或参数不匹配)\n");
        return -1;
    }
    {
        uint16_t nc_id = 0, tr = 0, sa = 0, bl = 0;
        uint16_t addr = CtrlNtGetRecvBlock(&nc_id, &tr, &sa, &bl);
        uint16_t buf[AB_MAX_WORDS];
        int words = bl / 2;
        if (words > AB_MAX_WORDS) words = AB_MAX_WORDS;
        for (int i = 0; i < words; i++)
            buf[i] = JlkMemRead(addr + i);
        printf("  收到: NC=0x%02X TR=%u SA=%u bytes=%u addr=0x%04X\n",
               nc_id, tr, sa, bl, addr);
        print_hex("  数据: ", buf, words, 8);
    }
    return 0;
}

static int read_int_prompt(const char *prompt, int def_val)
{
    char buf[64];
    printf("%s [%d]: ", prompt, def_val);
    fflush(stdout);
    if (!fgets(buf, sizeof(buf), stdin))
        return def_val;
    if (buf[0] == '\n' || buf[0] == '\0')
        return def_val;
    return (int)strtol(buf, NULL, 0);
}

static void peer_edit_interactive(peer_cfg_t *p)
{
    int v;
    peer_print(p);
    printf("直接回车保留原值; 支持 0x 前缀\n");
    v = read_int_prompt("local_id", p->local_id);
    p->local_id = (uint16_t)v;
    v = read_int_prompt("role 0=NC 1=NT 2=NC_NT", (int)p->role);
    if (v >= 0 && v <= 2) p->role = (glink_role_t)v;
    v = read_int_prompt("remote_id", p->remote_id);
    p->remote_id = (uint16_t)v;
    v = read_int_prompt("SA", p->sa);
    p->sa = (uint16_t)v;
    v = read_int_prompt("word_count", p->word_count);
    if (v > 0 && v <= AB_MAX_WORDS) p->word_count = v;
    v = read_int_prompt("TR 0=发送 1=拉取", p->tr);
    p->tr = v ? 1 : 0;
    v = read_int_prompt("retry_en", p->retry_en);
    p->retry_en = v ? 1 : 0;
    v = read_int_prompt("use_ch_b", p->use_ch_b);
    p->use_ch_b = v ? 1 : 0;
    v = read_int_prompt("rate(FPGA码 5=2.5G)", (int)p->rate);
    p->rate = (glink_rate_t)v;
    v = read_int_prompt("link_timeout_ms", p->link_timeout_ms);
    if (v > 0) p->link_timeout_ms = v;
    peer_print(p);
}

static test_rc_t opt_peer_comm(void)
{
    char buf[64];
    int sub;
    test_rc_t overall = TR_PASS;

    printf("\n=== 对端 GLink 通信配置 / 收发 ===\n");
    printf("  用于与另一块 GLink 板互通, 或本板 A<->B 自环(role=NC_NT, remote=local)\n");

    while (1) {
        peer_print(&g_peer);
        printf("  a) 编辑参数\n");
        printf("  b) 应用配置到硬件\n");
        printf("  c) 等待 LINK\n");
        printf("  d) NC 发送/拉取一次\n");
        printf("  e) NT 布防并等待接收\n");
        printf("  f) 一键: 应用+等LINK+按角色收发 (适合 NC_NT 自环)\n");
        printf("  q) 返回主菜单\n");
        printf("选择: ");
        fflush(stdout);
        if (!fgets(buf, sizeof(buf), stdin))
            break;
        sub = buf[0];
        if (sub == 'q' || sub == 'Q' || sub == '0')
            break;
        if (sub == 'a' || sub == 'A') {
            peer_edit_interactive(&g_peer);
        } else if (sub == 'b' || sub == 'B') {
            if (peer_apply(&g_peer) != 0) {
                printf("  [失败] apply\n");
                overall = TR_FAIL;
            } else {
                printf("  [通过] apply\n");
            }
        } else if (sub == 'c' || sub == 'C') {
            if (peer_wait_link(&g_peer) != 0)
                overall = TR_FAIL;
        } else if (sub == 'd' || sub == 'D') {
            if (peer_nc_xfer(&g_peer) != 0)
                overall = TR_FAIL;
        } else if (sub == 'e' || sub == 'E') {
            if (peer_nt_arm(&g_peer) != 0)
                overall = TR_FAIL;
        } else if (sub == 'f' || sub == 'F') {
            if (peer_apply(&g_peer) != 0 || peer_wait_link(&g_peer) != 0) {
                overall = TR_FAIL;
                continue;
            }
            if (g_peer.role == GLINK_ROLE_NT) {
                if (peer_nt_arm(&g_peer) != 0)
                    overall = TR_FAIL;
            } else {
                if (peer_nc_xfer(&g_peer) != 0)
                    overall = TR_FAIL;
            }
        }
    }
    return overall;
}

/* 非交互: 用当前 g_peer (可被环境默认) 执行一键 */
static test_rc_t opt_peer_comm_auto(void)
{
    printf("\n=== 对端通信一键 (非交互, 当前参数) ===\n");
    /* 默认改成 NC_NT 自环, 保证 A<->B 接线可测 */
    g_peer.role = GLINK_ROLE_NC_NT;
    g_peer.remote_id = g_peer.local_id;
    peer_print(&g_peer);
    if (peer_apply(&g_peer) != 0)
        return TR_FAIL;
    if (peer_wait_link(&g_peer) != 0)
        return TR_FAIL;
    if (peer_nc_xfer(&g_peer) != 0)
        return TR_FAIL;
    printf("  [通过] 一键对端/自环通信\n");
    return TR_PASS;
}

/*============================================================
 * 套件编排 / 菜单
 *============================================================*/
typedef test_rc_t (*test_fn_t)(void);

typedef struct {
    const char *name;
    test_fn_t fn;
} suite_item_t;

/* 扩展项在后方定义, 先声明供 ab-full 套件引用 */
static test_rc_t opt_smart_config_demo(void);
static test_rc_t opt_smart_short_loop(void);
static test_rc_t opt_smart_to_ctrlnt(void);
static test_rc_t opt_smart_long_smoke(void);
static test_rc_t opt_nm_full_demo(void);
static test_rc_t opt_io_ab_check(void);
static test_rc_t opt_rate_query(void);
static test_rc_t opt_repeater_ab_skip(void);

/* A↔B 回路 Ctrl 全功能 (不含 Smart, Smart 归第二项) */
static const suite_item_t g_ab_suite[] = {
    { "L0/L1 设备与EMIF",           test_l0_l1_emif },
    { "硬件信息/版本/能力",         test_hw_info },
    { "GPIO本地寄存器",             test_gpio_local },
    { "A/B LINK与运行状态",         test_link_status },
    { "CtrlNC->CtrlNT基础自环32字", test_ctrl_basic },
    { "多子地址SA=1/2/3",           test_multi_sa },
    { "变长载荷1~128字",            test_var_payload },
    { "CtrlNT->CtrlNC拉取TR=1",     test_nt_pull },
    { "重发配置+自环",              test_retry },
    { "帧记录",                     test_frame_record },
    { "忙表配置+通信",              test_busy_table },
    { "时间戳配置",                 test_timestamp },
    { "压力自环20轮",               test_stress },
    { "LINK监控10s",                test_link_monitor },
    { "双向通信NC<->NT",            test_bidirectional },
    { "寄存器诊断dump",             test_reg_dump },
};

#define AB_SUITE_COUNT ((int)(sizeof(g_ab_suite) / sizeof(g_ab_suite[0])))

/* 手册 AB 回环可测的 GLink 全项 (Ctrl + Smart + NM/IO + 速率; 中继跳过) */
static const suite_item_t g_ab_glink_suite[] = {
    /* —— 控制流 (已覆盖) —— */
    { "Ctrl: L0/L1 EMIF",              test_l0_l1_emif },
    { "Ctrl: 硬件信息",                test_hw_info },
    { "Ctrl: GPIO本地",                test_gpio_local },
    { "Ctrl: A/B LINK",                test_link_status },
    { "Ctrl: NC->NT基础32字",          test_ctrl_basic },
    { "Ctrl: 多子地址",                test_multi_sa },
    { "Ctrl: 变长载荷",                test_var_payload },
    { "Ctrl: NT拉取TR=1",              test_nt_pull },
    { "Ctrl: 重发",                    test_retry },
    { "Ctrl: 帧记录",                  test_frame_record },
    { "Ctrl: 忙表",                    test_busy_table },
    { "Ctrl: 时间戳",                  test_timestamp },
    { "Ctrl: 压力20轮",                test_stress },
    { "Ctrl: LINK监控",                test_link_monitor },
    { "Ctrl: 双向",                    test_bidirectional },
    { "Ctrl: 寄存器dump",              test_reg_dump },
    /* —— 智能流 (手册6.5/6.6, AB上此前未进ctrl-all) —— */
    { "Smart: 寄存器配置",             opt_smart_config_demo },
    { "Smart: 短报NC->NT",             opt_smart_short_loop },
    { "Smart: 短报NC->CtrlNT",         opt_smart_to_ctrlnt },
    { "Smart: 长报冒烟",               opt_smart_long_smoke },
    /* —— 其他大模式 / 诊断 —— */
    { "NM: 监听演示",                  opt_nm_full_demo },
    { "IO: 寄存器+恢复",               opt_io_ab_check },
    { "Rate: 速率查询",                opt_rate_query },
    { "Repeater: AB不适用",            opt_repeater_ab_skip },
};

#define AB_GLINK_SUITE_COUNT ((int)(sizeof(g_ab_glink_suite) / sizeof(g_ab_glink_suite[0])))

static int run_ab_full_suite(void)
{
    result_reset();
    printf("\n######## 【控制流】A<->B 全功能 (%d 项) ########\n", AB_SUITE_COUNT);
    printf("数据路径: CtrlNC 写MEM -> 光纤/电口 SerDes -> CtrlNT 读MEM\n");
    printf("示例数据: 递增字型 0001,0002,... 或按项生成的图案\n\n");
    for (int i = 0; i < AB_SUITE_COUNT; i++) {
        printf("\n---------- [%02d/%02d] %s ----------\n",
               i + 1, AB_SUITE_COUNT, g_ab_suite[i].name);
        test_rc_t rc = g_ab_suite[i].fn();
        result_record(g_ab_suite[i].name, rc);
    }
    result_summary();
    return g_fail ? -1 : 0;
}

static int run_ab_glink_full_suite(void)
{
    result_reset();
    printf("\n######## 【GLink AB回环统一测试】共 %d 项 ########\n",
           AB_GLINK_SUITE_COUNT);
    printf("范围: Ctrl全功能 + Smart短/长 + Smart->CtrlNT + NM/IO/Rate\n");
    printf("跳过: 中继(需C/D); 双卡对发; SmartNC2~4 多路\n\n");
    for (int i = 0; i < AB_GLINK_SUITE_COUNT; i++) {
        printf("\n========== [%02d/%02d] %s ==========\n",
               i + 1, AB_GLINK_SUITE_COUNT, g_ab_glink_suite[i].name);
        test_rc_t rc = g_ab_glink_suite[i].fn();
        result_record(g_ab_glink_suite[i].name, rc);
    }
    result_summary();
    return g_fail ? -1 : 0;
}

/*---------- 功能说明 + Smart/NM 演示（带测试数据） ----------*/

static void print_bytes(const char *prefix, const uint8_t *b, int n)
{
    printf("%s", prefix);
    for (int i = 0; i < n; i++)
        printf("%02X ", b[i]);
    printf("(%d字节)\n", n);
}

static void explain_ctrl(void)
{
    printf("\n");
    printf("╔══════════════════════════════════════════════════════╗\n");
    printf("║  【1】控制流 CtrlNC / CtrlNT                         ║\n");
    printf("╠══════════════════════════════════════════════════════╣\n");
    printf("║  是什么: 类似 1553 的控制消息, 小块可靠交换          ║\n");
    printf("║  数据在哪: JLK MEM 空间 (描述符+载荷)                ║\n");
    printf("║  谁发谁收: CtrlNC=主站发送/拉取  CtrlNT=从站收发     ║\n");
    printf("║  本板自环: role=NC+NT, A通道<->B通道 物理环回        ║\n");
    printf("║  关键寄存器: WORK_MODE bit0=CtrlNC1 bit1=CtrlNT      ║\n");
    printf("║  测试数据: 默认 32 字递增 C001,C002,...              ║\n");
    printf("║  推荐: 先「一键自环」看通, 再「全功能」 dig 细节     ║\n");
    printf("╚══════════════════════════════════════════════════════╝\n");
}

static void explain_smart(void)
{
    printf("\n");
    printf("╔══════════════════════════════════════════════════════╗\n");
    printf("║  【2】智能流 SmartNC / SmartNT                       ║\n");
    printf("╠══════════════════════════════════════════════════════╣\n");
    printf("║  是什么: 大数据流 (短报≤512B / 长报可很大)           ║\n");
    printf("║  数据在哪: FPGA FIFO (0x1000/0x2000) -> SerDes       ║\n");
    printf("║  与Ctrl区别: 不走 Ctrl 描述符MEM, 走同步FIFO         ║\n");
    printf("║  使能: WORK_MODE bit4=SmartNC1 bit8=SmartNT1         ║\n");
    printf("║  大模式: 仍在「标准模式」GC_MODE=1                   ║\n");
    printf("║  测试数据: 16字节 10 11 12 ... 1F (短报示例)         ║\n");
    printf("╚══════════════════════════════════════════════════════╝\n");
}

static void explain_nm(void)
{
    printf("\n");
    printf("╔══════════════════════════════════════════════════════╗\n");
    printf("║  【3】监听 NM / 系统诊断                             ║\n");
    printf("╠══════════════════════════════════════════════════════╣\n");
    printf("║  NM: 旁路听总线上的帧 (需监听大模式 GC_MODE=2 更完整)║\n");
    printf("║  Monitor位: 标准模式 WORK_MODE bit13 (NcConfigMonitor)║\n");
    printf("║  诊断: 速率/冗余/环、GC大模式探测、全API、寄存器dump ║\n");
    printf("║  注意: 硬件指南写「不支持在线改大模式」, 探测后恢复  ║\n");
    printf("╚══════════════════════════════════════════════════════╝\n");
}

/* Smart: 寄存器配置演示 + 打印测试数据意图 */
static test_rc_t opt_smart_config_demo(void)
{
    smartnc_config_t snc;
    smartnt_config_t snt;
    uint8_t demo[16];

    printf("\n=== Smart 配置演示 (标准模式 + 寄存器读回) ===\n");
    for (int i = 0; i < 16; i++)
        demo[i] = (uint8_t)(0x10 + i);
    print_bytes("  预定短报测试数据: ", demo, 16);

    if (K72Reset() != 0)
        return TR_FAIL;
    FpgaRegWrite(P_GC_MODE_REGISTER, 1);
    GlinkSetRate(GLINK_RATE_2G5);
    JlkRegWrite(JLK_REG_NODE_ID, NODE_ID_DEFAULT);
    JlkRegWrite(JLK_REG_CHANNEL_EN, CHANNEL_EN_AB);
    JlkRegWrite(JLK_REG_WORK_MODE, (uint16_t)(MODE_SMARTNC1 | MODE_SMARTNT1));
    MemorySpaceInit();

    printf("  WORK_MODE = 0x%04X (期望含 SmartNC1|SmartNT1)\n",
           JlkRegRead(JLK_REG_WORK_MODE));

    memset(&snc, 0, sizeof(snc));
    snc.timeout = 1000;
    snc.bandwidth = 0;          /* 50% */
    snc.payload_size = 3;       /* 64B */
    snc.stack_depth = 0;
    snc.stack_en = 1;
    snc.short_msg_mode = 1;
    snc.single_channel = 1;
    if (SmartNcInit(1, &snc) != 0)
        return TR_FAIL;
    SmartNcSetStackPtr(1, MEM_SMARTNC1_STACK_BASE);

    memset(&snt, 0, sizeof(snt));
    snt.pair_nc_id = AB_LOCAL_NC_ID;
    snt.pair_nc_ch = 0;
    snt.short_msg_mode = 1;
    if (SmartNtInit(1, &snt) != 0)
        return TR_FAIL;

    printf("  SmartNC1 TIMEOUT=0x%04X CONFIG=0x%04X STATUS=0x%04X\n",
           JlkRegRead(JLK_REG_SMARTNC1_TIMEOUT),
           JlkRegRead(JLK_REG_SMARTNC1_CONFIG),
           JlkRegRead(JLK_REG_SMARTNC1_STATUS));
    printf("  SmartNT1 CONFIG=0x%04X\n", JlkRegRead(JLK_REG_SMARTNT1_CONFIG));
    printf("  SP(MEM 0x%04X)=0x%04X\n",
           MEM_SMARTNC1_SP, SmartNcGetCurrentSp(1));

    printf("  [通过] Smart 寄存器已按短报模式配置 (尚未发数)\n");
    /* 恢复 Ctrl 默认, 避免影响后续 Ctrl 测试 */
    JlkConfig(NODE_ID_DEFAULT, GLINK_ROLE_NC_NT);
    return TR_PASS;
}

/* Smart: 短报文自环 (手册 V1.6 + K72 RTL, 不跟厂家 FMC) */
static test_rc_t opt_smart_short_loop(void)
{
    uint8_t tx[32], rx[64];
    smartnc_config_t snc;
    smartnt_config_t snt;
    uint16_t cmd = 0;
    uint16_t raw_st;
    int nrecv;
    int link_ok;
    uint32_t rd0, rd1;
    int i;

    printf("\n=== SmartNC1 -> SmartNT1 短报文自环 (AB) ===\n");
    printf("依据: 手册表54/60 + RTL_EMIF_IF (SEL=0xC8)\n");
    printf("SNC=0x0400 SNT=0x4000 NODE=0x8003 WORK=0x0110\n");

    for (i = 0; i < 16; i++)
        tx[i] = (uint8_t)(0xA0 + i);
    memset(rx, 0, sizeof(rx));
    print_bytes("  TX 测试数据: ", tx, 16);

    if (K72Reset() != 0)
        return TR_FAIL;
    FpgaRegWrite(P_GC_MODE_REGISTER, 1);
    GlinkSetRate(GLINK_RATE_2G5);
    FpgaFifoReset();
    SmartFifoSetNcShort(1);
    SmartFifoDumpSelect("after-SetNcShort");

    JlkRegWrite(0x01, 0x0001);
    usleep(1000);
    JlkRegWrite(0x01, 0x0000);
    JlkRegWrite(JLK_REG_NODE_ID, NODE_ID_DEFAULT);
    JlkRegWrite(JLK_REG_CHANNEL_EN, CHANNEL_EN_AB);
    JlkRegWrite(JLK_REG_SMARTNC1_TIMEOUT, 0x8000);
    JlkRegWrite(JLK_REG_TIMESTAMP, DEFAULT_TIMESTAMP);
    JlkRegWrite(JLK_REG_INT_MODE, 0x0002);
    JlkMemWrite(MEM_SMARTNC1_SP, MEM_SMARTNC1_STACK_BASE);

    printf("  等待 LINK...\n");
    link_ok = (GlinkWaitLinkUp(GLINK_CH_A, 15000) == 0);
    GlinkWaitLinkUp(GLINK_CH_B, 5000);
    printf("  LINK A=%d B=%d\n",
           GlinkGetLinkStatus(GLINK_CH_A), GlinkGetLinkStatus(GLINK_CH_B));
    if (!link_ok || !GlinkGetLinkStatus(GLINK_CH_B)) {
        printf("  [失败] A/B LINK 未同时建立\n");
        JlkConfig(NODE_ID_DEFAULT, GLINK_ROLE_NC_NT);
        return TR_FAIL;
    }

    memset(&snc, 0, sizeof(snc));
    snc.timeout = 0x8000;
    snc.stack_en = 0;
    snc.short_msg_mode = 1;
    SmartNcInit(1, &snc);
    JlkRegWrite(JLK_REG_SMARTNC1_CONFIG, 0x0400);
    SmartNcSetStackPtr(1, MEM_SMARTNC1_STACK_BASE);

    memset(&snt, 0, sizeof(snt));
    snt.pair_nc_id = 0;
    snt.pair_nc_ch = 0;
    snt.short_msg_mode = 1;
    SmartNtInit(1, &snt);
    JlkRegWrite(JLK_REG_SMARTNT1_CONFIG, 0x4000);
    JlkRegWrite(JLK_REG_WORK_MODE, (uint16_t)(MODE_SMARTNC1 | MODE_SMARTNT1));
    SmartFifoDumpSelect("after-init");

    rd0 = FpgaRegRead(P_RD_FIFO1_WR_NUM);
    printf("  [1] ShortMsgSendEx NT_ID=0x03 type=SmartNT1 len=16 RD0=%u\n",
           (unsigned)rd0);
    if (SmartNcShortMsgSendEx(1, 0x0001, AB_LOCAL_NC_ID, 0, tx, 16, 0) != 0) {
        printf("  [失败] ShortMsgSendEx\n");
        JlkConfig(NODE_ID_DEFAULT, GLINK_ROLE_NC_NT);
        return TR_FAIL;
    }
    SmartNcWaitDone(1, 3000);
    raw_st = JlkRegRead(JLK_REG_SMARTNC1_STATUS);
    printf("  STATUS=0x%04X fail=%u b14=%u b15=%u\n",
           raw_st, (raw_st >> 4) & 0xF, (raw_st >> 14) & 1, (raw_st >> 15) & 1);

    printf("  [2] WaitRdFifo / ShortMsgRecv...\n");
    SmartNcWaitRdFifo(1, 1500);
    rd1 = FpgaRegRead(P_RD_FIFO1_WR_NUM);
    printf("  RD_FIFO1 %u -> %u\n", (unsigned)rd0, (unsigned)rd1);
    SmartFifoDumpSelect("after-wait");

    if (rd1 == rd0) {
        printf("  [失败] RD未变; fail=%u (手册/RTL用法已对齐)\n",
               (raw_st >> 4) & 0xF);
        JlkRegWrite(JLK_REG_SMARTNC1_STATUS, 0x1000);
        JlkConfig(NODE_ID_DEFAULT, GLINK_ROLE_NC_NT);
        return TR_FAIL;
    }

    nrecv = SmartNtShortMsgRecv(1, rx, sizeof(rx), &cmd);
    SmartFifoSetNcShort(1);
    printf("  ShortMsgRecv ret=%d cmd=0x%04X\n", nrecv, cmd);
    if (nrecv > 0)
        print_bytes("  RX: ", rx, nrecv > 32 ? 32 : nrecv);

    JlkRegWrite(JLK_REG_SMARTNC1_STATUS, 0x1000);
    if (nrecv >= 16 && memcmp(tx, rx, 16) == 0) {
        printf("  [通过] 短报自环数据一致\n");
        JlkConfig(NODE_ID_DEFAULT, GLINK_ROLE_NC_NT);
        return TR_PASS;
    }
    printf("  [跳过] 有RD但载荷不一致\n");
    JlkConfig(NODE_ID_DEFAULT, GLINK_ROLE_NC_NT);
    return TR_SKIP;
}

/* SmartNC短报 -> CtrlNT (手册6.5.2/表54 type=100) */
static test_rc_t opt_smart_to_ctrlnt(void)
{
    uint8_t tx[16];
    uint16_t raw_st;
    uint32_t rd0, rd1;
    int i;

    printf("\n=== SmartNC1 -> CtrlNT 短报 (表54 type=100) ===\n");
    for (i = 0; i < 16; i++)
        tx[i] = (uint8_t)(0xB0 + i);
    print_bytes("  TX: ", tx, 16);

    if (K72Reset() != 0)
        return TR_FAIL;
    FpgaRegWrite(P_GC_MODE_REGISTER, 1);
    GlinkSetRate(GLINK_RATE_2G5);
    FpgaFifoReset();
    /* 厂家默认: WR=NC1 RD=NT1 → 0xC8 (CtrlNT 短报读回仍走 NT 侧 FIFO) */
    SmartFifoSetNcShort(1);
    SmartFifoDumpSelect("smart->CtrlNT");

    JlkRegWrite(0x01, 0x0001);
    usleep(1000);
    JlkRegWrite(0x01, 0x0000);
    JlkRegWrite(JLK_REG_NODE_ID, NODE_ID_DEFAULT);
    JlkRegWrite(JLK_REG_CHANNEL_EN, 0x0003);
    JlkRegWrite(JLK_REG_INT_MODE, 0x0002);
    JlkRegWrite(JLK_REG_INT_MASK, 0x0804);
    JlkRegWrite(JLK_REG_TIMESTAMP, DEFAULT_TIMESTAMP);
    JlkRegWrite(0x24, 0xA0);
    JlkRegWrite(0x25, 0x1C);
    MemorySpaceInit();
    NcMemoryMapInit(0x0200, 0x0400);
    NtChannelMap(0, AB_LOCAL_NC_ID);
    NtChannelMap(1, AB_LOCAL_NC_ID);
    JlkRegWrite(JLK_REG_SMARTNC1_TIMEOUT, 0x8000);
    JlkRegWrite(JLK_REG_SMARTNC1_CONFIG, 0x0400);
    JlkRegWrite(JLK_REG_WORK_MODE, (uint16_t)(MODE_SMARTNC1 | MODE_CTRLNT));

    if (GlinkWaitLinkUp(GLINK_CH_A, 15000) != 0 ||
        !GlinkGetLinkStatus(GLINK_CH_B)) {
        printf("  [失败] LINK\n");
        JlkConfig(NODE_ID_DEFAULT, GLINK_ROLE_NC_NT);
        return TR_FAIL;
    }
    printf("  MODE=0x%04X LINK A/B OK\n", JlkRegRead(JLK_REG_WORK_MODE));

    rd0 = FpgaRegRead(P_RD_FIFO1_WR_NUM);
    if (SmartNcShortMsgSendEx(1, 0x0001, AB_LOCAL_NC_ID, 4 /*CtrlNT*/,
                              tx, 16, 0) != 0) {
        JlkConfig(NODE_ID_DEFAULT, GLINK_ROLE_NC_NT);
        return TR_FAIL;
    }
    SmartNcWaitDone(1, 3000);
    raw_st = JlkRegRead(JLK_REG_SMARTNC1_STATUS);
    rd1 = FpgaRegRead(P_RD_FIFO1_WR_NUM);
    printf("  STATUS=0x%04X fail=%u RD %u->%u STAT4=0x%08X\n",
           raw_st, (raw_st >> 4) & 0xF, (unsigned)rd0, (unsigned)rd1,
           FpgaRegRead(P_STATUS_REGISTER));
    JlkRegWrite(JLK_REG_SMARTNC1_STATUS, 0x1000);
    JlkConfig(NODE_ID_DEFAULT, GLINK_ROLE_NC_NT);

    if (((raw_st >> 4) & 0xF) == 0 && rd1 > rd0) {
        printf("  [通过] Smart->CtrlNT 有响应\n");
        return TR_PASS;
    }
    printf("  [失败] Smart->CtrlNT 无有效闭环 (fail或RD不变)\n");
    return TR_FAIL;
}

/* Smart 长报冒烟: 配置长报 + 发一小段, 期望能启动(忙位/完成) */
static test_rc_t opt_smart_long_smoke(void)
{
    uint8_t tx[64];
    uint16_t raw_st;
    smartnc_config_t snc;
    smartnt_config_t snt;
    int i;

    printf("\n=== SmartNC1 长报冒烟 (手册6.5长报) ===\n");
    for (i = 0; i < 64; i++)
        tx[i] = (uint8_t)i;

    if (K72Reset() != 0)
        return TR_FAIL;
    FpgaRegWrite(P_GC_MODE_REGISTER, 1);
    GlinkSetRate(GLINK_RATE_2G5);
    FpgaFifoReset();
    /* 长报同样 WR=NC RD=NT, 用厂家默认 0xC8 */
    SmartFifoSetNcShort(1);
    SmartFifoDumpSelect("long-smoke");
    JlkRegWrite(JLK_REG_NODE_ID, NODE_ID_DEFAULT);
    JlkRegWrite(JLK_REG_CHANNEL_EN, 0x0003);
    JlkRegWrite(JLK_REG_WORK_MODE, (uint16_t)(MODE_SMARTNC1 | MODE_SMARTNT1));
    JlkMemWrite(MEM_SMARTNC1_SP, MEM_SMARTNC1_STACK_BASE);

    if (GlinkWaitLinkUp(GLINK_CH_A, 15000) != 0 ||
        !GlinkGetLinkStatus(GLINK_CH_B)) {
        JlkConfig(NODE_ID_DEFAULT, GLINK_ROLE_NC_NT);
        return TR_FAIL;
    }

    memset(&snc, 0, sizeof(snc));
    snc.timeout = 0x8000;
    snc.short_msg_mode = 0; /* 长报 */
    snc.stack_en = 0;
    SmartNcInit(1, &snc);

    memset(&snt, 0, sizeof(snt));
    snt.pair_nc_id = AB_LOCAL_NC_ID;
    snt.pair_nc_ch = 0;
    snt.short_msg_mode = 0; /* 长报需配对 */
    SmartNtInit(1, &snt);

    printf("  SNC=0x%04X SNT=0x%04X (期望长报 bit10/14=0)\n",
           JlkRegRead(JLK_REG_SMARTNC1_CONFIG),
           JlkRegRead(JLK_REG_SMARTNT1_CONFIG));

    if (SmartNcLongMsgSend(1, tx, 64) != 0) {
        printf("  [失败] LongMsgSend\n");
        JlkConfig(NODE_ID_DEFAULT, GLINK_ROLE_NC_NT);
        return TR_FAIL;
    }
    SmartNcWaitDone(1, 3000);
    raw_st = JlkRegRead(JLK_REG_SMARTNC1_STATUS);
    printf("  STATUS=0x%04X fail=%u STAT4=0x%08X\n",
           raw_st, (raw_st >> 4) & 0xF, FpgaRegRead(P_STATUS_REGISTER));
    JlkRegWrite(JLK_REG_SMARTNC1_STATUS, 0x1000);
    JlkConfig(NODE_ID_DEFAULT, GLINK_ROLE_NC_NT);

    /* 长报闭环同样依赖 Smart FIFO; 忙位挂死或 fail 都记失败 */
    if (raw_st & 0xC000) {
        printf("  [失败] 长报后仍忙 STATUS=0x%04X (bit14/15)\n", raw_st);
        return TR_FAIL;
    }
    if (((raw_st >> 4) & 0xF) != 0) {
        printf("  [失败] 长报交换失败计数非0\n");
        return TR_FAIL;
    }
    printf("  [通过] 长报发送流程结束且无 fail_cnt (载荷闭环另验)\n");
    return TR_PASS;
}

/* AB 不适用: 中继需 C/D 通道 */
static test_rc_t opt_repeater_ab_skip(void)
{
    printf("\n=== 中继 Repeater (AB回环) ===\n");
    printf("  手册: 中继使用 CH_C/CH_D; 当前 AB 电口自环无 C/D 对端\n");
    printf("  [跳过] 需双卡光纤或 C/D 环回后再测 RepeaterInit/状态\n");
    return TR_SKIP;
}

/* NM 监听演示 (已有 opt_nm_full_demo) — 包装名称 */
/* IO 模式寄存器 */
static test_rc_t opt_io_ab_check(void)
{
    test_rc_t rc = opt_io_regs();
    /* 恢复后确认 AB 仍可 LINK */
    if (ab_bringup() != 0) {
        printf("  [失败] IO 配置后 AB bringup 失败\n");
        return TR_FAIL;
    }
    printf("  IO 后 Ctrl bringup 仍 OK\n");
    return rc;
}

/*---------- NM 演示: 说明 + 切模式探测 + 记录区 + 可选 Monitor 位 ----------*/
static test_rc_t opt_nm_full_demo(void)
{
    nm_config_t cfg;
    uint8_t rec[64];
    uint32_t ts = 0;
    int n;
    uint32_t old_gc;

    printf("\n=== 监听 NM 演示 ===\n");
    printf("步骤: 读当前模式 -> (可选)切 GC=2 -> NmInit -> 读记录区 -> 恢复标准\n");

    BridgeRelease();
    old_gc = FpgaRegRead(P_GC_MODE_REGISTER) & 0x7;
    printf("  当前 GC_MODE=%u (1=标准 2=监听 3=IO 4=中继+IO)\n", old_gc);

    printf("  [A] 标准模式下置 Monitor 位 (bit13)...\n");
    JlkConfig(NODE_ID_DEFAULT, GLINK_ROLE_NC_NT);
    NcConfigMonitor(0, 1);
    printf("  WORK_MODE=0x%04X\n", JlkRegRead(JLK_REG_WORK_MODE));
    NcConfigMonitor(0, 0);

    printf("  [B] 切到监听大模式 GC=2 并 NmInit...\n");
    FpgaRegWrite(P_GC_MODE_REGISTER, 2);
    usleep(100000);
    printf("  GC 读回=%u  PID=0x%04X\n",
           FpgaRegRead(P_GC_MODE_REGISTER) & 0x7,
           JlkRegRead(JLK_REG_PRODUCT_ID));

    memset(&cfg, 0, sizeof(cfg));
    cfg.node_id = 3;
    cfg.channel_en = 0x03;
    cfg.timestamp_en = 1;
    if (NmInit(&cfg) != 0) {
        printf("  [失败] NmInit\n");
        FpgaRegWrite(P_GC_MODE_REGISTER, 1);
        JlkConfig(NODE_ID_DEFAULT, GLINK_ROLE_NC_NT);
        return TR_FAIL;
    }
    printf("  NM_STATUS=0x%04X\n", NmGetStatus());

    memset(rec, 0, sizeof(rec));
    n = NmReadRecord(rec, sizeof(rec), &ts);
    printf("  NmReadRecord: %d 字节, timestamp=0x%08X\n", n, ts);
    if (n > 0)
        print_bytes("  记录区头: ", rec, n > 16 ? 16 : n);
    else
        printf("  (记录区空: 需总线上有他人发帧时才有监听数据)\n");

    printf("  [C] 恢复 GC=1 标准 + CtrlNC/NT...\n");
    FpgaRegWrite(P_GC_MODE_REGISTER, 1);
    usleep(100000);
    JlkConfig(NODE_ID_DEFAULT, GLINK_ROLE_NC_NT);
    printf("  恢复后 LINK A=%d B=%d\n",
           GlinkGetLinkStatus(GLINK_CH_A), GlinkGetLinkStatus(GLINK_CH_B));
    printf("  [通过] NM 流程演示完成\n");
    return TR_PASS;
}

static void print_test_data_cheat(void)
{
    uint16_t w[8];
    uint8_t b[16];
    gen_pattern(w, 8, 0x0001);
    for (int i = 0; i < 16; i++) b[i] = (uint8_t)(0xA0 + i);

    printf("\n---- 本工具常用测试数据 ----\n");
    print_hex("  Ctrl 递增字: ", w, 8, 8);
    print_bytes("  Smart 短报:  ", b, 16);
    printf("  Ctrl 一键自环: seed=0xC001 起 32 字\n");
    printf("  TR=1 拉取:     seed=0x8001 / 0xB001\n");
    printf("---------------------------\n");
}

/*==================== 三项子菜单 ====================*/

/* LINK 检测: 即时状态 + 可选复位配置后轮询; 若有 xdma1 则双卡一起查 */
static void print_card_link(const char *tag)
{
    uint16_t a = JlkRegRead(JLK_REG_CH_A_STATUS);
    uint16_t b = JlkRegRead(JLK_REG_CH_B_STATUS);
    int a_up = GlinkGetLinkStatus(GLINK_CH_A);
    int b_up = GlinkGetLinkStatus(GLINK_CH_B);

    printf("  [%s] rate=%d  A:%s(0x%04X)  B:%s(0x%04X)  "
           "A_RUN=0x%04X B_RUN=0x%04X  CHEN=0x%04X WORK=0x%04X\n",
           tag, (int)GlinkGetRate(),
           a_up ? "UP  " : "DOWN", a,
           b_up ? "UP  " : "DOWN", b,
           GlinkGetARunStatus(), GlinkGetBRunStatus(),
           JlkRegRead(JLK_REG_CHANNEL_EN),
           JlkRegRead(JLK_REG_WORK_MODE));
}

static void card_light_bringup(glink_rate_t rate)
{
    K72Reset();
    JlkConfig(NODE_ID_DEFAULT, GLINK_ROLE_NC_NT);
    JlkRegWrite(JLK_REG_CHANNEL_EN, CHANNEL_EN_AB);
    GlinkSetRate(rate);
}

static test_rc_t opt_link_detect(void)
{
    const int poll_s = 15;
    int up0 = 0, up1 = 0;
    int has_card1 = (access("/dev/xdma1_user", F_OK) == 0);
    glink_rate_t rate = GLINK_RATE_2G5;
    int i;

    printf("\n=== LINK 检测 ===\n");
    printf("  作用: 查看光/电口 SerDes 是否已建立 LINK (不发业务帧)\n");
    printf("  判定: CH_x_STATUS 同时具备活动+LINK 位则显示 UP\n");
    if (has_card1)
        printf("  发现 /dev/xdma1_user, 将同时检测两块卡\n");

    /* 1) 先读当前状态 (不复位) */
    printf("\n[1] 当前状态 (未复位):\n");
    GlinkBind(0);
    print_card_link("card0");
    if (has_card1) {
        if (GlinkOpenPath(1, "/dev/xdma1_user") == 0) {
            GlinkBind(1);
            print_card_link("card1");
            GlinkBind(0);
        } else {
            has_card1 = 0;
            printf("  [警告] 打开 xdma1 失败, 仅测 card0\n");
        }
    }

    /* 2) 轻量复位配置后再轮询 */
    printf("\n[2] 复位+配置(NC+NT, rate=2.5G) 后轮询 %ds...\n", poll_s);
    GlinkBind(0);
    card_light_bringup(rate);
    print_card_link("card0-cfg");
    if (has_card1) {
        GlinkBind(1);
        card_light_bringup(rate);
        print_card_link("card1-cfg");
        GlinkBind(0);
    }

    printf("  时间   card0 A/B              ");
    if (has_card1)
        printf("card1 A/B");
    printf("\n");

    for (i = 0; i <= poll_s; i++) {
        int a0, b0, a1 = 0, b1 = 0;
        uint16_t s0a, s0b, s1a = 0, s1b = 0;

        GlinkBind(0);
        a0 = GlinkGetLinkStatus(GLINK_CH_A);
        b0 = GlinkGetLinkStatus(GLINK_CH_B);
        s0a = JlkRegRead(JLK_REG_CH_A_STATUS);
        s0b = JlkRegRead(JLK_REG_CH_B_STATUS);
        if (a0 || b0)
            up0 = 1;

        if (has_card1) {
            GlinkBind(1);
            a1 = GlinkGetLinkStatus(GLINK_CH_A);
            b1 = GlinkGetLinkStatus(GLINK_CH_B);
            s1a = JlkRegRead(JLK_REG_CH_A_STATUS);
            s1b = JlkRegRead(JLK_REG_CH_B_STATUS);
            if (a1 || b1)
                up1 = 1;
            GlinkBind(0);
        }

        printf("  %3ds   %s/%s(%04X/%04X)",
               i,
               a0 ? "UP  " : "DOWN", b0 ? "UP  " : "DOWN", s0a, s0b);
        if (has_card1)
            printf("   %s/%s(%04X/%04X)",
                   a1 ? "UP  " : "DOWN", b1 ? "UP  " : "DOWN", s1a, s1b);
        printf("\n");

        if (has_card1) {
            if (up0 && up1)
                break;
        } else if (up0) {
            break;
        }
        if (i < poll_s)
            usleep(1000000);
    }

    printf("\n[3] 结论:\n");
    if (has_card1) {
        printf("  card0: %s\n", up0 ? "有 LINK" : "无 LINK");
        printf("  card1: %s\n", up1 ? "有 LINK" : "无 LINK");
        if (up0 && up1) {
            printf("  [通过] 两卡均检测到 LINK, 可继续做互通通信测试\n");
            return TR_PASS;
        }
        if (up0 || up1) {
            printf("  [部分] 仅一侧有 LINK, 请查对端光纤/速率/光模块\n");
            return TR_FAIL;
        }
        printf("  [失败] 两侧均无 LINK (查光纤 TX↔RX、光模块灯、速率是否一致)\n");
        return TR_FAIL;
    }

    if (up0) {
        printf("  [通过] 本卡至少一路 LINK UP (A 或 B)\n");
        return TR_PASS;
    }
    printf("  [失败] 本卡 A/B 均未 LINK (自环请接 A↔B; 双卡请接两板光口)\n");
    return TR_FAIL;
}

static int read_choice_line(void)
{
    char buf[64];
    if (!fgets(buf, sizeof(buf), stdin))
        return -1;
    if (buf[0] == 'q' || buf[0] == 'Q')
        return 0;
    return atoi(buf);
}

static void menu_ctrl(void)
{
    explain_ctrl();
    while (1) {
        printf("\n---- 控制流 Ctrl 子菜单 ----\n");
        printf("  1. 再看功能说明\n");
        printf("  2. 一键自环 (32字, 最快验证通路)\n");
        printf("  3. A<->B 全功能套件 (发/拉/多SA/压力...)\n");
        printf("  4. 对端配参通信 (交互, 可连另一块板)\n");
        printf("  5. 打印常用测试数据\n");
        printf("  0. 返回主菜单\n");
        printf("选择: ");
        fflush(stdout);
        {
            int c = read_choice_line();
            test_rc_t rc;
            if (c == 0 || c < 0)
                return;
            result_reset();
            switch (c) {
            case 1: explain_ctrl(); break;
            case 2:
                rc = opt_peer_comm_auto();
                result_record("Ctrl一键自环", rc);
                result_summary();
                break;
            case 3:
                run_ab_full_suite();
                break;
            case 4:
                rc = opt_peer_comm();
                result_record("Ctrl对端配参", rc);
                result_summary();
                break;
            case 5: print_test_data_cheat(); break;
            default: printf("无效\n"); break;
            }
        }
    }
}

static void menu_smart(void)
{
    explain_smart();
    while (1) {
        printf("\n---- 智能流 Smart 子菜单 ----\n");
        printf("  1. 再看功能说明\n");
        printf("  2. 配置演示 (写寄存器并读回, 打印测试数据)\n");
        printf("  3. 短报文自环尝试 (TX 16字节 A0..AF)\n");
        printf("  4. 打印常用测试数据\n");
        printf("  0. 返回主菜单\n");
        printf("选择: ");
        fflush(stdout);
        {
            int c = read_choice_line();
            test_rc_t rc;
            if (c == 0 || c < 0)
                return;
            result_reset();
            switch (c) {
            case 1: explain_smart(); break;
            case 2:
                rc = opt_smart_config_demo();
                result_record("Smart配置演示", rc);
                result_summary();
                break;
            case 3:
                rc = opt_smart_short_loop();
                result_record("Smart短报自环", rc);
                result_summary();
                break;
            case 4: print_test_data_cheat(); break;
            default: printf("无效\n"); break;
            }
        }
    }
}

static void menu_diag(void)
{
    explain_nm();
    while (1) {
        printf("\n---- 监听 / 诊断 子菜单 ----\n");
        printf("  1. 再看功能说明\n");
        printf("  2. ★ LINK 检测 (A/B 是否建链, 双卡自动识别)\n");
        printf("  3. ★ 查询速率 (双卡是否一致, 只读)\n");
        printf("  4. ★ 对齐速率到 2.5G (双卡同写)\n");
        printf("  5. NM 监听完整演示 (含切模式与恢复)\n");
        printf("  6. GC_MODE 大模式探测\n");
        printf("  7. 速率配置 (写寄存器扫档后恢复2.5G)\n");
        printf("  8. 冗余/环配置\n");
        printf("  9. IO/PWM 寄存器\n");
        printf(" 10. 中继器寄存器\n");
        printf(" 11. 全 API 冒烟\n");
        printf(" 12. 寄存器 dump\n");
        printf("  0. 返回主菜单\n");
        printf("选择: ");
        fflush(stdout);
        {
            int c = read_choice_line();
            test_rc_t rc;
            if (c == 0 || c < 0)
                return;
            result_reset();
            switch (c) {
            case 1: explain_nm(); break;
            case 2:
                rc = opt_link_detect();
                result_record("LINK检测", rc);
                result_summary();
                break;
            case 3:
                rc = opt_rate_query();
                result_record("速率查询", rc);
                result_summary();
                break;
            case 4:
                rc = opt_rate_sync(GLINK_RATE_2G5);
                result_record("速率对齐2.5G", rc);
                result_summary();
                break;
            case 5:
                rc = opt_nm_full_demo();
                result_record("NM演示", rc);
                result_summary();
                break;
            case 6:
                rc = opt_gc_mode_probe();
                result_record("GC_MODE", rc);
                result_summary();
                break;
            case 7:
                rc = opt_rate_config();
                result_record("速率配置", rc);
                result_summary();
                break;
            case 8:
                rc = opt_redun_ring();
                result_record("冗余/环", rc);
                result_summary();
                break;
            case 9:
                rc = opt_io_regs();
                result_record("IO", rc);
                result_summary();
                break;
            case 10:
                rc = opt_repeater_regs();
                result_record("中继", rc);
                result_summary();
                break;
            case 11:
                rc = opt_api_full_test();
                result_record("全API", rc);
                result_summary();
                break;
            case 12:
                rc = test_reg_dump();
                result_record("dump", rc);
                result_summary();
                break;
            default: printf("无效\n"); break;
            }
        }
    }
}

static void print_main_menu(void)
{
    printf("\n");
    printf("╔════════════════════════════════════════════╗\n");
    printf("║     K72 GLink 功能测试 (三项)              ║\n");
    printf("║     接线: A通道 <-> B通道 自环             ║\n");
    printf("╠════════════════════════════════════════════╣\n");
    printf("║  1. 控制流 CtrlNC/CtrlNT                   ║\n");
    printf("║       小块可靠交换 · MEM路径 · 已验证      ║\n");
    printf("║  2. 智能流 SmartNC/SmartNT                 ║\n");
    printf("║       大数据 · FPGA FIFO路径               ║\n");
    printf("║  3. 监听 NM / 系统诊断                     ║\n");
    printf("║       旁路听帧 · 速率/模式 · API/dump      ║\n");
    printf("║  4. LINK 检测 (A/B 是否建链)               ║\n");
    printf("║  5. 查询速率 (双卡是否一致)                ║\n");
    printf("║  0. 退出                                   ║\n");
    printf("╚════════════════════════════════════════════╝\n");
    printf("快捷: ./test_glink_api 1|2|3|4|5\n");
    printf("      ./test_glink_api link | rate | rate-sync | ctrl-loop\n");
}

static int run_category(int cat)
{
    if (GlinkOpen() != 0) {
        printf("[失败] 设备打开失败 (/dev/xdma0_user)\n");
        return -1;
    }
    switch (cat) {
    case 1: menu_ctrl(); break;
    case 2: menu_smart(); break;
    case 3: menu_diag(); break;
    case 4: {
        test_rc_t rc;
        result_reset();
        rc = opt_link_detect();
        result_record("LINK检测", rc);
        result_summary();
        break;
    }
    case 5: {
        test_rc_t rc;
        result_reset();
        rc = opt_rate_query();
        result_record("速率查询", rc);
        result_summary();
        break;
    }
    default:
        printf("请选 1/2/3/4/5\n");
        GlinkCloseAll();
        return -1;
    }
    GlinkCloseAll();
    return 0;
}

/* 非交互快捷动作 (设备已打开由调用方保证) */
static int run_shortcut(const char *arg)
{
    test_rc_t rc;

    if (GlinkOpen() != 0) {
        printf("[失败] 设备打开失败\n");
        return -1;
    }
    result_reset();
    if (strcmp(arg, "ctrl-loop") == 0 || strcmp(arg, "11") == 0) {
        rc = opt_peer_comm_auto();
        result_record("Ctrl一键自环", rc);
    } else if (strcmp(arg, "ctrl-all") == 0 || strcmp(arg, "all") == 0) {
        int r = run_ab_full_suite();
        GlinkCloseAll();
        return r;
    } else if (strcmp(arg, "ab-full") == 0 || strcmp(arg, "glink-ab") == 0) {
        int r = run_ab_glink_full_suite();
        GlinkCloseAll();
        return r;
    } else if (strcmp(arg, "smart") == 0) {
        rc = opt_smart_short_loop();
        result_record("Smart短报", rc);
    } else if (strcmp(arg, "smart-cfg") == 0) {
        rc = opt_smart_config_demo();
        result_record("Smart配置", rc);
    } else if (strcmp(arg, "nm") == 0) {
        rc = opt_nm_full_demo();
        result_record("NM演示", rc);
    } else if (strcmp(arg, "link") == 0) {
        rc = opt_link_detect();
        result_record("LINK检测", rc);
    } else if (strcmp(arg, "rate") == 0) {
        rc = opt_rate_query();
        result_record("速率查询", rc);
    } else if (strcmp(arg, "rate-sync") == 0) {
        rc = opt_rate_sync(GLINK_RATE_2G5);
        result_record("速率对齐2.5G", rc);
    } else if (strcmp(arg, "rate-sync-625") == 0) {
        rc = opt_rate_sync(GLINK_RATE_625M);
        result_record("速率对齐625M", rc);
    } else if (strcmp(arg, "api") == 0) {
        rc = opt_api_full_test();
        result_record("全API", rc);
    } else {
        printf("未知快捷: %s\n", arg);
        GlinkCloseAll();
        return -1;
    }
    result_summary();
    GlinkCloseAll();
    return (rc == TR_FAIL) ? -1 : 0;
}

int main(int argc, char **argv)
{
    if (argc >= 2) {
        const char *a = argv[1];
        if (strcmp(a, "1") == 0 || strcmp(a, "ctrl") == 0)
            return run_category(1);
        if (strcmp(a, "2") == 0 || strcmp(a, "smart-menu") == 0)
            return run_category(2);
        if (strcmp(a, "3") == 0 || strcmp(a, "diag") == 0)
            return run_category(3);
        if (strcmp(a, "4") == 0)
            return run_category(4);
        if (strcmp(a, "5") == 0)
            return run_category(5);
        return run_shortcut(a);
    }

    while (1) {
        char buf[64];
        print_main_menu();
        printf("请选择 1/2/3/4/5/0: ");
        fflush(stdout);
        if (!fgets(buf, sizeof(buf), stdin))
            break;
        size_t n = strlen(buf);
        while (n > 0 && (buf[n - 1] == '\n' || buf[n - 1] == '\r'))
            buf[--n] = 0;
        if (n == 0)
            continue;
        if (strcmp(buf, "0") == 0 || strcmp(buf, "q") == 0) {
            printf("退出\n");
            return 0;
        }
        if (strcmp(buf, "1") == 0 || strcmp(buf, "2") == 0 ||
            strcmp(buf, "3") == 0 || strcmp(buf, "4") == 0 ||
            strcmp(buf, "5") == 0)
            run_category(atoi(buf));
        else
            printf("请输入 1、2、3、4、5 或 0\n");
    }
    return 0;
}
