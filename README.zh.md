# dshbase 🎛️

> **DeepSeek Harness 的插件宇宙** —— 一个中英双语、实时更新的插件目录。

[dshbase.com](https://dshbase.com) 是 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)（官方开源 Agent 框架，口号是「一切皆插件」）的社区插件目录。我们把散落在 GitHub 各处的 DSH 插件**收编成册**：每个插件都有安装命令、验证状态、实时 Star 数 —— **不用再点进仓库一个个翻了**。

---

## ✨ 这里有什么

| 亮点 | 说明 |
|---|---|
| 🧩 **1100+ 插件** | 覆盖 7 大类：界面增强 / 会话消息 / 工具能力 / 工作流自动化 / 通知集成 / 开发运行时 / 趣味 |
| 🌐 **中英双语** | 每页都有英文（`/`）和中文（`/zh/`），带 hreflang + 右上角语言切换 |
| 📦 **插件详情页** | 每插件一页：安装命令、验证状态、Star/Fork/Issue、SEO 元数据，搜索引擎友好 |
| 📊 **生态总览** | 目录页顶部实时展示：插件总数、增长曲线、分类分布、热门 Top10 |
| 🎨 **皮肤中心** | `/themes/` 页展示 `dsh-themes` 的 151 款昼夜皮肤，accent 色实时预览 |
| ⚡ **实时 Star** | 通过 Cloudflare Pages Function 实时拉 GitHub 星数，不是死快照 |

---

## 🔌 数据从哪来

**官方 [GitHub `dsh-plugin` topic](https://github.com/topics/dsh-plugin)** —— 不是抄任何第三方目录。每天凌晨自动同步一次，刷新 Star、Fork、语言、归档状态。

> 诚实说明：官方 topic 里混着一些「蹭标签」的非插件仓库（比如图床工具、Claude 桌面端）。我们**收录范围是人工/智能筛选后的精选清单**，数据（Star 等）才是从官方 topic 刷新的。

---

## 🛠️ 技术栈

- **[Astro](https://astro.build)** —— 纯静态站，构建快、SEO 好
- **Cloudflare Pages** —— 托管 + Serverless Functions（`functions/`）
- **纯 JSON 数据** —— 目录在 `src/data/plugins.json`，皮肤在 `src/data/skins.json`，无数据库、无后端

---

## 🤖 三个机器人，全自动运转

整个目录靠三个 GitHub Actions workflow 自动维护，**几乎不用人工**：

| 机器人 | 触发时机 | 干什么 |
|---|---|---|
| 🚪 **收录机器人** `ingest-plugin.yml` | 有人开 `[收录]` issue | 验证仓库（存在 / topic / license / bundle 清单）→ **DeepSeek 读 README 智能写双语描述 + 分类 + 判垃圾** → 收录 → 回复 → 关 issue |
| 🔄 **同步机器人** `sync-topic.yml` | 每天 04:17 UTC | 从官方 topic 拉数据，刷新 Star/Fork/语言 |
| 🧪 **体检机器人** `compat-check.yml` | 每天 03:23 UTC | 挨个 `dsh plugin add` 实测 npm 插件，只**升级**验证状态、绝不误降 |

**收录流程是「先收后补」的暖男风格**：就算缺 topic / license / bundle 清单，也会先收录，然后在回复里温柔提醒「建议补充 X，补充后我会更新」——**不打击热情，只标注不拒绝**。唯一的硬红线是「根本不是插件」（蹭 topic 的仓库）。

---

## 📮 提交你的插件

开一个 issue，选「提交插件 / Submit your plugin」模板即可。机器人会自动处理，几秒内回复。**最低门槛**（缺了也会先收录，只是会提醒补）：

- 仓库加了 `dsh-plugin` topic
- 有 LICENSE
- 带 bundle 清单（`cordis.patch.yml` / `cordis.yml` / `dsh.bundle.patch`）

---

## 💻 本地开发

```bash
npm install
npm run dev       # http://localhost:4321
npm run build     # 输出到 dist/
```

`scripts/` 里的脚本（需要 `GITHUB_TOKEN`，部分还要 `DEEPSEEK_API_KEY`）：

```bash
# 验证 + 收录一个插件（全局去重，绝不重复）
python scripts/ingest-plugin.py https://github.com/owner/repo --category "Tools & Capabilities"

# 从官方 topic 刷新 Star
python scripts/sync-topic.py

# 解析 issue 正文并跑完整收录流程（读 ISSUE_NUMBER / ISSUE_BODY）
python scripts/process-issue.py
```

---

## 📄 License

MIT —— 见 [LICENSE](LICENSE)。
