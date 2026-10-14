<p align="center">
  <a href="README.md"><b>English</b></a> · <a href="README.zh.md"><b>简体中文</b></a>
</p>

# dshbase 🎛️

> **DeepSeek Harness 的插件宇宙**

[dshbase.com](https://dshbase.com) 是 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)（官方开源 Agent 框架，口号「一切皆插件」）的社区插件目录，**中英双语**、实时更新。我们把散落在 GitHub 各处的 DSH 插件**收编成册**——每个插件都有安装命令、验证状态、实时 Star 数，**不用再点进仓库一个个翻了**。

## ✨ 这里有什么

| 亮点 | 说明 |
|---|---|
| 🧩 **1700+ 插件** | 覆盖 15 大类：开发工具 / UI 与皮肤 / 知识 / 自动化 / 网络 等 |
| 🌐 **中英双语** | 每页都有英文（`/`）和中文（`/zh/`），带 hreflang + 右上角语言切换 |
| 📦 **插件详情页** | 每插件一页：安装命令、验证状态、Star/Fork/Issue、SEO 元数据 |
| 📊 **生态总览** | 目录页顶部实时展示插件总数、增长曲线、分类分布、热门 Top10 |
| 🎨 **皮肤中心** | `/themes/` 页展示 151 款昼夜皮肤，accent 色实时预览 |
| ⚡ **实时 Star** | 通过 Cloudflare Pages Function 实时拉 GitHub 星数，不是死快照 |

## 🔌 数据从哪来

**主源（每日）：** [dsh.so](https://www.dsh.so/) 的 `search-index.json`，由 `scripts/sync-dshso.py` 拉取并写入目录元数据（也可补新仓）。我们不再对上游清单做一轮自筛；对外页面仍用 dshbase 既有「验证」展示（`test` / 已验证徽章）。

**补充（仅特别火的）：** GitHub topic [`dsh-plugin`](https://github.com/topics/dsh-plugin)，`scripts/sync-topic.py` —— **仅 stars ≥ 100**。低于阈值的 topic 仓库会跳过并打印日志。

**去重：** 只认同一个 GitHub 仓库身份（规范化后的 `owner/repo`：协议、`.git`、尾斜杠、大小写）。**仅同名不算重复。**

> 诚实说明：topic 里仍有蹭标签仓库。topic 路径只碰特别火的；目录增长主要跟 dsh.so + Issue 提交走。

## 🛠️ 技术栈

- **[Astro](https://astro.build)** —— 纯静态站，构建快、SEO 好
- **Cloudflare Pages** —— 托管 + Serverless Functions
- **纯 JSON 数据** —— 目录在 `src/data/plugins.json`，皮肤在 `src/data/skins.json`，无数据库、无后端

## 🤖 自动化

两个 GitHub Actions workflow 每天自动维护：

| 机器人 | 触发 | 干什么 |
|---|---|---|
| 🔄 **同步** `sync-plugins.yml` | 每天 04:17 UTC（另：每周日 05:17 UTC topic 补充） | 主源 dsh.so → `plugins.json`；补充 topic（stars ≥ 100） |
| 🧪 **体检** `compat-check.yml` | 每天 03:23 UTC | 挨个实测 npm 插件，只升级验证状态、绝不误降 |

## 📮 提交插件

开一个 issue，选「提交插件」模板即可，我们会验证 + 收录 + 友好回复。最低门槛：

- 仓库加了 `dsh-plugin` topic
- 有 LICENSE
- 带 bundle 清单（`cordis.patch.yml` / `cordis.yml` / `dsh.bundle.patch`）

已经收录但想拿「已验证」标签？用「提交验证证据」模板开 issue——附上插件在 dsh 里实际运行的截图/日志，我们审核后即标记「已验证」。

## 💻 本地开发

```bash
npm install
npm run dev       # http://localhost:4321
npm run build     # 输出到 dist/
```

`scripts/` 里的脚本（需要 `GITHUB_TOKEN`，部分还要 `DEEPSEEK_API_KEY`）：

```bash
# 验证 + 收录一个插件（仅按 canonical GitHub 仓库去重）
python scripts/ingest-plugin.py https://github.com/owner/repo --category "Developer"

# Hub 目录仅作线索 → 写入 pending（绝不自动标 verified）
python scripts/import-hub-candidates.py
python scripts/import-hub-candidates.py --ingest --limit 20

# 导出轻量 in-DSH catalog（含仅已验证场景包）
python scripts/gen-catalog.py /path/to/dshbase-catalog/src/catalog.json

# 主源：从 dsh.so 同步（可用 --dry-run / --no-add / --max-add N 做冒烟）
python scripts/sync-dshso.py --dry-run
# 补充：topic 仅 stars >= 100
python scripts/sync-topic.py --dry-run
```

DSH 内发现：`dsh plugin add dshbase-catalog` — 见 [docs/dshbase-catalog.md](docs/dshbase-catalog.md)。场景包（仅已验证）：`/packs/`。

## 📄 License

MIT —— 见 [LICENSE](LICENSE)。
