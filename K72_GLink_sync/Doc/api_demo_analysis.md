# test_glink_api.c 分析文档

## 概述

`test_glink_api.c` 是基于 glink_api 封装层(L1 API)的 K72 GLink 板卡测试程序, 覆盖 JLK1263 寄存器配置、A↔B 通道自环通信、API 功能验证及 LINK 状态监控。程序以中文菜单方式交互, 用户选择测试项后自动执行对应的测试流程。

程序文件: `Code/demo/test_glink_api.c`
依赖头文件: `glink_api.h`, `glink_regs.h`
依赖库: `libglink_api.a` (静态库, 由 `Code/api/glink_api.c` 编译生成)
底层驱动: XDMA PCIe 内核模块 (设备名 `/dev/xdma0_user`)

---

## 三层架构

```
                          用户操作
                            |
                   test_glink_api (L2 测试层)
                   菜单驱动、参数选择、结果校验
                            |
                        glink_api (L1 封装层)
                   GlinkOpen / EmifRead / EmifWrite
                   FpgaRegRead / JlkRegRead / JlkMemRead
                            |
                     /dev/xdma0_user (L0 设备层)
                   mmap PCIe BAR + 寄存器读写
                   XDMA 内核驱动 xdma.ko
```

---

## API 列表 (glink_api.h)

### L0: 设备开关

| API | 功能 | L0实现方式 |
|-----|------|-----------|
| `GlinkOpen()` | 打开设备并 mmap | open() + mmap(), 自动回退到 sysfs |
| `GlinkClose()` | 关闭设备 | munmap() + close() |

### L0: XDMA 寄存器直接读写

| API | 功能 | L0实现方式 |
|-----|------|-----------|
| `XdmaWrite(addr, val)` | 写 XDMA BAR 寄存器 | 直接写 mmap 内存 |
| `XdmaRead(addr, *val)` | 读 XDMA BAR 寄存器 | 直接读 mmap 内存 |

### L1: BRIDGE 控制

| API | 功能 |
|-----|------|
| `BridgeRelease()` | 释放 INDIRECT BRIDGE 复位 |
| `BridgeReset()` | 拉低 INDIRECT BRIDGE 复位 |

### L1: EMIF 片选切换

| API | 功能 |
|-----|------|
| `EmifSetCeN(ce_n)` | 设置 CE_N[3:0] (0x7=FPGA, 0xB=JLK) |
| `EmifSelectFpga()` | 切到 FPGA 寄存器空间 |
| `EmifSelectJlk()` | 切到 JLK1263 空间 |

### L1: EMIF 间接读写

| API | 功能 | 数据流 |
|-----|------|--------|
| `EmifWrite(emif_addr, wdata)` | EMIF 写 | AR<-addr, WR<-data, ST<-WR_EN |
| `EmifRead(emif_addr, *rddata)` | EMIF 读 | AR<-addr, ST<-RD_EN, 轮询RX, ST<-FIFO_RD_EN, RD->data |

### L1: FPGA 寄存器读写

| API | 功能 |
|-----|------|
| `FpgaRegWrite(reg, val)` | 写 FPGA 内部寄存器 (CE_N=0x7) |
| `FpgaRegRead(reg)` | 读 FPGA 内部寄存器 |

### L1: JLK1263 REG 读写

| API | 功能 |
|-----|------|
| `JlkRegWrite(reg, val)` | 写 JLK1263 寄存器 (CE_N=0xB, bit18=0) |
| `JlkRegRead(reg)` | 读 JLK1263 寄存器 |

### L1: JLK1263 MEM 读写

| API | 功能 |
|-----|------|
| `JlkMemWrite(mem_off, val)` | 写 MEM 空间 (CE_N=0xB, bit18=1) |
| `JlkMemRead(mem_off)` | 读 MEM 空间 |

### L2: 高级配置接口

