#ifndef _GLINK_API_H_
#define _GLINK_API_H_

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/*============================================================
 * K72 GLink API 接口定义
 * 三层架构:
 *   L0 设备层: /dev/xdma0_user 或 /sys/bus/pci/devices/.../resource0
 *   L1 封装层: 本文件 (XDMA HAL + EMIF 间接访问)
 *   L2 测试层: test_glink_api.c
 *============================================================*/

/*----------------- 常量定义 -----------------------------------------*/
/* 通道选择 */
typedef enum {
    GLINK_CH_A = 0,    /* A通道 */
    GLINK_CH_B = 1,    /* B通道 */
    GLINK_CH_C = 2,    /* C通道 */
    GLINK_CH_D = 3     /* D通道 */
} glink_channel_t;

/* 节点角色 */
typedef enum {
    GLINK_ROLE_NC = 0,    /* 控制节点 (Controller Node) */
    GLINK_ROLE_NT = 1,    /* 目标节点 (Target Node) */
    GLINK_ROLE_NC_NT = 2  /* NC+NT 双角色 (自环测试) */
} glink_role_t;

/* 速率配置 */
typedef enum {
    GLINK_RATE_625M = 0,
    GLINK_RATE_1G   = 1,
    GLINK_RATE_2G5  = 5,    /* K72 默认 2.5Gbps */
    GLINK_RATE_5G   = 2
} glink_rate_t;

/*----------------- L0: 设备开关 ------------------------------------*/
#ifndef GLINK_MAX_DEV
#define GLINK_MAX_DEV  4
#endif

/**
 * @brief 打开 XDMA 设备并映射内存 (设备索引0, 兼容旧用法)
 * @return 成功返回0, 失败返回-1
 * @note 自动尝试 /dev/xdma0_user, 失败则回退到 sysfs 路径
 */
int GlinkOpen(void);

/**
 * @brief 按路径打开指定设备索引 (用于双卡互通等)
 * @param idx  0..GLINK_MAX_DEV-1
 * @param path 如 /dev/xdma0_user 或 /sys/bus/pci/devices/0000:01:00.0/resource0
 * @return 成功返回0, 失败返回-1
 */
int GlinkOpenPath(int idx, const char *path);

/**
 * @brief 切换当前操作的设备上下文 (后续 API 作用于该卡)
 * @param idx 已打开的设备索引
 * @return 成功返回0
 */
int GlinkBind(int idx);

/** @brief 当前绑定的设备索引, 未打开返回 -1 */
int GlinkCurrent(void);

/**
 * @brief 关闭当前绑定设备
 */
void GlinkClose(void);

/** @brief 关闭全部已打开设备 */
void GlinkCloseAll(void);

/*----------------- L0: XDMA 寄存器直接读写 -------------------------*/
/**
 * @brief 直接写 XDMA BAR 寄存器
 * @param addr BAR 偏移地址
 * @param val 32位数据
 * @return 成功返回0, 失败返回-1
 */
int XdmaWrite(uint32_t addr, uint32_t val);

/**
 * @brief 直接读 XDMA BAR 寄存器
 * @param addr BAR 偏移地址
 * @param val 读出的数据
 * @return 成功返回0, 失败返回-1
 */
int XdmaRead(uint32_t addr, uint32_t *val);

/*----------------- L1: BRIDGE 控制 ---------------------------------*/
/**
 * @brief 释放 INDIRECT BRIDGE 复位
 * @return 成功返回0
 */
int BridgeRelease(void);

/**
 * @brief 拉低 INDIRECT BRIDGE 复位
 */
int BridgeReset(void);

/*----------------- L1: EMIF 片选切换 --------------------------------*/
/**
 * @brief 设置 EMIF_CE_N 片选
 * @param ce_n 0x7=FPGA寄存器, 0xB=JLK1263
 * @return 成功返回0
 */
int EmifSetCeN(uint8_t ce_n);

/**
 * @brief 便捷函数: 切到 FPGA 寄存器空间
 */
int EmifSelectFpga(void);

/**
 * @brief 便捷函数: 切到 JLK1263 空间
 */
int EmifSelectJlk(void);

/*----------------- L1: EMIF 间接读写 (核心) ------------------------*/
/**
 * @brief EMIF 写 (通过 INDIRECT BRIDGE)
 * @param emif_addr 19位 EMIF 地址 (REG_ADDR 或 MEM_ADDR)
 * @param wdata 32位数据
 * @return 成功返回0
 */
int EmifWrite(uint32_t emif_addr, uint32_t wdata);

/**
 * @brief EMIF 读 (通过 INDIRECT BRIDGE)
 * @param emif_addr 19位 EMIF 地址
 * @param rddata 读出的数据
 * @return 成功返回0
 */
int EmifRead(uint32_t emif_addr, uint32_t *rddata);

/*----------------- L1: FPGA 寄存器读写 (CE_N=0x7) ------------------*/
/**
 * @brief 写 FPGA 内部寄存器
 * @param reg P_xxx 寄存器地址 (0x0000-0xF000)
 * @param val 32位数据
 */
int FpgaRegWrite(uint32_t reg, uint32_t val);

/**
 * @brief 读 FPGA 内部寄存器
 * @param reg P_xxx 寄存器地址
 * @return 读出的32位数据
 */
uint32_t FpgaRegRead(uint32_t reg);

/*----------------- L1: JLK1263 REG 读写 (CE_N=0xB, bit18=0) ---------*/
/**
 * @brief 写 JLK1263 寄存器
 * @param reg JLK_REG_xxx (0x00-0x0F)
 * @param val 16位数据
 */
