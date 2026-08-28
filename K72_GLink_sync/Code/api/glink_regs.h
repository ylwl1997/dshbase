#ifndef _GLINK_REGS_H_
#define _GLINK_REGS_H_

/*============================================================
 * K72 GLink 寄存器定义
 * 依据: glinkfpga寄存器说明.docx / EMIF_IF.v / JLK1263 软件设计指南
 * 访问路径: XDMA PCIe -> INDIRECT BRIDGE -> EMIF 总线 -> JLK1263 / FPGA
 *============================================================*/

/*----------------- XDMA INDIRECT BRIDGE 寄存器 (PCIe BAR 偏移) -----------*/
#define EF_WR_ADDR     0x10000    /* 写数据寄存器: 写入32位数据到EMIF */
#define EF_RD_ADDR     0x10004    /* 读数据寄存器: 读出EMIF返回的32位数据 */
#define EF_AR_ADDR     0x10008    /* 地址寄存器: 19位EMIF地址 (bit18=MEM标志) */
#define EF_ST_ADDR     0x1000C    /* 状态/控制寄存器 */

/* EF_ST_ADDR 控制位 */
#define EF_WR_EN       0x00000001    /* 写使能: 写1按AR+WR执行EMIF写 */
#define EF_RD_EN       0x00000002    /* 读使能: 写1按AR执行EMIF读, 数据进FIFO */
#define EF_RD_CLEAN    0x00000004    /* 清除读数据有效位 */
#define EF_CE_N_WE     0x00000008    /* CE_N[3:0] 写使能 (BIT3=1 才能写 BIT4-7) */
#define EF_FIFO_RD_EN  0x00000100    /* RX FIFO 读使能: 锁存数据到 EF_RD_ADDR */

/* EF_ST_ADDR 状态位 (只读) */
#define EF_ST_WR_EMPTY 0x00010000    /* 写FIFO空 (写操作完成) */
#define EF_ST_WR_FULL  0x00020000    /* 写FIFO满 */
#define EF_ST_TX_WR_BUSY 0x00040000  /* TX FIFO 写忙 */
#define EF_ST_TX_RD_BUSY 0x00080000  /* TX FIFO 读忙 */
#define EF_ST_RX_EMPTY 0x00100000    /* RX FIFO 空(1) / 非空(0,有数据) */
#define EF_ST_RX_FULL  0x00200000    /* RX FIFO 满 */
#define EF_ST_RX_WR_BUSY 0x00400000  /* RX FIFO 写忙 */
#define EF_ST_RX_RD_BUSY 0x00800000  /* RX FIFO 读忙 */

/* BRIDGE 复位寄存器 (PCIe BAR 偏移 0x10) */
#define EF_BRIDGE_RST  0x10
#define BRIDGE_RST_RELEASE 0x1   /* 1=释放复位, 才能开始工作 */
#define BRIDGE_RST_PULL    0x0   /* 0=拉低复位 */

/*----------------- EMIF 片选 CE_N[3:0] 编码 ---------------------------*/
#define CE_N_FPGA      0x7     /* 访问 FPGA 内部寄存器 (0x0000-0xF000) */
#define CE_N_JLK1263   0xB     /* 访问 JLK1263 CPU 端口 (REG/MEM) */

/*----------------- EMIF 地址空间 -------------------------------------*/
/* EMIF_EA[18:0] 19位地址, bit18=I_MEM_ACCESS 区分 REG/MEM 空间 */
#define EMIF_ADDR_MASK 0x3FFFF      /* 18位地址掩码 */
#define MEM_ACCESS_BIT 0x40000       /* bit18=1: MEM 空间 */
#define REG_ADDR(x)    ((x) & EMIF_ADDR_MASK)             /* REG(x)地址 */
#define MEM_ADDR(x)    (MEM_ACCESS_BIT | ((x) & 0xFFFF))  /* MEM(x)地址 */

