# K72 GLink 测试工程

K72 GLink 板卡的 XDMA + EMIF 寄存器读写与通信测试工程, 参照 `serial` 串口卡工程的三层架构设计。

## 快速开始

```bash
# 1. 编译 API 静态库
cd Code/api && make

# 2. 编译测试程序
cd Code/demo && make

# 3. 运行 (root 权限)
sudo ./test_glink_api
```

## 目录结构

```
K72_GLink/
├── Doc/                      # 文档
│   ├── 工程使用说明.md
│   └── api_demo_analysis.md
├── Code/
│   ├── api/                  # L1 API 封装层 (libglink_api.a)
│   │   ├── glink_regs.h     # 寄存器宏定义
│   │   ├── glink_api.h       # API 接口声明
│   │   ├── glink_api.c       # API 实现
│   │   └── Makefile
│   └── demo/                 # L2 测试层
│       ├── test_glink_api.c  # 测试程序
│       └── Makefile
└── README.md
```

## 架构

```
test_glink_api (L2 测试层)
       |
glink_api (L1 封装层: XDMA HAL + EMIF)
       |
/dev/xdma0_user (L0 设备层: mmap PCIe BAR)
```

## 测试项

1. **交互式收发测试** - 选角色/通道, 菜单驱动收发
2. **A↔B 通道自环测试** - 自动完整 NC→NT 自环验证
3. **API 功能测试** - 16 项 API 逐个验证
4. **LINK 状态监控** - 30 秒持续监控

## 依赖

- Linux (内核 4.19+)
- GCC 7.3+
- XDMA 内核模块 (xdma.ko)
- K72 GLink 板 (Kintex-7 + JLK1263N)
