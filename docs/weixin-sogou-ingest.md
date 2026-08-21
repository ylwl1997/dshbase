# 搜狗微信 → dshbase 博客改写流水线

从 [weixin.sogou.com](https://weixin.sogou.com) 搜索 DeepSeek Harness / DSH 相关公众号文，**改写**为站内 EN+ZH 博客（禁止原文大段搬运）。

## 脚本

```bash
# 仅搜索候选（需 bsk）
python scripts/weixin-sogou-ingest.py --search-only

# 干跑：搜索 + 抓取摘要 + LLM 改写预览，不写 Astro
python scripts/weixin-sogou-ingest.py --dry-run --limit 5

# 发布 2–3 篇（写 Astro + blog-posts.json + 索引 + state）
python scripts/weixin-sogou-ingest.py --publish --limit 3

# 指定搜狗/微信链接
python scripts/weixin-sogou-ingest.py --publish --href "https://weixin.sogou.com/link?..." --limit 1
```

默认关键词：`DeepSeek Harness`、`rc.8`、`DSH 插件`、`多模态`、`命令` 等。可用 `--query` 追加。

## 运行环境（重要）

| 环境 | 建议 |
|------|------|
| **本机 / VPS + bsk** | **推荐**。搜狗与 `mp.weixin.qq.com` 有反爬/验证码，需已登录的真实 Chromium + [browser-skill](https://github.com/) `bsk`。 |
| GitHub Actions | 默认 **dry-run / 不抓文**。CI 无登录 Cookie，搜狗几乎必然空结果或验证码。可用 `workflow_dispatch` 人工触发检查脚本语法；真正发布在 VPS 跑。 |

依赖：

1. `bsk` 在 PATH，扩展已连接（`bsk status` 绿色）
2. `DEEPSEEK_API_KEY` 或 `~/.dsh/.credentials.yaml` 中的 key（改写用）
3. Python 3.11+

若 bsk 超时：先 `bsk session stop --all`，再 `bsk doctor`；不要对搜狗并行开多个会话。
本机曾出现 navigate RPC 卡死（连 `example.com` 也 timeout）——重启 daemon / 升级 `bsk update` 后再跑。

首批改写也可在 bsk 不可用时，用公开发布说明 + 搜狗主题线索手工跑：

```bash
python scripts/weixin-sogou-batch1.py   # 一次性样例；日常请用 weixin-sogou-ingest.py
```

HTTP 回退（`--http-fallback`）仅作应急，搜狗常返回空页，**不能替代 bsk**。

## 去重与质量

- 状态：`src/data/weixin-ingest-state.json`（seen / published URL+标题）
- 与现有博客标题、已覆盖主题（大起底/插件哲学、30.2→96.2、第一天上手等）去重
- 广告/招聘/低相关自动降分或 LLM `skip`
- 新文 slug 一律 `wx-…`，避免与并行 SEO/rc.8 文撞路径

## 版权

- 产出为面向 dshbase 读者的**改写/分析**
- 原文链接仅作「参考/线索」，`rel=nofollow`
- 不把微信正文 verbatim 写入仓库

## GitHub Action

`.github/workflows/weixin-sogou-ingest.yml`：

- `workflow_dispatch` 为主；可选 cron（默认 dry-run）
- 仅当 repository secret `WEIXIN_INGEST_PUBLISH=1` 且 runner 自备 bsk 时才可能 `--publish`（官方 ubuntu runner **不支持** bsk）
- 建议：VPS crontab `0 10 * * 1,4`（周一/周四）跑 `--publish --limit 2`

## 发布后

```bash
python scripts/gen-sitemap.py
git add src/pages/blog/wx-*.astro src/pages/zh/blog/wx-*.astro \
  src/data/blog-posts.json src/data/weixin-ingest-state.json \
  src/pages/blog/index.astro src/pages/zh/blog/index.astro public/sitemap.xml
# 按需 commit / push（勿提交 _tmp_* / secrets）
```

若 `blog-posts.json` 与并行 agent 冲突：保留双方条目后 rebase，勿 force-push main。