/*----------------- FPGA 内部寄存器 (CE_N=0x7) -----------------------*/
/* 控制与状态寄存器 0x0000-0x003C */
#define P_CTRL_REGISTER          0x0000    /* 控制寄存器 (读:状态标志 / 写:触发请求) */
#define P_STATUS_REGISTER        0x0004    /* 状态寄存器 (只读) */
#define P_NC1_SEND_NUM          0x0008    /* NC1 发送数据数量 */
#define P_NC2_SEND_NUM          0x000C    /* NC2 发送数据数量 */
#define P_NC3_SEND_NUM          0x0010    /* NC3 发送数据数量 */
#define P_NC4_SEND_NUM          0x0014    /* NC4 发送数据数量 */
#define P_NT1_SEND_NUM          0x0018    /* NT1 发送数据数量 (低9位) */
#define P_NT2_SEND_NUM          0x001C    /* NT2 发送数据数量 (低9位) */
#define P_NT3_SEND_NUM          0x0020    /* NT3 发送数据数量 (低9位) */
#define P_NT4_SEND_NUM          0x0024    /* NT4 发送数据数量 (低9位) */
#define P_WD_FIFO1_WR_NUM       0x0028    /* WD_FIFO1 已写入数据量 */
#define P_WD_FIFO2_WR_NUM       0x002C    /* WD_FIFO2 已写入数据量 */
#define P_RC_FIFO1_WR_NUM       0x0030    /* RC_FIFO1 已写入数据量 */
#define P_RC_FIFO2_WR_NUM       0x0034    /* RC_FIFO2 已写入数据量 */
#define P_RD_FIFO1_WR_NUM       0x0038    /* RD_FIFO1 已写入数据量 */
#define P_RD_FIFO2_WR_NUM       0x003C    /* RD_FIFO2 已写入数据量 */

/* 数据写入与发送寄存器 0x1000-0x3000 */
#define P_FIFO1_WRITE_REGISTER  0x1000    /* FIFO1 数据写入 (EMIF_ED_IN[15:0]) */
#define P_FIFO1_SEND_RAM_WRITE  0x1004    /* FIFO1 发送 RAM 写控制 */
#define P_FIFO2_WRITE_REGISTER  0x2000    /* FIFO2 数据写入 */
#define P_FIFO2_SEND_RAM_WRITE  0x2004    /* FIFO2 发送 RAM 写控制 */
#define P_DATA_READ_REGISTER    0x3000    /* 数据读取 (RD_FIFO1/2 读使能) */

/* 系统配置与复位寄存器 0x4000-0x5000 */
#define P_JLK_RESET_REGISTER    0x4000   /* JLK 复位 (bit0=I_RESET_N) */
#define P_FIFO_SELECT_REGISTER  0x4004   /* FIFO 通道选择 */
#define P_CLK_FREQ_SEL_REGISTER  0x4008  /* SerDes 时钟频率选择 (4位) */
#define P_GC_MODE_REGISTER      0x400C   /* JLK 工作模式 (3位, 需FPGA支持) */
#define P_FIFO_RESET_REGISTER   0x5000   /* FIFO 复位 (bit0=FIFO_RST 脉冲) */

/* 调试寄存器 */
#define P_DEBUG_REGISTER        0xF000   /* FIFO 上溢/下溢错误标志 */

/* P_CTRL_REGISTER 触发位 */
#define CTRL_NC1_TX    0x0001    /* 触发 NC1 发送 */
#define CTRL_NC2_TX    0x0002    /* 触发 NC2 发送 */
#define CTRL_NC3_TX    0x0004    /* 触发 NC3 发送 */
#define CTRL_NC4_TX    0x0008    /* 触发 NC4 发送 */
#define CTRL_NT1_TX    0x0010    /* 触发 NT1 发送 */
#define CTRL_NT2_TX    0x0020    /* 触发 NT2 发送 */
#define CTRL_NT3_TX    0x0040    /* 触发 NT3 发送 */
#define CTRL_NT4_TX    0x0080    /* 触发 NT4 发送 */
#define CTRL_NC1_RD    0x0100    /* 触发 NC1 读请求 */
#define CTRL_NC2_RD    0x0200
#define CTRL_NC3_RD    0x0400
#define CTRL_NC4_RD    0x0800
#define CTRL_NT1_RD    0x1000
#define CTRL_NT2_RD    0x2000
#define CTRL_NT3_RD    0x4000
#define CTRL_NT4_RD    0x8000

/* P_STATUS_REGISTER 状态位 */
#define ST_NC1_DONE    0x0001    /* NC1 任务完成 */
#define ST_NC2_DONE    0x0002
#define ST_NC3_DONE    0x0004
#define ST_NC4_DONE    0x0008
#define ST_NT1_DONE    0x0010
#define ST_NT2_DONE    0x0020
#define ST_NT3_DONE    0x0040
#define ST_NT4_DONE    0x0080