int JlkRegWrite(uint32_t reg, uint16_t val);

/**
 * @brief 读 JLK1263 寄存器
 * @param reg JLK_REG_xxx
 * @return 16位数据
 */
uint16_t JlkRegRead(uint32_t reg);

/*----------------- L1: JLK1263 MEM 读写 (CE_N=0xB, bit18=1) --------*/
/**
 * @brief 写 JLK1263 MEM 空间
 * @param mem_off MEM 偏移 (16位 word 地址)
 * @param val 16位数据
 */
int JlkMemWrite(uint32_t mem_off, uint16_t val);

/**
 * @brief 读 JLK1263 MEM 空间
 * @param mem_off MEM 偏移
 * @return 16位数据
 */
uint16_t JlkMemRead(uint32_t mem_off);

/*----------------- L2: 高级配置接口 --------------------------------*/
/**
 * @brief 复位整个 K72 板 (FPGA + JLK1263 + FIFO)
 * @return 成功返回0
 */
int K72Reset(void);

/**
 * @brief 配置 JLK1263 寄存器 (节点ID/通道使能/工作模式)
 * @param node_id 节点ID (如 0x8003)
 * @param role 节点角色
 * @return 成功返回0
 */
int JlkConfig(uint16_t node_id, glink_role_t role);

/**
 * @brief 初始化 NC 内存映射 (MEM 空间)
 * @param stack_addr 发送栈底地址
 * @param mem_addr 发送内存地址
 * @return 成功返回0
 */
int NcMemoryMapInit(uint16_t stack_addr, uint16_t mem_addr);

/**
 * @brief 初始化 NT 通道映射
 * @param ch 通道号 (0=A, 1=B)
 * @param nc_id 对应 NC 的 ID
 * @return 成功返回0
 */
int NtChannelMap(int ch, uint16_t nc_id);

/**
 * @brief MemorySpaceInit: MEM(0x000~0x0FF) 填 0xFFFF
 */
int MemorySpaceInit(void);

/**
 * @brief 查询通道 LINK 状态
 * @param ch 通道号
 * @return 1=UP, 0=DOWN
 */
int GlinkGetLinkStatus(glink_channel_t ch);

/**
 * @brief 等待指定通道 LINK UP
 * @param ch 通道号
 * @param timeout_ms 超时(毫秒)
 * @return 0=LINK UP, -1=超时
 */
int GlinkWaitLinkUp(glink_channel_t ch, int timeout_ms);

/*----------------- L2: 数据传输接口 --------------------------------*/
/**
 * @brief 写数据到 FPGA FIFO (发送数据准备)
 * @param ch 通道号 (0=FIFO1, 1=FIFO2)
 * @param data 16位数据数组
 * @param count 数据个数
 * @return 实际写入个数
 */
int FpgaFifoWrite(int ch, const uint16_t *data, int count);

/**
 * @brief 触发 NC 发送
 * @param ch 通道号 (1-4 对应 NC1-NC4)
 * @param send_num 发送数据数量
 * @return 成功返回0
 */
int NcTriggerSend(int ch, uint32_t send_num);

/**
 * @brief 等待 NC 发送完成
 * @param ch 通道号 (1-4)
 * @param timeout_ms 超时
 * @return 0=完成, -1=超时
 */
int NcWaitDone(int ch, int timeout_ms);

/**
 * @brief 读取接收 FIFO 数据量
 * @param ch 通道号 (0=RC_FIFO1/RD_FIFO1, 1=RC_FIFO2/RD_FIFO2)
 * @return 数据量
 */
uint32_t RxFifoGetCount(int ch);

/**
 * @brief 从 RD_FIFO 读数据
 * @param ch 通道号 (0=FIFO1, 1=FIFO2)
 * @param buf 数据缓冲区
 * @param count 读取个数
 * @return 实际读取个数
 */
int RxFifoRead(int ch, uint16_t *buf, int count);

/*----------------- L2: 调试与诊断 ----------------------------------**/
/**
 * @brief 读 FPGA 调试寄存器 (FIFO 上溢/下溢错误)
 * @return 32位调试数据
 */
uint32_t FpgaGetDebug(void);

/**
 * @brief 打印全部 JLK1263 寄存器 (0x00-0x0F)
 */
void JlkDumpAll(void);

/**
 * @brief 打印 FPGA 关键寄存器状态
 */
void FpgaDumpStatus(void);

/*----------------- L2: ctrlNC 协议接口 ----------------------------**/
/**
 * @brief 配置 ctrlNC1 内存映射 (栈底+发送内存地址+交换块数)
 * @param stack_addr 发送栈底地址
 * @param mem_addr   发送内存地址
 * @param exch_count  交换块数
 * @return 成功返回0
 * @note 等价 demo configNC_Memory_Map()
 */
int CtrlNcMemoryMap(uint16_t stack_addr, uint16_t mem_addr, uint16_t exch_count);

/**
 * @brief 配置 ctrlNC 描述符 (发送给哪路NT, 字节数等)
 * @param mem_addr      发送内存地址
 * @param nt1_id..nt4_id 目标NT的ID
 * @param subaddress    子地址
 * @param tr            0=发送, 1=读取
 * @param byte_count   字节数 (word数*2)
 * @return 成功返回0
 * @note 等价 demo ConfigctrlNC_TargetNT()
 */
