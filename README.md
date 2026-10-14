<p align="center">
  <a href="README.md"><b>English</b></a> · <a href="README.zh.md"><b>简体中文</b></a>
</p>

# dshbase 🎛️

> **The plugin universe for DeepSeek Harness**

[dshbase.com](https://dshbase.com) is the bilingual (English / 中文) community directory for [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) — DeepSeek's open-source agent framework ("everything is a plugin"). We've collected DSH plugins scattered across GitHub into one organized catalog: every plugin ships with its install command, verification status, and live star count — **no more clicking into each repo to check**.

## ✨ What's inside

| Highlight | What it is |
|---|---|
| 🧩 **1,700+ plugins** | across 15 categories — developer tools, UI & skins, knowledge, automation, networking, and more |
| 🌐 **Bilingual** | every page in English (`/`) and 中文 (`/zh/`), with hreflang + auto language switcher |
| 📦 **Plugin detail pages** | one page per plugin: install command, status, stars/forks/issues, SEO metadata |
| 📊 **Ecosystem overview** | live stats on the directory page: total, growth curve, category distribution, top 10 |
| 🎨 **Theme center** | `/themes/` showcases 151 day/night skins with accent-color previews |
| ⚡ **Live stars** | real-time GitHub stars via a Cloudflare Pages Function — not a stale snapshot |

## 🔌 Data source

**Primary (daily):** [dsh.so](https://www.dsh.so/) `search-index.json` via `scripts/sync-dshso.py` — refreshes catalog metadata and can add new repos. We trust the upstream feed (no separate screening pass); public pages still use dshbase’s existing verify UX (`test` / Verified badge).

**Supplement (hot only):** GitHub topic [`dsh-plugin`](https://github.com/topics/dsh-plugin) via `scripts/sync-topic.py` — **stars ≥ 100** only. Lower-star topic repos are skipped (logged).

**Dedup:** same GitHub repository identity only (canonical `owner/repo`, normalizing scheme, `.git`, trailing slash, case). Matching display names alone are not duplicates.

> Honest note: the topic still contains tag-squatting repos. The topic path only touches especially popular ones; listing growth mainly follows dsh.so + issue submissions.

## 🛠️ Tech stack

- **[Astro](https://astro.build)** — static site, fast builds, SEO-friendly
- **Cloudflare Pages** — hosting + Serverless Functions
- **Plain JSON data** — catalog in `src/data/plugins.json`, skins in `src/data/skins.json`; no database, no backend

## 🤖 Automation

Two GitHub Actions workflows keep the directory fresh every day:

| Bot | When | What it does |
|---|---|---|
| 🔄 **Sync** `sync-plugins.yml` | daily 04:17 UTC (+ weekly topic Sun 05:17 UTC) | primary: dsh.so → `plugins.json`; supplement: topic repos with stars ≥ 100 |
| 🧪 **Health-check** `compat-check.yml` | daily 03:23 UTC | installs each npm plugin and upgrades verified status (never downgrades) |

## 📮 Submit a plugin

Open an issue with the "Submit your plugin" template — we verify, ingest, and reply. Minimum requirements:

- repo tagged `dsh-plugin`
- has a LICENSE
- ships a bundle manifest (`cordis.patch.yml` / `cordis.yml` / `dsh.bundle.patch`)

Already listed but want the **Verified** badge? Open an issue with the **"Submit verification evidence"** template — attach screenshots or logs of your plugin actually running in dsh, and we'll review and mark it verified.

## 💻 Local development

```bash
npm install
npm run dev       # http://localhost:4321
npm run build     # outputs to dist/
```

Scripts in `scripts/` (require `GITHUB_TOKEN`, some also `DEEPSEEK_API_KEY`):

```bash
# verify + ingest one plugin (dedup by canonical GitHub repo only)
python scripts/ingest-plugin.py https://github.com/owner/repo --category "Developer"

# Hub catalog as *clues only* → ingest pending (never auto-verified)
python scripts/import-hub-candidates.py              # dry-run top gaps
python scripts/import-hub-candidates.py --ingest --limit 20

# export lightweight in-DSH catalog (+ verified-only packs)
python scripts/gen-catalog.py /path/to/dshbase-catalog/src/catalog.json

# primary daily sync from dsh.so (use --dry-run / --no-add / --max-add N for smoke)
python scripts/sync-dshso.py --dry-run
# supplemental topic sync — hot repos only (stars >= 100)
python scripts/sync-topic.py --dry-run
```

In-DSH discovery: install `dsh plugin add dshbase-catalog` — see [docs/dshbase-catalog.md](docs/dshbase-catalog.md). Scene packs (verified-only): `/packs/`.

## 📄 License

MIT — see [LICENSE](LICENSE).