/*----------------- JLK1263 寄存器 (CE_N=0xB, REG空间) ---------------*/
/* REG 地址 = EMIF 地址低16位, 通过 REG_ADDR(x) 计算 */
#define JLK_REG_NODE_ID          0x00    /* 节点ID (bit15使能, bit0-14 ID) */
#define JLK_REG_RESERVED_01      0x01
#define JLK_REG_WORK_MODE        0x02    /* 工作模式使能 (bit0=ctrlNC1 等) */
#define JLK_REG_CHANNEL_EN       0x03    /* A/B通道发送/接收使能 */
#define JLK_REG_INT_MODE         0x04    /* 中断模式 */
#define JLK_REG_INT_MASK         0x05    /* 中断屏蔽 */
#define JLK_REG_RESERVED_06      0x06
#define JLK_REG_TIMESTAMP        0x07    /* 时间戳间隔 (1us/step, 默认5) */
#define JLK_REG_PRODUCT_ID      0x08    /* 产品ID (只读) */
#define JLK_REG_VERSION          0x09    /* 版本号 (只读) */
#define JLK_REG_CH_A_STATUS      0x0A    /* A通道状态 (bit0=活动, bit1=LINK) */
#define JLK_REG_CH_B_STATUS      0x0B    /* B通道状态 */
#define JLK_REG_CH_C_STATUS      0x0C    /* C通道状态 */
#define JLK_REG_CH_D_STATUS      0x0D    /* D通道状态 */
#define JLK_REG_RESERVED_0E      0x0E
#define JLK_REG_RESERVED_0F      0x0F
#define JLK_REG_CTRLNC1_RETRY    0x18    /* ctrlNC1 重发参数 */

/* JLK_REG_WORK_MODE 使能位 */
#define MODE_CTRLNC1    0x0001   /* ctrlNC1 使能 */
#define MODE_CTRLNT     0x0002   /* ctrlNT 使能 */
#define MODE_SMARTNC1   0x0010   /* smartNC1 使能 */
#define MODE_SMARTNC2   0x0020
#define MODE_SMARTNC3   0x0040
#define MODE_SMARTNC4   0x0080
#define MODE_SMARTNT1   0x0100   /* smartNT1 使能 */
#define MODE_SMARTNT2   0x0200
#define MODE_SMARTNT3   0x0400
#define MODE_SMARTNT4   0x0800
#define MODE_CTRLNC2    0x1000   /* ctrlNC2 使能 */
#define MODE_MONITOR     0x2000  /* 监听使能 */

/* JLK_REG_NODE_ID 默认配置 (bit15=1 节点使能) */
#define NODE_ID_DEFAULT 0x8003   /* 默认节点ID=0x03 */

/* JLK_REG_CHANNEL_EN 默认配置 */
#define CHANNEL_EN_AB   0x00C3  /* A/B 通道发送/接收使能 */

/* JLK LINK 状态位 (REG 0x0A-0x0D) */
#define LINK_ACTIVE     0x0001  /* bit0: 通道活动 */
#define LINK_UP         0x0002  /* bit1: LINK 建立 */

/*----------------- JLK1263 MEM 空间 (CE_N=0xB, bit18=1) -------------*/
/* MEM 地址通过 MEM_ADDR(x) 计算, x 是 16位 word 偏移 */
#define MEM_ADDR_SPACE_INIT_BASE  0x000   /* MemorySpaceInit 起始 (0x000~0x0FF 填0xFFFF) */
#define MEM_NC1_BASE              0x100   /* NC1 内存映射基址 */
#define MEM_NC1_EXCH_COUNT        0x100   /* NC1 交换块数 */
#define MEM_NC1_ID                0x101   /* NC1 节点ID */
#define MEM_NC1_STACK_L           0x102   /* NC1 发送栈底地址低16位 */
#define MEM_NC1_MEM_L             0x103   /* NC1 发送内存地址低16位 */
#define MEM_NC1_STACK_H           0x104   /* 栈底地址高16位 */
#define MEM_NC1_MEM_H             0x105   /* 发送内存地址高16位 */

#define MEM_NT_BASE               0x120   /* ctrlNT 通道映射基址 */
#define MEM_NT_CH1                0x120   /* ctrlNT 通道1: NC_ID | 0x8000 | (NC_type<<12) */
#define MEM_NT_CH2                0x121   /* ctrlNT 通道2 */
#define MEM_NT_CH3                0x122
#define MEM_NT_CH4                0x123