int CtrlNcConfigDescriptor(uint16_t mem_addr,
                           uint16_t nt1_id, uint16_t nt2_id,
                           uint16_t nt3_id, uint16_t nt4_id,
                           uint16_t subaddress, uint8_t tr,
                           uint16_t byte_count);

/**
 * @brief 写发送数据到 MEM 空间
 * @param mem_addr 发送内存地址
 * @param data 16位数据数组
 * @param word_count word个数
 * @return 成功返回0
 * @note 等价 demo ctrlnc_SendData()
 */
int CtrlNcSendData(uint16_t mem_addr, const uint16_t *data, int word_count);

/**
 * @brief 触发 ctrlNC 发送
 * @param ctrlnc1 1=触发 ctrlNC1
 * @param ctrlnc2 1=触发 ctrlNC2
 * @return 成功返回0
 * @note 等价 demo startctrlxmit()
 */
int CtrlNcStartXmit(int ctrlnc1, int ctrlnc2);

/**
 * @brief 等待 NC 发送完成 (EOE=1)
 * @param stack_addr 栈地址
 * @param timeout_ms 超时
 * @return 0=完成, -1=超时
 * @note 等价 demo getCtrlNcStatusWord()
 */
int CtrlNcWaitDone(uint16_t stack_addr, int timeout_ms);

/*----------------- L2: ctrlNT 协议接口 ----------------------------**/
/**
 * @brief 配置 ctrlNT 栈指针
 * @param stack_addr NT栈指针
 * @return 成功返回0
 * @note 等价 demo configNTSP()
 */
int CtrlNtSetStackPtr(uint16_t stack_addr);

/**
 * @brief 配置 ctrlNT 通道映射 (接收哪路NC的数据)
 * @param ch 1-4 ctrlNT通道
 * @param nc_type 0=ctrlNC1, 1=ctrlNC2, 2=smartNC1...
 * @param nc_id 对应NC的ID
 * @return 成功返回0
 * @note 等价 demo configctrlNTchanel()
 */
int CtrlNtChannelMap(int ch, uint16_t nc_type, uint16_t nc_id);

/**
 * @brief 配置 ctrlNT 接收内存地址
 * @param ch 1-4 ctrlNT通道
 * @param subaddress 子地址
 * @param recv_addr 接收内存地址
 * @return 成功返回0
 * @note 等价 demo config_recv_ctrlnt_memory()
 */
int CtrlNtConfigRecvMemory(int ch, uint16_t subaddress, uint16_t recv_addr);

/**
 * @brief 完整版: 配置 ctrlNT 接收内存地址
 * @param ch 1-4 ctrlNT通道
 * @param area 区域号
 * @param service 服务号
 * @param contrl_word 控制字 (0x200=中断使能)
 * @param subaddress 子地址
 * @param recv_addr 接收内存地址
 * @return 成功返回0
 */
int CtrlNtConfigRecvMemoryFull(int ch, uint16_t area, uint16_t service,
                                uint16_t contrl_word, uint16_t subaddress,
                                uint16_t recv_addr);

/**
 * @brief 配置 ctrlNT 发送内存地址
 * @param ch 1-4 ctrlNT通道
 * @param subaddress 子地址
 * @param send_addr 发送内存地址
 * @return 成功返回0
 * @note 等价 demo config_send_ctrlnt_memory()
 */
int CtrlNtConfigSendMemory(int ch, uint16_t subaddress, uint16_t send_addr);

/**
 * @brief 初始化未使用的 ctrlNT 通道 (置0防止误触发)
 * @param unused_begin_chanel 从第几路开始未使用
 * @return 成功返回0
 */
int CtrlNtInitUnusedChannel(uint16_t unused_begin_chanel);

/**
 * @brief 配置忙表 (子地址忙位)
 * @param ch ctrlNT通道
 * @param tr 0=接收子地址, 1=发送子地址
 * @param busy_subaddress 忙位子地址 (0-31)
 * @return 成功返回0
 */
int CtrlNtConfigBusyTable(uint16_t ch, uint16_t tr, uint16_t busy_subaddress);

/**
 * @brief 读取中断状态
 * @return 16位中断状态 (bit11=ctrlNT接收中断)
 */
uint16_t JlkGetIntStatus(void);

/**
 * @brief 等待 ctrlNT 接收中断
 * @param timeout_ms 超时
 * @return 0=收到中断, -1=超时
 */
int CtrlNtWaitInterrupt(int timeout_ms);

/**
 * @brief 轮询 NT 栈指针变化检测接收 (推荐用于自环模式)
 * @param initial_sp 配置时的初始栈指针 (CtrlNtSetStackPtr 的值)
 * @param timeout_ms 超时
 * @return 0=收到数据, -1=超时
 * @note 栈指针变化表示 NT 写入了一条接收记录
 */
int CtrlNtWaitRecv(uint16_t initial_sp, int timeout_ms);

/**
 * @brief 获取当前 ctrlNT 接收的数据块地址
 * @param nc_id 传出: 发送方NC ID
 * @param tr    传出: 0=发送 1=读取
 * @param subaddress 传出: 子地址
 * @param bytes_len 传出: 字节数
 * @return 数据块MEM地址
 * @note 等价 demo get_current_Target_NC_ID()
 */
uint16_t CtrlNtGetRecvBlock(uint16_t *nc_id, uint16_t *tr,
                             uint16_t *subaddress, uint16_t *bytes_len);

/**
 * @brief 读取当前 NT 栈指针
 * @return 当前栈指针值
 */
uint16_t CtrlNtGetCurrentSp(void);

