# dshbase 🎛️

> **DeepSeek Harness 的插件宇宙** · The plugin universe for DeepSeek Harness

[dshbase.com](https://dshbase.com) 是 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)（官方开源 Agent 框架，口号「一切皆插件」）的社区插件目录，**中英双语**、实时更新。我们把散落在 GitHub 各处的 DSH 插件**收编成册**——每个插件都有安装命令、验证状态、实时 Star 数，**不用再点进仓库一个个翻了**。

[dshbase.com](https://dshbase.com) is the bilingual (English / 中文) community directory for [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness), DeepSeek's open-source agent framework. Every plugin comes with its install command, verification status, and live star count — no more clicking into each repo.

---

## ✨ 这里有什么 / What's inside

| 亮点 · Highlight | 说明 · What it is |
|---|---|
| 🧩 **1100+ 插件** | 覆盖 7 大类：界面增强 / 会话消息 / 工具能力 / 工作流自动化 / 通知集成 / 开发运行时 / 趣味 |
| 🌐 **中英双语** | 每页都有英文（`/`）和中文（`/zh/`），带 hreflang + 右上角语言切换 |
| 📦 **插件详情页** | 每插件一页：安装命令、验证状态、Star/Fork/Issue、SEO 元数据 |
| 📊 **生态总览** | 目录页顶部实时展示插件总数、增长曲线、分类分布、热门 Top10 |
| 🎨 **皮肤中心** | `/themes/` 页展示 151 款昼夜皮肤，accent 色实时预览 |
| ⚡ **实时 Star** | 通过 Cloudflare Pages Function 实时拉 GitHub 星数，不是死快照 |

## 🔌 数据从哪来 / Data source

官方 [GitHub `dsh-plugin` topic](https://github.com/topics/dsh-plugin) —— 不是抄任何第三方目录。每天自动同步一次，刷新 Star、Fork、语言、归档状态。

Sourced from the official [GitHub `dsh-plugin` topic](https://github.com/topics/dsh-plugin), refreshed daily.

> 诚实说明：官方 topic 里混着一些「蹭标签」的非插件仓库。我们**收录范围是筛选后的精选清单**，数据（Star 等）才从官方 topic 刷新。

## 🛠️ 技术栈 / Tech stack

- **[Astro](https://astro.build)** —— 纯静态站，构建快、SEO 好
- **Cloudflare Pages** —— 托管 + Serverless Functions
- **纯 JSON 数据** —— 目录在 `src/data/plugins.json`，皮肤在 `src/data/skins.json`，无数据库、无后端

## 🤖 自动化 / Automation

两个 GitHub Actions workflow 每天自动维护：

| 机器人 · Bot | 触发 · When | 干什么 · What |
|---|---|---|
| 🔄 **同步** `sync-topic.yml` | 每天 04:17 UTC | 从官方 topic 刷新 Star/Fork/语言 |
| 🧪 **体检** `compat-check.yml` | 每天 03:23 UTC | 挨个实测 npm 插件，只升级验证状态、绝不误降 |

## 📮 提交插件 / Submit a plugin

开一个 issue，选「提交插件」模板即可，我们会**验证 + 收录 + 友好回复**。最低门槛：

Open an issue with the "Submit your plugin" template. We verify, ingest, and reply warmly. Minimum requirements:

- 仓库加了 `dsh-plugin` topic · repo tagged `dsh-plugin`
- 有 LICENSE · has a LICENSE
- 带 bundle 清单 · ships a bundle manifest（`cordis.patch.yml` / `cordis.yml` / `dsh.bundle.patch`）

## 💻 本地开发 / Local development

```bash
npm install
npm run dev       # http://localhost:4321
npm run build     # 输出到 dist/
```

`scripts/` 里的脚本（需要 `GITHUB_TOKEN`，部分还要 `DEEPSEEK_API_KEY`）：

```bash
# 验证 + 收录一个插件（全局去重）
python scripts/ingest-plugin.py https://github.com/owner/repo --category "Tools & Capabilities"

# 从官方 topic 刷新 Star
python scripts/sync-topic.py
```

## 📄 License

MIT —— 见 [LICENSE](LICENSE)。