/*----------------- 默认配置参数 -------------------------------------*/
#define DEFAULT_SERDES_RATE       0x5    /* FPGA 0x4008 默认 2.5Gbps */
#define DEFAULT_TIMESTAMP         0x0005 /* 1us 时间戳间隔 */
#define DEFAULT_CTRLNC1_RETRY    0xC440 /* retry=1次, 重传2次 */

/* XDMA 设备路径 */
#define XDMA_USER_DEV     "/dev/xdma0_user"
#define XDMA_SYSFS_DEV    "/sys/bus/pci/devices/0000:87:00.0/resource0"
#define XDMA_MAP_SIZE     0x800000   /* 8MB 映射 */

/*----------------- SmartNC 寄存器 (5.2.11) --------------------------*/
#define JLK_REG_SMARTNC1_TIMEOUT   0x29    /* 第1路SmartNC超时设置 */
#define JLK_REG_SMARTNC2_TIMEOUT   0x2E
#define JLK_REG_SMARTNC3_TIMEOUT   0x33
#define JLK_REG_SMARTNC4_TIMEOUT   0x38
#define JLK_REG_SMARTNC1_CONFIG    0x2A    /* 第1路SmartNC配置 */
#define JLK_REG_SMARTNC2_CONFIG    0x2F
#define JLK_REG_SMARTNC3_CONFIG    0x34
#define JLK_REG_SMARTNC4_CONFIG    0x39
#define JLK_REG_SMARTNC1_STATUS    0x2B    /* 第1路SmartNC交换状态 */
#define JLK_REG_SMARTNC1_RUN       0x2C    /* 运行状态: bit[15:8]外部触发计数 bit[11:8]业务发起 */
#define JLK_REG_SMARTNC2_STATUS    0x30
#define JLK_REG_SMARTNC3_STATUS    0x35
#define JLK_REG_SMARTNC4_STATUS    0x3A

/* SmartNC 配置寄存器位定义 */
#define SMARTNC_BW_50              0x0000  /* 50%带宽 */
#define SMARTNC_BW_25              0x0001
#define SMARTNC_BW_12              0x0002
#define SMARTNC_BW_6               0x0003
#define SMARTNC_PAYLOAD_512        0x0000  /* 512字节 */
#define SMARTNC_PAYLOAD_256        0x0004
#define SMARTNC_PAYLOAD_128        0x0008
#define SMARTNC_PAYLOAD_64         0x000C
#define SMARTNC_STACK_DEPTH_1K      0x0000  /* 1KB/64条 */
#define SMARTNC_STACK_DEPTH_2K      0x0010
#define SMARTNC_STACK_DEPTH_4K      0x0020
#define SMARTNC_STACK_DEPTH_8K      0x0030
#define SMARTNC_STACK_EN           0x0040  /* 堆栈使能 */
#define SMARTNC_HIGH_PRI           0x0080  /* 高优先级 */
#define SMARTNC_SHORT_MSG          0x0400  /* 短报文模式 */
#define SMARTNC_SINGLE_CH          0x0800  /* 单通道 */
#define SMARTNC_CH_B               0x1000  /* 使用B通道 */

/*----------------- SmartNT 寄存器 (5.2.12) --------------------------*/
#define JLK_REG_SMARTNT1_CONFIG    0x3C    /* 第1路SmartNT配置 */
#define JLK_REG_SMARTNT2_CONFIG    0x3D
#define JLK_REG_SMARTNT3_CONFIG    0x3E
#define JLK_REG_SMARTNT4_CONFIG    0x3F

/* SmartNT 配置寄存器位定义 */
#define SMARTNT_SHORT_MSG          0x4000  /* 短报文接收模式 */

/*----------------- 帧记录寄存器 (5.2.13) ----------------------------*/
#define JLK_REG_FRAME_RECORD_CFG   0x4C    /* 帧记录配置 */
#define JLK_REG_FRAME_FILTER_DSID  0x4D    /* 帧过滤目标D_ID/S_ID */
#define MEM_FRAME_RECORD_BASE      0x3000  /* 帧信息记录表基址 */
#define MEM_FRAME_RECORD_SIZE      0x800   /* 256条 * 16字节 */