/**
 * @brief 从指定栈指针处读取接收信息
 * @param current_sp 指定栈指针
 * @param nc_id 传出: 发送方NC ID
 * @param tr 传出: 0=发送 1=读取
 * @param subaddress 传出: 子地址
 * @param bytes_len 传出: 字节数
 * @return 数据块MEM地址
 */
uint16_t CtrlNtGetSpTargetNcId(uint16_t current_sp, uint16_t *nc_id,
                                uint16_t *tr, uint16_t *subaddress,
                                uint16_t *bytes_len);

/*----------------- L2: SmartNC/SmartNT 协议 -----------------------**/
/**
 * @brief 配置 smartNC1 超时
 * @param time_out 超时值
 * @return 成功返回0
 */
int SmartNc1ConfigTimeout(uint16_t time_out);

/**
 * @brief 配置 smartNC1 工作参数
 * @param reg 配置寄存器值
 * @return 成功返回0
 */
int SmartNc1Config(uint16_t reg);

/**
 * @brief 配置 smartNT 通道映射
 * @param smartnt_chanel 1-4 smartNT通道
 * @param smartnc_id smartNC的ID
 * @param smartnc_chanel 对应的NC通道
 * @param long_short_mode 1=短报文, 0=长报文
 * @return 成功返回0
 */
int SmartNtConfigChannel(uint16_t smartnt_chanel, uint16_t smartnc_id,
                          uint16_t smartnc_chanel, uint16_t long_short_mode);

/**
 * @brief 触发 smartNC 发送
 * @param soft_reset 1=软复位
 * @return 成功返回0
 * @note 等价 demo startxmit()
 */
int SmartNcStartXmit(int soft_reset);

/*----------------- L2: 完整版 NC/NT 配置 --------------------------**/
/**
 * @brief 配置 NC 内存映射 (组模式, 支持多交换块)
 * @param stack_addr 发送栈底地址
 * @param gap_time_us 交换块间隔时间(us)
 * @param mem_addr 发送内存地址
 * @param exch_count 交换块数
 * @return 成功返回0
 */
int CtrlNcMemoryMapGroup(uint16_t stack_addr, uint16_t gap_time_us,
                         uint16_t mem_addr, uint16_t exch_count);

/**
 * @brief 完整版 ctrlNC 描述符配置
 * @param mem_addr 内存地址
 * @param nt1_id..nt4_id 目标NT的ID
 * @param subaddress 子地址
 * @param tr 0=发送 1=读取
 * @param mode 0/1
 * @param state 0/1
 * @param int_en 1=中断使能
 * @param retry_en 1=重发使能
 * @param prior 1=高优先级
 * @param one_chanel 1=单通道
 * @param ch_b 0=A通道, 1=B通道
 * @param nt_num NT数量
 * @param nt1_type..nt4_type NT类型
 * @param byte_count 字节数
 * @return 成功返回0
 */
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
                               uint16_t byte_count);

/**
 * @brief 完整版 ctrlNC 触发发送
 * @param soft_reset 1=软复位
 * @param ctrlnc1 1=触发ctrlNC1
 * @param ctrlnc2 1=触发ctrlNC2
 * @return 成功返回0
 */
int CtrlNcStartXmitFull(int soft_reset, int ctrlnc1, int ctrlnc2);

/**
 * @brief 获取交换块状态
 * @param stack_addr 栈地址
 * @return 16位状态
 */
uint16_t CtrlNcGetExchangeBlockStatus(uint16_t stack_addr);

/**
 * @brief 配置 ctrlNC1 重发
 * @param retry 1=使能
 * @param retry_num 重发次数
 * @return 成功返回0
 */
int CtrlNc1ConfigRetry(uint16_t retry, uint16_t retry_num);

/**
 * @brief 配置 ctrlNC1 重发 (组模式, 带间隔使能)
 * @param retry 1=使能
 * @param retry_num 重发次数
 * @param gap_enable 1=使能间隔
 * @return 成功返回0
 */
int CtrlNc1ConfigRetryGroup(uint16_t retry, uint16_t retry_num, uint16_t gap_enable);

/**
 * @brief 配置 ctrlNT 寄存器 (REG(0x24)/REG(0x25))
 * @param reg1 寄存器1值
 * @param reg2 寄存器2值
 * @return 成功返回0
 */
int CtrlNtConfig(uint16_t reg1, uint16_t reg2);

/*----------------- L2: 通道状态查询 (阻塞/非阻塞) -----------------**/
/**
 * @brief 阻塞等待指定通道 LINK UP
 * @param ch 通道号 'A'/'B'
 * @return 成功返回0, 失败返回-1
 * @note 死等, 不超时
 */
int GlinkCheckChannelStatus(char ch);

/**
 * @brief 非阻塞查询指定通道 LINK 状态
 * @param ch 通道号 'A'/'B'
 * @return 1=UP, 0=DOWN
 */
int GlinkGetChannelStatus(char ch);

/*----------------- L2: 设备能力/硬件信息 --------------------------**/
/**
 * @brief 设备能力信息结构
 */
typedef struct {
    uint32_t fpga_version;       /* FPGA 版本 */
    uint32_t channel_num;        /* 通道数 */
    uint32_t port_num;           /* 端口数 */
    uint32_t bank_num;           /* Bank 数 */
    uint16_t jlK1263_reg_0a;     /* A通道状态 */
    uint16_t jlK1263_reg_0b;     /* B通道状态 */
} glink_capability_t;

/**
 * @brief 获取设备能力信息
 * @param cap 传出: 能力信息
 * @return 成功返回0
 */
int GlinkGetCapability(glink_capability_t *cap);