| API | 功能 |
|-----|------|
| `K72Reset()` | 复位整个 K72 板 (FPGA+JLK+FIFO) |
| `JlkConfig(node_id, role)` | 配置 JLK1263 (节点ID/通道/工作模式) |
| `MemorySpaceInit()` | 初始化 MEM 0x000-0x0FF 为 0xFFFF |
| `NcMemoryMapInit(stack, mem)` | 初始化 NC1 内存映射 |
| `NtChannelMap(ch, nc_id)` | 配置 NT 通道映射 |
| `GlinkGetLinkStatus(ch)` | 查询通道 LINK 状态 |
| `GlinkWaitLinkUp(ch, timeout)` | 等待 LINK UP |

### L2: 数据传输接口

| API | 功能 |
|-----|------|
| `FpgaFifoWrite(ch, data, count)` | 写数据到 FPGA FIFO |
| `NcTriggerSend(ch, send_num)` | 触发 NC 发送 |
| `NcWaitDone(ch, timeout)` | 等待 NC 发送完成 |
| `RxFifoGetCount(ch)` | 读取接收 FIFO 数据量 |
| `RxFifoRead(ch, buf, count)` | 从 RD_FIFO 读数据 |

### L2: 调试与诊断

| API | 功能 |
|-----|------|
| `FpgaGetDebug()` | 读 FPGA DEBUG 寄存器 (FIFO错误) |
| `JlkDumpAll()` | 打印全部 JLK1263 寄存器 |
| `FpgaDumpStatus()` | 打印 FPGA 关键状态 |

---

## 测试模式详解

### 模式 1: 交互式收发测试

**作用**: 用户自选节点角色和通道, 进行交互式收发测试。

**流程**:

```
选择参数:
  节点角色 (0=NC 1=NT 2=NC+NT自环)
  通道 (0=A 1=B)

配置 K72:
  JlkConfig(0x8003, role)

子菜单:
  1. NC 发送 32 字递增数据 (0x0001~0x0020)
     FpgaFifoWrite(ch, data, 32)
     NcTriggerSend(1, 32)
     NcWaitDone(1, 1000ms)
  2. NT 接收数据
     RxFifoGetCount(ch)
     RxFifoRead(ch, buf, count)
  3. 查询 LINK 状态
     GlinkGetLinkStatus(A/B)
  4. 打印全部 JLK1263 寄存器
     JlkDumpAll()
  5. 打印 FPGA 状态
     FpgaDumpStatus()
  0. 返回主菜单
```

---

### 模式 2: A↔B 通道自环测试

**作用**: 在同一块 K72 板上, A通道光口与B通道光口光纤直连, 验证 NC→NT 自环通信。

**硬件连接**:
```
K72 板:
  A通道光口 TX ──光纤──> B通道光口 RX
  A通道光口 RX <──光纤── B通道光口 TX
```

**流程**:

```
1. K72Reset()         - 复位 FPGA + JLK1263 + FIFO
2. JlkConfig(0x8003, NC_NT)  - 配置 NC+NT 双角色
3. MemorySpaceInit()  - 初始化 MEM 0x000-0x0FF
   NcMemoryMapInit()  - NC1 内存映射
   NtChannelMap()     - NT 通道映射
4. GlinkWaitLinkUp(A, 30s)  - 等待 A通道 LINK
   GlinkWaitLinkUp(B, 30s)  - 等待 B通道 LINK
5. FpgaFifoWrite(0, data, 32)  - 写 32 字到 FIFO1
   NcTriggerSend(1, 32)       - 触发 NC1 发送
   NcWaitDone(1, 1000ms)      - 等待发送完成
6. 轮询 RxFifoGetCount(0)     - 等待接收
   RxFifoRead(0, buf, n)      - 读数据
7. verify_data()              - 逐字节比对
8. FpgaGetDebug()             - 检查 FIFO 错误
```

**通过条件**:
- A/B 通道 LINK UP
- NC1 发送完成
- 收到 32 字数据且完全一致
- DEBUG 寄存器 = 0 (无 FIFO 错误)