/*----------------- SmartNC MEM 空间 --------------------------------*/
#define MEM_SMARTNC1_SP            0x0108  /* 第1路SmartNC栈指针 */
#define MEM_SMARTNC2_SP            0x0109
#define MEM_SMARTNC3_SP            0x010A
#define MEM_SMARTNC4_SP            0x010B
#define MEM_SMARTNC1_STACK_BASE    0x3000  /* 第1路SmartNC堆栈 */
#define MEM_SMARTNC2_STACK_BASE    0x4000
#define MEM_SMARTNC3_STACK_BASE    0x5000
#define MEM_SMARTNC4_STACK_BASE    0x6000
#define MEM_SMARTNC_STACK_SIZE     0x1000  /* 每路4KB */

/* SmartNC 描述块大小 (16字 = 32字节) */
#define SMARTNC_DESC_BLOCK_SIZE    16

/* SmartNC 运行状态寄存器1 (0x2B等) — 软件指南 5.2.11, 勿与描述块状态字混淆 */
#define SMARTNC_REG_FAIL_CNT_MASK  0x00F0  /* bit[7:4] 失败次数 */
#define SMARTNC_REG_BLK_A          0x0100  /* bit8  A通道发送阻塞 */
#define SMARTNC_REG_BLK_B          0x0200  /* bit9  B通道发送阻塞 */
#define SMARTNC_REG_BLK_AB         0x0400  /* bit10 A+B阻塞 */
#define SMARTNC_REG_FIFO_OVF       0x0800  /* bit11 FIFO写溢出(NC1) */
#define SMARTNC_REG_SUSPEND        0x1000  /* bit12 运行挂起, 写1清除 */
#define SMARTNC_REG_EXCH_BUSY      0x4000  /* bit14 交换运行忙 */
#define SMARTNC_REG_XFER_BUSY      0x8000  /* bit15 传输业务忙 */

/* SmartNC 描述块状态字位定义 (堆栈, 非 0x2B) */
#define SMARTNC_ST_EOE             0x8000  /* 交换结束 */
#define SMARTNC_ST_SOE             0x4000  /* 交换开始 */
#define SMARTNC_ST_MODE            0x2000  /* 0=大数据流, 1=控制流 */
#define SMARTNC_ST_ERROR           0x1000  /* 错误 */
#define SMARTNC_ST_BUSY            0x0800  /* 忙 */
#define SMARTNC_ST_EXCH_ERR        0x0400  /* 交换错误 */
#define SMARTNC_ST_RX_TIMEOUT      0x0200  /* 接收超时 */

/*----------------- IO 模式寄存器 (5.5) -----------------------------*/
/* IO模式通过 MEM 地址访问, 基址 0x100000 (bit18=1, bit19=0) */
#define IO_REG_CHIP_ID             0x100   /* 芯片ID */
#define IO_REG_CTRL_SRC1_ID        0x101   /* 控制源1 ID */
#define IO_REG_CTRL_SRC2_ID        0x102   /* 控制源2 ID */
#define IO_REG_CTRL_SRC3_ID        0x103   /* 控制源3 ID */
#define IO_REG_WHITELIST1          0x104   /* 白名单1 */
#define IO_REG_WHITELIST2          0x105   /* 白名单2 */
#define IO_REG_WHITELIST_SAFE      0x106   /* 白名单及安全模式 */
#define IO_REG_TARGET_NT           0x107   /* 目标NT配置 */
#define IO_REG_FUNC_REPEATER       0x108   /* 功能及中继器配置 */
#define IO_REG_SMARTNC_TRANS       0x109   /* SmartNC传输配置 */
#define IO_REG_TIMESTAMP_CFG       0x10A   /* 时间戳配置 */
#define IO_REG_FIFO_EN             0x10B   /* 数据缓存FIFO使能 */
#define IO_REG_SMARTNC_SEND        0x10C   /* SmartNC发送配置 */
#define IO_REG_IO_READBACK_CFG     0x10D   /* IO回读配置 */
#define IO_REG_SMART_INTF_TX_FIFO  0x10E   /* 智能接口主动发送 */
#define IO_REG_SMART_INTF_CFG      0x10F   /* 智能接口配置 */
#define IO_REG_SMART_INTF_INFO     0x110   /* 智能接口信息记录 */
#define IO_REG_SMART_INTF_FILTER   0x111   /* 智能接口滤波参数 */