/**
 * @brief 获取硬件信息
 * @param fpga_version 传出: FPGA版本
 * @param jlK1263_id 传出: JLK1263 ID
 * @return 成功返回0
 */
int GlinkGetHardWareInfo(uint32_t *fpga_version, uint16_t *jlK1263_id);

/**
 * @brief 复位指定端口
 * @param port 端口号 (0=A, 1=B)
 * @return 成功返回0
 */
int GlinkResetPort(int port);

/*----------------- L2: 速率配置 --------------------------------**/
/**
 * @brief 设置通道速率
 * @param rate 速率枚举
 * @return 成功返回0
 */
int GlinkSetRate(glink_rate_t rate);

/**
 * @brief 查询当前通道速率
 * @return 速率枚举
 */
glink_rate_t GlinkGetRate(void);

/*----------------- L2: NC/NT 启停控制 ----------------------------**/
/**
 * @brief 启动 NC (设置工作模式)
 * @return 成功返回0
 */
int NcStart(void);

/**
 * @brief 停止 NC (清工作模式)
 * @return 成功返回0
 */
int NcStop(void);

/**
 * @brief 启动 NT (设置工作模式)
 * @return 成功返回0
 */
int NtStart(void);

/**
 * @brief 停止 NT (清工作模式)
 * @return 成功返回0
 */
int NtStop(void);

/**
 * @brief 触发 NC 非周期消息发送
 * @param msg_index 消息索引
 * @param high_priority 1=高优先级
 * @return 成功返回0
 */
int NcAperiodicRun(int msg_index, int high_priority);

/*----------------- L2: SA 级数据收发 (类WGLK220接口) -------------**/
/**
 * @brief NC: 填充数据到 SA
 * @param nc_id NC ID
 * @param nt_id NT ID
 * @param sa 子地址
 * @param data 数据
 * @param len 字节数
 * @return 成功返回0
 */
int NcSaFillData(uint16_t nc_id, uint16_t nt_id, uint16_t sa,
                  const uint8_t *data, int len);

/**
 * @brief NC: 从 SA 读数据
 * @param nc_id NC ID
 * @param nt_id NT ID
 * @param sa 子地址
 * @param buf 接收缓冲区
 * @param buf_len 缓冲区长度
 * @return 实际读取字节数
 */
int NcSaReadData(uint16_t nc_id, uint16_t nt_id, uint16_t sa,
                  uint8_t *buf, int buf_len);

/**
 * @brief NT: 添加 SA (接收使能)
 * @param ch ctrlNT通道
 * @param nc_id 对应NC ID
 * @param subaddress 子地址
 * @param enable_tx 1=发送使能
 * @param enable_rx 1=接收使能
 * @return 成功返回0
 */
int NtAddSa(int ch, uint16_t nc_id, uint16_t subaddress,
             int enable_tx, int enable_rx);

/**
 * @brief NT: 从 SA 读数据
 * @param ch ctrlNT通道
 * @param subaddress 子地址
 * @param buf 接收缓冲区
 * @param buf_len 缓冲区长度
 * @return 实际读取字节数
 */
int NtSaReadData(int ch, uint16_t subaddress, uint8_t *buf, int buf_len);

/*----------------- L2: 消息管理 (类WGLK220接口) ------------------**/
#define GLINK_MAX_MSG_NUM  16    /* 最大消息数 */

/**
 * @brief NC 消息配置结构
 */
typedef struct {
    uint16_t src_nc_id;      /* 源 NC ID */
    uint16_t dst_nt_id;      /* 目的 NT ID */
    uint16_t sa;              /* 子地址 */
    uint8_t  is_long;         /* 0=短消息, 1=长消息(SmartNC) */
    uint8_t  tr;              /* 0=发送, 1=读取 */
    uint16_t byte_count;      /* 字节数 */
    uint8_t  retry_en;        /* 1=重发使能 */
    uint8_t  int_en;          /* 1=中断使能 */
} glink_msg_t;

/**
 * @brief 分配 NC 消息缓冲区
 * @param periodic_num 周期消息数
 * @param aperiodic_num 非周期消息数
 * @return 成功返回0
 */
int NcAllocMsgBuf(int periodic_num, int aperiodic_num);

/**
 * @brief 配置 NC 消息
 * @param msg_index 消息索引
 * @param msg 消息配置
 * @return 成功返回0
 */
int NcSetMsg(int msg_index, const glink_msg_t *msg);

/**
 * @brief 查询 NC 消息配置
 * @param msg_index 消息索引
 * @param msg 传出: 消息配置
 * @return 成功返回0
 */
int NcGetMsg(int msg_index, glink_msg_t *msg);

/*----------------- L2: 增强功能 (P2) -----------------------------**/
/**
 * @brief 多播配置 (NT to NT 转发)
 * @param ch ctrlNT通道
 * @param enable 1=使能
 * @return 成功返回0
 */
int NcConfigMulticast(int ch, int enable);

/**
 * @brief NC Monitor 配置 (监听 NT to NT)
 * @param ch ctrlNT通道
 * @param enable 1=使能
 * @return 成功返回0
 */
int NcConfigMonitor(int ch, int enable);

/**
 * @brief 设置冗余模式 (A/B 冗余切换)
 * @param enable 1=使能冗余
 * @return 成功返回0
 */
int GlinkSetRedunMode(int enable);

/**
 * @brief 设置时间同步
 * @param timesynvalue 时间同步值
 * @param synerrorvalue 同步误差值
 * @param triggermode 触发模式
 * @return 成功返回0
 */
