# dshbase

[**dshbase.com**](https://dshbase.com) — the **DeepSeek Harness (DSH) plugin directory**. A curated, bilingual (English / 中文) catalog of the DSH plugin ecosystem: every plugin with its install command, verification status, and live GitHub stars — no clicking through to check.

> DeepSeek Harness ([deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness)) is DeepSeek's open-source agent framework ("everything is a plugin"). This site is the community directory for its plugin ecosystem.

## What's here

- **1,100+ plugins** across 7 categories (UI, sessions, tools, workflow, integrations, runtime, fun)
- **Bilingual** — every page in English (`/`) and 中文 (`/zh/`), with hreflang + automatic language switcher
- **Plugin detail pages** — each with install command, verification status, stars/forks/issues, and SEO metadata
- **Ecosystem overview** — growth curve, category distribution, and live stats on the directory page
- **Theme center** (`/themes/`) — 151 day/night skin previews from `dsh-themes`
- **Live stars** — real-time GitHub stars/forks via a Cloudflare Pages Function

## Data source

The catalog is sourced from the official **[GitHub `dsh-plugin` topic](https://github.com/topics/dsh-plugin)** — not from any third-party snapshot. A daily sync refreshes stars, forks, language, and archive status.

## Tech stack

- **[Astro](https://astro.build)** (static site, `src/pages/**/*.astro`)
- **Cloudflare Pages** (hosting + Functions in `functions/`)
- Data lives in `src/data/plugins.json` (the catalog) and `src/data/skins.json` (themes)

## Automation

Three GitHub Actions workflows keep the directory current:

| Workflow | Trigger | What it does |
|---|---|---|
| [`ingest-plugin.yml`](.github/workflows/ingest-plugin.yml) | new issue titled `[收录] …` | verifies the repo (exists · `dsh-plugin` topic · license · bundle manifest), **AI-enriches** the description/category via DeepSeek, adds it to the catalog, replies, and closes the issue |
| [`sync-topic.yml`](.github/workflows/sync-topic.yml) | daily 04:17 UTC | pulls the `dsh-plugin` topic and refreshes stars/forks/language |
| [`compat-check.yml`](.github/workflows/compat-check.yml) | daily 03:23 UTC | installs each npm plugin in a fresh profile and upgrades verified status (never downgrades) |

The ingestion pipeline is **AI-assisted**: the hard checks (topic, license, bundle) stay deterministic, while [DeepSeek](https://www.deepseek.com) reads each plugin's README to write the bilingual description, pick the right category, and flag repos that merely tag `dsh-plugin` for visibility.

## Submit a plugin

Open an issue using the **「提交插件 / Submit your plugin」** template. The bot verifies and ingests it automatically. Minimum requirements:

- repo is tagged `dsh-plugin`
- has a LICENSE
- ships a bundle manifest (`cordis.patch.yml` / `cordis.yml` / `dsh.bundle.patch`)

## Local development

```bash
npm install
npm run dev       # http://localhost:4321
npm run build     # outputs to dist/
```

Scripts in `scripts/` (all require `GITHUB_TOKEN`, some also `DEEPSEEK_API_KEY`):

```bash
# verify + ingest one plugin (global dedup by name/repo)
python scripts/ingest-plugin.py https://github.com/owner/repo --category "Tools & Capabilities"

# refresh stars from the GitHub topic
python scripts/sync-topic.py

# parse an issue body and run the full ingest flow
python scripts/process-issue.py   # reads ISSUE_NUMBER / ISSUE_BODY / GITHUB_TOKEN
```

## License

MIT — see [LICENSE](LICENSE).