/* IO 输出/回读寄存器 */
#define IO_REG_OUTPUT_LEVEL        0x200   /* IO输出电平 (16位) */
#define IO_REG_OUTPUT_DIR          0x201   /* IO方向 (0=输入, 1=输出) */
#define IO_REG_READBACK_DATA       0x202   /* IO回读数据 */
#define IO_REG_PWM_CFG             0x203   /* PWM配置 */
#define IO_REG_PWM_DUTY            0x204   /* PWM占空比 */
#define IO_REG_PWM_PERIOD          0x205   /* PWM周期 */

/* IO模式 中继器配置 */
#define IO_REPEATER_NUM            0x300   /* 中继器编号 */
#define IO_REPEATER_RESET          0x301   /* 中继器复位 */
#define IO_REPEATER_FUNC           0x302   /* 中继器功能配置 */

/*----------------- 监听模式寄存器 (5.3) -----------------------------*/
/* 监听模式 NM 寄存器 */
#define NM_REG_CTRLNC1_STATUS      0x10    /* NM模式 ctrlNC1 状态 */
#define NM_REG_NT_STATUS           0x11    /* NM模式 NT 状态 */
#define NM_REG_NM_STATUS           0x12    /* NM 状态 */
#define NM_REG_NM_TIMESTAMP        0x13    /* NM 时间戳 */

/* NM MEM 空间 */
#define MEM_NM_RECORD_BASE         0x7000  /* NM 监听记录基址 */
#define MEM_NM_RECORD_SIZE         0x1000  /* 4KB 记录空间 */

/*----------------- 中继器寄存器 (5.4) ------------------------------*/
/* 中继器通过 MEM 地址高6位=000100 访问 */
#define REPEATER_BASE_ADDR         0x100000  /* 中继器寄存器基址 */
#define REPEATER_REG_NUM           0x00    /* 中继器编号 */
#define REPEATER_REG_RESET         0x01    /* 复位与控制 */
#define REPEATER_REG_FUNC          0x02    /* 功能配置 */
#define REPEATER_REG_VERSION       0x03    /* 版本 */
#define REPEATER_REG_CHC_STATUS    0x04    /* C通道状态 */
#define REPEATER_REG_CHD_STATUS    0x05    /* D通道状态 */

/*----------------- CtrlNT 模式码相关 --------------------------------*/
#define CTRLNT_MODE_CODE_BASE      0x240   /* CtrlNT模式码处理基址 */
#define CTRLNT_ENHANCE_MODE_BASE   0x280   /* 增强型模式码基址 */
#define CTRLNT_ILLEGAL_CFG_BASE    0x2C0   /* 命令非法配置基址 */

/*----------------- 16个双向IO口 (标准模式) --------------------------*/
#define GPIO_REG_BASE              0x500   /* 16个IO口基址 */
#define GPIO_REG_OUTPUT            0x500   /* 输出电平 */
#define GPIO_REG_DIRECTION         0x501   /* 方向 (0=输入, 1=输出) */
#define GPIO_REG_READBACK          0x502   /* 回读 */

/*----------------- SmartNC FIFO 接口 (FPGA侧) ----------------------*/
/* SmartNC 通过 FPGA FIFO 接口进行数据传输 */
#define FPGA_SMARTNC_FIFO1_BASE    0x1000  /* FIFO1: SmartNC1/2, SmartNT1/2 */
#define FPGA_SMARTNC_FIFO2_BASE    0x2000  /* FIFO2: SmartNC3/4, SmartNT3/4 */
#define FPGA_SMARTNC_FIFO_STATUS   0x4004  /* FIFO通道选择 */

/*----------------- 运行状态信息寄存器 ------------------------------*/
#define JLK_REG_RUN_STATUS_BASE    0x50    /* 运行状态信息基址 */
#define JLK_REG_A_RUN_STATUS       0x50    /* A通道运行状态 */
#define JLK_REG_B_RUN_STATUS       0x51    /* B通道运行状态 */

/*----------------- 速率枚举扩展 ------------------------------------*/
#define GLINK_RATE_0G5             0x0    /* 0.5Gbps */
#define GLINK_RATE_0G625           0x1    /* 0.625Gbps */
#define GLINK_RATE_1G              0x2    /* 1Gbps */
#define GLINK_RATE_2G              0x3    /* 2Gbps */
#define GLINK_RATE_2G5             0x5    /* 2.5Gbps */
#define GLINK_RATE_4G              0x6    /* 4Gbps */
#define GLINK_RATE_4G25            0x7    /* 4.25Gbps */
#define GLINK_RATE_5G              0x8    /* 5Gbps */

#endif /* _GLINK_REGS_H_ */