int GlinkSetTimeSyn(uint32_t timesynvalue, uint32_t synerrorvalue, uint32_t triggermode);

/*----------------- L2: loopback 自检 -----------------------------**/
/**
 * @brief JLK1263 内部 loopback 自检
 * @return 成功返回0, 失败返回-1
 * @note 检查 REG(0x0A)/REG(0x0B) 通道状态和 MEM 读写
 */
int GlinkLoopbackTest(void);

/**
 * @brief FIFO 复位 (P_FIFO_RESET_REGISTER)
 * @return 成功返回0
 */
int FpgaFifoReset(void);

/*----------------- L2: SmartNC 完整数据传输 (6.5) ------------------**/
/**
 * @brief SmartNC 配置结构
 */
typedef struct {
    uint16_t timeout;            /* 超时设置 */
    uint8_t  bandwidth;          /* 带宽: 0=50%, 1=25%, 2=12.5%, 3=6.25% */
    uint8_t  payload_size;       /* 负载: 0=512B, 1=256B, 2=128B, 3=64B */
    uint8_t  stack_depth;        /* 堆栈深度: 0=1K, 1=2K, 2=4K, 3=8K */
    uint8_t  stack_en;           /* 堆栈使能 */
    uint8_t  high_priority;      /* 高优先级 */
    uint8_t  short_msg_mode;     /* 短报文模式 */
    uint8_t  single_channel;     /* 单通道 */
    uint8_t  use_ch_b;           /* 使用B通道 */
} smartnc_config_t;

/**
 * @brief SmartNC 块状态字
 */
typedef struct {
    uint8_t  eoe;                /* 交换结束 */
    uint8_t  soe;                /* 交换开始 */
    uint8_t  work_mode;          /* 0=大数据流, 1=控制流 */
    uint8_t  error;              /* 错误 */
    uint8_t  busy;               /* 忙 */
    uint8_t  exch_err;           /* 交换错误 */
    uint8_t  rx_timeout;         /* 接收超时 */
    uint8_t  version_err;        /* 版本比对错误 */
} smartnc_status_t;

/**
 * @brief 初始化 SmartNC (完整版)
 * @param ch 1-4 SmartNC通道
 * @param cfg 配置参数
 * @return 成功返回0
 */
int SmartNcInit(int ch, const smartnc_config_t *cfg);

/**
 * @brief 配置 SmartNC 栈指针
 * @param ch 1-4 SmartNC通道
 * @param stack_addr 栈底地址
 * @return 成功返回0
 */
int SmartNcSetStackPtr(int ch, uint16_t stack_addr);

/**
 * @brief 读取 SmartNC 当前栈指针
 * @param ch 1-4 SmartNC通道
 * @return 当前栈指针
 */
uint16_t SmartNcGetCurrentSp(int ch);

/**
 * @brief SmartNC 长报文发送数据
 * @param ch 1-4 SmartNC通道
 * @param data 数据
 * @param byte_count 字节数 (1~4G-1)
 * @return 成功返回0
 * @note 数据通过FPGA FIFO接口发送
 */
int SmartNcLongMsgSend(int ch, const uint8_t *data, uint32_t byte_count);

/**
 * @brief SmartNC 短报文发送数据 (裸封装, 默认 offset=1 / NT=0x06 / SmartNT1)
 * @note 推荐改用 SmartNcShortMsgSendEx 明确对端参数
 */
int SmartNcShortMsgSend(int ch, const uint8_t *data, uint16_t byte_count);

/**
 * @brief SmartNC 短报文发送 (手册表54 命令+载荷)
 * @param ch          1-4 SmartNC
 * @param offset_or_sa 子地址/偏移 (word0)
 * @param nt_id       目标 NT ID (低12位)
 * @param nt_type     0=SmartNT1 .. 3=SmartNT4, 4=CtrlNT
 * @param data        载荷 (可为NULL且 byte_count=0)
 * @param byte_count  1~512 (0 表示 512)
 * @param retry_en    重传使能
 * @return 0=触发成功 (不代表对端已收齐)
 */
int SmartNcShortMsgSendEx(int ch, uint16_t offset_or_sa,
                          uint16_t nt_id, uint8_t nt_type,
                          const uint8_t *data, uint16_t byte_count,
                          int retry_en);

/**
 * @brief SmartNC 等待发送完成
 * @param ch 1-4 SmartNC通道
 * @param timeout_ms 超时
 * @return 0=完成, -1=超时
 */
int SmartNcWaitDone(int ch, int timeout_ms);

/** 读 P_FIFO_SELECT 低 8 位 */
uint32_t SmartFifoGetSelect(void);

/**
 * 短报 SmartNCx→SmartNTx: WR=NCx, RD=NTx (厂家确认; ch1 → 0xC8)
 * 勿用 WR=RD=NC 的 0xC0
 */
int SmartFifoSetNcShort(int ch);

/** 短报发完后轮询 RD_FIFO (保持 WR=NC RD=NT) */
int SmartNcWaitRdFifo(int ch, int timeout_ms);

/** 打印 SEL 及 F1_WR/F1_RD 解码, 便于与 FPGA ILA 对照 */
void SmartFifoDumpSelect(const char *tag);

/**
 * @brief 读取 SmartNC 交换状态
 * @param ch 1-4 SmartNC通道
 * @param status 传出: 状态字解析
 * @return 原始状态字
 */
uint16_t SmartNcGetStatus(int ch, smartnc_status_t *status);