---

### 模式 3: API 功能测试

**作用**: 逐个验证 16 个 API 函数的基本功能。

**测试项**:

| # | API | 测试方法 | 通过条件 |
|---|-----|---------|---------|
| 01 | GlinkOpen | 打开设备 | 返回 0 |
| 02 | BridgeRelease | 释放 BRIDGE 复位 | 返回 0 |
| 03 | EmifSelectFpga | 切 FPGA 片选 | 返回 0 |
| 04 | EmifSelectJlk | 切 JLK 片选 | 返回 0 |
| 05 | FpgaRegWrite/Read | 写读 0x4008 | 读出非零 |
| 06 | JlkRegWrite/Read | 写读 NODE_ID | 读回 0x8003 |
| 07 | JlkMemWrite/Read | 写读 MEM(0x102) | 读回 0x2000 |
| 08 | GlinkGetLinkStatus | 查询 LINK | 显示 A/B 状态 |
| 09 | K72Reset | 复位 K72 | 返回 0 |
| 10 | JlkConfig | 配置 JLK | 返回 0 |
| 11 | MemorySpaceInit | 初始化 MEM | 读回 0xFFFF |
| 12 | NcMemoryMapInit | NC 内存映射 | 读回正确值 |
| 13 | NtChannelMap | NT 通道映射 | 读回正确值 |
| 14 | FpgaFifoWrite | 写 FIFO | 写入 4 字 |
| 15 | JlkDumpAll | 打印寄存器 | 显示 16 个寄存器 |
| 16 | FpgaDumpStatus | 打印 FPGA 状态 | 显示状态信息 |

---

### 模式 4: LINK 状态监控

**作用**: 每 2 秒采样一次 A/B 通道 LINK 状态, 持续 30 秒。

**输出格式**:
```
  时间    A通道    B通道
  -----   ------   ------
   0s     UP(0x0007)  UP(0x0007)
   2s     UP(0x0007)  UP(0x0007)
   ...
```

---

## 辅助函数

| 函数 | 功能 |
|------|------|
| `gen_test_data(buf, size)` | 生成递增数据 `buf[i] = i+1` |
| `print_hex(prefix, buf, len, max_show)` | 十六进制打印, 最多显示 max_show 字 |
| `verify_data(a, b, len)` | 逐字比对, 返回首个差异偏移 (-1=一致) |
| `ch_name(ch)` | 通道号→名称字符串 |

---

## 重要设计点

### EMIF 间接访问时序

1. **写操作**: AR -> WR -> ST(WR_EN) -> 轮询 WR_EMPTY
2. **读操作**: AR -> ST(RD_EN) -> 轮询 RX_EMPTY -> ST(FIFO_RD_EN) -> RD
3. **两次读之间加延时**: 避免 RX FIFO 残留旧数据

### MEM 空间地址

- `MEM(x)` 对应 EMIF 地址 `0x40000 | x` (bit18=1)
- 同一 offset 的 REG 和 MEM 是独立存储, 不会相互影响
- 验证方法: 写 MEM(0x102)=0x2000, 读 REG(0x102) 应为不同值

### 片选缓存

- `g_current_ce` 缓存当前 CE_N, 避免重复设置
- 首次调用或切换时才真正写入 EF_ST_ADDR

### 通过/失败/跳过 标识

- `[通过]`: 测试项通过
- `[失败]`: 测试项失败 (附带详细信息)
- `[跳过]`: 因硬件原因跳过 (如端口不存在)

---

## 编译和运行

```bash
# 编译 API 静态库
cd Code/api/
make

# 编译测试程序
cd Code/demo/
make

# 运行 (需要 root 权限)
sudo ./test_glink_api
```

**注意**:
- 需要 root 权限访问 `/dev/xdma0_user`
- 需要先加载 `xdma.ko` 内核模块
- 若 `/dev/xdma0_user` 不存在, 程序自动回退到 sysfs 路径
