# 厂家 FMC FPGA 参考 (init_1263 / test_1263)

**注意 (2026-08-24): 厂家 FMC 管脚/桥接与 K72 不同，K72 软件与抓波
以本工程手册、原理图、`RTL_EMIF_IF.v` / `RTL_JLK_FIFO_IF.v` 为准，
不再把下列 init 值当作 K72 必须对齐项。**

下文仅作对照存档。

## 1. init_1263 寄存器序列 (CFG_NUM=7)

| # | Addr | Value | 含义 | 我们当前 | 差异 |
|---|------|-------|------|----------|------|
| 0 | 0x00 | 0x0001 | NODE_ID=1 | 0x8003 (ID=3+奇校验) | ID 不同 |
| 1 | 0x03 | 0x00C3 | CHEN A/B + bit[7:6] | 0x0003 | **我们缺 0x00C0** |
| 2 | 0x29 | 0x3000 | SmartNC1 TIMEOUT | 0x8000 | 超时门限不同 |
| 3 | 0x07 | 0x0005 | TIMESTAMP 1us | 0xFFFF | 时标不同 |
| 4 | 0x2A | 0x0440 | 短报(bit10)+堆栈使能(bit6) | 0x0400 | **我们缺 STACK_EN** |
| 5 | 0x3C | 0x4003 | SmartNT1 短报 + 低位=3 | 0x4000 | 多了 pair/ID 低位 |
| 6 | 0x02 | 0x0110 | SmartNC1\|SmartNT1 | 0x0110 | **一致** |

说明: 源码注释里 address/data 描述有多处笔误，以 `reg_data[]` 常量为准。

## 2. test_1263 FIFO_SEL (硬接线)

```
WR_SEL CH1 = {MUX1,MUX0} = 00 → SmartNC1
RD_SEL CH1 = {MUX1,MUX0} = 10 → SmartNT1
```

与厂家口头确认及我们的 **0xC8** 完全一致。否决 0xC0。

## 3. test_1263 短报帧

| 字段 | 厂家 | 我们 (16B) | 说明 |
|------|------|------------|------|
| CFG1 | 0x0001 | 0x0001 | SA 一致 |
| CFG2 | **0x1000** | 0x1010 | 厂家: 1路NT、len=0→512B；我们 len=16 |
| CFG3 | 0x0001 | 0x0003 | type=000 SmartNT1；ID=本端 NODE |
| DATA | 0x5555 (2B) | 16B A0..AF | 厂家 BYTE_CNT=2 |

厂家 CFG2 声明长度 512，却只写 2 字节载荷，参考工程自身不一致；但 **type=000 SmartNT1** 与我们一致，且 **不用 0x4001**。

## 4. 发送时序

厂家 FSM: **先 TRIG 脉冲 → 再写 CFG1/CFG2/CFG3/DATA**（看 AFULL）。

K72 `RTL_JLK_FIFO_IF`: 主机先填 WD_FIFO + SEND_NUM + CTRL → FPGA **先 TRIG 再从 WD 抽数给 JLK**。

对 K72：CTRL 前把 WD 备好即可。我们的 TX 顺序对 K72 正确。

## 5. SmartNT ACK

厂家: empty 上升沿脉冲 `SMARTNT1_ACK`；有数据时 RD 读 FIFO，读到 0x5555 点灯。

K72 `RTL_JLK_FIFO_IF.v` 含 `P_NT_ACK_GEN` 自动产生 ACK。主机一般不必手写 ACK。

## 6. 差异优先级

### P0 建议对齐复测
1. CHEN: `0x0003` → `0x00C3`
2. SNC CONFIG: `0x0400` → `0x0440` (短报+堆栈使能)
3. TIMEOUT: 试 `0x3000`
4. SNT: 试 `0x4003`
5. NODE_ID: 可试 `0x0001` + 目标 ID=1

### 已确认正确、勿改
- FIFO_SEL WR=NC1 RD=NT1 (0xC8)
- WORK_MODE 0x0110
- 表54 type=000 SmartNT1

### 厂家工程自身问题
- CFG2 len=0(512) vs 只写 2B
- init 注释与数值不符