/**
 * @brief 从 SmartNC 堆栈读取交换描述块
 * @param ch 1-4 SmartNC通道
 * @param sp 栈指针
 * @param status_word 传出: 块状态字
 * @param resp_time 传出: 响应时间
 * @param soe_time 传出: 开始时间戳
 * @param eoe_time 传出: 结束时间戳
 * @param nt_id 传出: NT ID
 * @param exch_len 传出: 交换字节长度
 * @return 成功返回0
 */
int SmartNcGetDescBlock(int ch, uint16_t sp, uint16_t *status_word,
                         uint16_t *resp_time, uint16_t *soe_time,
                         uint16_t *eoe_time, uint16_t *nt_id,
                         uint16_t *exch_len);

/*----------------- L2: SmartNT 完整数据接收 (6.6) ------------------**/
/**
 * @brief SmartNT 配置结构
 */
typedef struct {
    uint16_t pair_nc_id;         /* 配对SmartNC的ID */
    uint8_t  pair_nc_ch;         /* 配对SmartNC通道 0-3 */
    uint8_t  short_msg_mode;     /* 短报文模式 */
} smartnt_config_t;

/**
 * @brief 初始化 SmartNT (完整版)
 * @param ch 1-4 SmartNT通道
 * @param cfg 配置参数
 * @return 成功返回0
 */
int SmartNtInit(int ch, const smartnt_config_t *cfg);

/**
 * @brief SmartNT 长报文接收数据
 * @param ch 1-4 SmartNT通道
 * @param buf 接收缓冲区
 * @param buf_len 缓冲区长度
 * @param src_nc_id 传出: 源NC ID
 * @param src_nc_type 传出: 源NC类型
 * @return 实际接收字节数, -1=错误
 * @note 数据格式: [NC_ID|NC_TYPE][LEN_H][LEN_L][数据...]
 */
int SmartNtLongMsgRecv(int ch, uint8_t *buf, int buf_len,
                        uint16_t *src_nc_id, uint8_t *src_nc_type);

/**
 * @brief SmartNT 短报文接收数据
 * @param ch 1-4 SmartNT通道
 * @param buf 接收缓冲区
 * @param buf_len 缓冲区长度
 * @param cmd 传出: 命令编码
 * @return 实际接收字节数, -1=错误
 */
int SmartNtShortMsgRecv(int ch, uint8_t *buf, int buf_len, uint16_t *cmd);

/**
 * @brief SmartNT 短报文发送数据 (NT->NC)
 * @param ch 1-4 SmartNT通道
 * @param data 数据
 * @param byte_count 字节数 (1~512)
 * @return 成功返回0
 */
int SmartNtShortMsgSend(int ch, const uint8_t *data, uint16_t byte_count);

/**
 * @brief SmartNT 等待数据到达
 * @param ch 1-4 SmartNT通道
 * @param timeout_ms 超时
 * @return 0=有数据, -1=超时
 */
int SmartNtWaitRecv(int ch, int timeout_ms);

/*----------------- L2: CtrlNT 高级功能 ----------------------------**/
/**
 * @brief CtrlNT 模式码处理配置
 * @param ch ctrlNT通道
 * @param mode_code 模式码
 * @return 成功返回0
 */
int CtrlNtModeCodeProcess(int ch, uint16_t mode_code);

/**
 * @brief CtrlNT 增强型模式码处理
 * @param ch ctrlNT通道
 * @param enhance_mode 增强模式码
 * @return 成功返回0
 */
int CtrlNtEnhanceModeCode(int ch, uint16_t enhance_mode);

/**
 * @brief CtrlNT 命令非法配置
 * @param ch ctrlNT通道
 * @param illegal_cmd 非法命令字
 * @return 成功返回0
 */
int CtrlNtIllegalCmdConfig(int ch, uint16_t illegal_cmd);

/*----------------- L2: 16个双向IO口 (标准模式) --------------------**/
/**
 * @brief 设置 GPIO 方向
 * @param mask 16位掩码 (1=输出, 0=输入)
 * @return 成功返回0
 */
int GpioSetDirection(uint16_t mask);

/**
 * @brief 设置 GPIO 输出电平
 * @param value 16位电平值
 * @return 成功返回0
 */
int GpioSetOutput(uint16_t value);

/**
 * @brief 读取 GPIO 回读电平
 * @return 16位回读值
 */
uint16_t GpioReadback(void);

/*----------------- L2: 监听模式 NM (第7章) ------------------------**/
/**
 * @brief NM 配置结构
 */
typedef struct {
    uint16_t node_id;           /* 终端ID */
    uint16_t channel_en;       /* 通道使能 */
    uint8_t  ring_enable;      /* 环功能使能 */
    uint8_t  bandwidth_stats;  /* 带宽统计使能 */
    uint8_t  fault_detect;     /* 故障检测使能 */
    uint8_t  timestamp_en;     /* 时间戳使能 */
} nm_config_t;

/**
 * @brief 初始化监听模式 NM
 * @param cfg 配置参数
 * @return 成功返回0
 * @note 需要芯片工作在监听模式 (MODE=010)
 */
int NmInit(const nm_config_t *cfg);

/**
 * @brief NM 读取监听帧记录
 * @param buf 接收缓冲区
 * @param buf_len 缓冲区长度
 * @param timestamp 传出: 时间戳
 * @return 实际读取字节数
 */
int NmReadRecord(uint8_t *buf, int buf_len, uint32_t *timestamp);

/**
 * @brief NM 获取监听状态
 * @return 状态字
 */
uint16_t NmGetStatus(void);

