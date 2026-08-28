# Smart「已启动、卡在忙」分析 (STATUS=0x8000)

日期: 2026-08-24  
程序: `test_smart_busy_diag` / `wd_probe` / `busy_cmp`

## 1. 状态位含义 (手册 5.2.11 REG 0x2B)

| 位 | 含义 | 卡死时观测 |
|----|------|------------|
| bit15 | SMARTNC **交换组**处于传输 | **一直为 1** |
| bit14 | SMARTNC **单次交换**处于传输 | **一直为 0** |
| bit[7:4] | 失败次数 (无响应/超时) | **一直为 0** |
| bit11 | FIFO 写溢出 | 0 |
| bit12 | 传输挂起 | 0 |
| bit[10:8] | A/B 发送阻塞 | 0 |

`ST=0x8000` = 交换组已占用，但单次交换未进入传输，且超时失败计数不增加。

## 2. 主机侧已排除的问题

### 2.1 数据确实写入并被 FPGA 抽走

`wd_probe` 实测:

```
pre WD=2
after write[0..3] WD=16,32,48,64   ← 每写 1 字计数 +16
after SEND_NUM=4  WD=64
after CTRL+1ms    WD=2  ST=8000     ← CTRL 后 WD 被抽空
```

结论: **往 0x1000 写数有效；CTRL 后 K72 TX FSM 已把 WD 灌给 JLK。**  
不是「卡在 P_NC_IDLE_WAIT 从未 SEND」。

### 2.2 与 STACK / CHEN / NODE 无关的共性

对比 C1(0440) / C2(0400) / C3(1000饥饿) / C4(短超时) / OLD-like / VND：
**全部**在 TRIG 后立刻 `ST=8000`，5s 内不变，`fail_cnt` 不增。

→ 卡死点在 **JLK1263 收到命令后的协议/链路完成路径**，不是某一个 init 位单独造成。

## 3. K72 FPGA 发送时序 (对照)

```
写 0x1000 × N  →  写 0x0008=N  →  写 0x0000 bit0
                      ↓
              WC_FIFO → TRIG → 等 IDLE=0 → 抽 WD → JLK_FIFO_WR
```

与厂家 `test_1263`「先 TRIG 再写 FIFO」在芯片管脚上不同，但对本桥接：
**CTRL 之后 WD 已排空**，说明本板 FPGA 喂数阶段已完成。

## 4. 根因判断 (按可能性)

### P0 — JLK 进入交换组忙后，短报单次交换未真正开跑

证据: bit15=1 且 bit14=0 长期并存；若已在等 NT 响应，通常会先有 bit14，随后超时 `fail_cnt++`。  
现超时不触发 → 更像 **命令未进入「等响应」阶段**（或超时逻辑未启动）。

### P1 — 同片 SmartNC+SmartNT + A↔B 自环，芯片不完成短报交换

厂家 FMC 工程亦是同片 0x0110，但直接驱 JLK 管脚；K72 经 FPGA FIFO。  
Ctrl 流 MEM 路径 AB 已通，说明 SerDes/链路物理可用；**Smart FIFO 路径仍可能未在网表/约束上跑通**。

### P2 — 喂数与 TRIG 时序相对 JLK 仍有毛刺

虽 WD 已排空，需 ILA 确认:
- `SMARTNC1_TRIG` 相对首拍 `JLK_FIFO_WR` 的先后
- `SMARTNC1_AFULL` 在 SEND 期间是否异常拉高截断
- 4 拍 WDATA 是否正好为 `0001 1002 0001 5555`

## 5. 给 FPGA 的抓波建议

触发: `SMARTNC1_TRIG` 上升沿  

同屏必看:

1. `r_nc1_tx_req` / `r_tx_fsm_state` (IDLE_WAIT→SEND→DONE?)
2. `WD_FIFO_EMPTY` / `WD_FIFO_RD_EN` / `JLK_FIFO_WR` / `JLK_FIFO_WDATA[15:0]`
3. `SMARTNC1_IDLE` / `SMARTNC1_AFULL` / `SMARTNC1_ERR`
4. `SMARTNT1_EMPTY` / `REQ` / `ACK` (若有)
5. FIFO_SEL: WR=00 RD=10

关注点:

- TRIG 后 `IDLE` 是否变 0？
- `JLK_FIFO_WR` 是否正好 4 拍？WDATA 对不对？
- SEND 之后 `IDLE` 是否一直 0（与 ST=8000 对应）？
- 有无任何 SmartNT 侧活动？

主机复现: `./test_smart_nc1_nt1` 或 `./test_smart_busy_diag`

## 6. 软件侧结论

| 项 | 结论 |
|----|------|
| 写 0x1000 | 正确，计数有增加 |
| CTRL 触发 | 正确，WD 被抽空，ST→8000 |
| 卡死位置 | **JLK 交换组忙、单次交换未跑、超时不至** |
| 软件可改项 | 已穷尽 SEL/init/帧长；需 FPGA/芯片侧波形 |

历史 `fail_cnt=1`（ST=0x0010）说明某些条件下超时路径能走完；当前稳定复现是 **busy 挂死**，两者都指向 Smart 交换未在链路上闭环，只是结束方式不同。