/*----------------- L2: IO模式 (第8章) ----------------------------**/
/**
 * @brief IO模式配置结构
 */
typedef struct {
    uint16_t chip_id;          /* 芯片ID */
    uint8_t  safe_mode;        /* 安全模式 */
    uint8_t  redun_mode;       /* 冗余模式 */
    uint8_t  ctrl_src_id[3];   /* 控制源1/2/3 ID */
    uint8_t  ring_node_mode;   /* 环节点模式 */
    uint16_t default_output;   /* IO输出默认值 */
} io_mode_config_t;

/**
 * @brief 初始化 IO模式
 * @param cfg 配置参数
 * @return 成功返回0
 * @note 需要芯片工作在IO模式 (MODE=011)
 */
int IoModeInit(const io_mode_config_t *cfg);

/**
 * @brief IO输出 (PWM)
 * @param channel IO通道 (0-63)
 * @param duty_cycle 占空比 (0-100)
 * @param period 周期
 * @return 成功返回0
 */
int IoPwmOutput(int channel, uint8_t duty_cycle, uint16_t period);

/**
 * @brief IO输出 (电平)
 * @param channel IO通道 (0-63)
 * @param level 电平 (0/1)
 * @return 成功返回0
 */
int IoLevelOutput(int channel, int level);

/**
 * @brief IO回读 (被动读取)
 * @param channel IO通道 (0-31)
 * @return 电平值 0/1, -1=错误
 */
int IoReadback(int channel);

/**
 * @brief IO回读主动发送配置
 * @param channel IO通道 (0-31)
 * @param enable 1=使能
 * @return 成功返回0
 */
int IoReadbackAutoSend(int channel, int enable);

/**
 * @brief 智能接口配置
 * @param cmd 指令集
 * @param data 数据
 * @param len 数据长度
 * @return 成功返回0
 */
int SmartInterfaceConfig(uint16_t cmd, const uint8_t *data, int len);

/**
 * @brief 智能接口触发CPU
 * @return 成功返回0
 */
int SmartInterfaceTriggerCpu(void);

/**
 * @brief 智能接口复位CPU
 * @return 成功返回0
 */
int SmartInterfaceResetCpu(void);

/**
 * @brief 智能接口清空FIFO
 * @return 成功返回0
 */
int SmartInterfaceClearFifo(void);

/*----------------- L2: 中继器配置 (5.4) ---------------------------**/
/**
 * @brief 中继器配置结构
 */
typedef struct {
    uint8_t  repeater_num;     /* 中继器编号 */
    uint8_t  ch_c_enable;      /* C通道使能 */
    uint8_t  ch_d_enable;      /* D通道使能 */
    uint8_t  ring_mode;        /* 环模式 (0=交换网络, 1=环网络) */
    uint8_t  bandwidth_stats;  /* 带宽统计 */
    uint8_t  mark_primitive;   /* mark原语发送 */
} repeater_config_t;

/**
 * @brief 初始化中继器
 * @param cfg 配置参数
 * @return 成功返回0
 * @note 需要芯片工作在中继器+IO模式 (MODE=100)
 */
int RepeaterInit(const repeater_config_t *cfg);

/**
 * @brief 中继器软复位
 * @return 成功返回0
 */
int RepeaterReset(void);

/**
 * @brief 读取中继器C通道状态
 * @return 状态字
 */
uint16_t RepeaterGetChCStatus(void);

/**
 * @brief 读取中继器D通道状态
 * @return 状态字
 */
uint16_t RepeaterGetChDStatus(void);

/**
 * @brief 读取中继器版本
 * @return 版本号
 */
uint16_t RepeaterGetVersion(void);

/*----------------- L2: 帧记录功能 (5.2.13) -------------------------**/
/**
 * @brief 使能帧记录功能
 * @param filter_en 帧过滤使能
 * @param record_en 帧记录使能
 * @return 成功返回0
 */
int FrameRecordEnable(int filter_en, int record_en);

/**
 * @brief 配置帧过滤目标
 * @param nc_nt_type NC/NT类型 (0-10)
 * @param terminal_id 终端ID
 * @return 成功返回0
 */
int FrameRecordSetFilter(uint8_t nc_nt_type, uint16_t terminal_id);

/**
 * @brief 读取帧记录
 * @param index 帧索引 (0-255)
 * @param frame_info 传出: 帧信息 (8字)
 * @return 成功返回0
 */
int FrameRecordRead(int index, uint16_t frame_info[8]);

/*----------------- L2: 运行状态查询 ------------------------------**/
/**
 * @brief 读取A通道运行状态
 * @return 状态字
 */
uint16_t GlinkGetARunStatus(void);

/**
 * @brief 读取B通道运行状态
 * @return 状态字
 */
uint16_t GlinkGetBRunStatus(void);

/*----------------- L2: 环网络功能 --------------------------------**/
/**
 * @brief 使能环网络功能
 * @param enable 1=使能
 * @return 成功返回0
 */
int GlinkEnableRing(int enable);

/**
 * @brief 配置环节点带宽分配
 * @param bandwidth 0=6.25%, 1=12.5%, 2=25%, 3=50%
 * @return 成功返回0
 */
int GlinkConfigRingBandwidth(uint8_t bandwidth);

/**
 * @brief 配置帧传输延迟超时
 * @param timeout 0=16us, 1=32us, 2=64us, 3=128us
 * @return 成功返回0
 */
int GlinkConfigFrameTimeout(uint8_t timeout);

#ifdef __cplusplus
}
#endif

#endif /* _GLINK_API_H_ */
