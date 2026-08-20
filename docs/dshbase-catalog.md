# dshbase-catalog — lightweight in-DSH discovery

Official lightweight market entry for DeepSeek Harness (not a full Hub clone).

## Install

```sh
dsh plugin add dshbase-catalog
```

Then ask your agent to search/install plugins from the dshbase directory, or open whatever UI the plugin registers.

## What “Verified” means

On dshbase (and in the catalog JSON this plugin ships), **Verified** means:

1. **L1 Install** — `dsh plugin add` into a clean profile
2. **L2 Load** — profile boots / dump-config succeeds
3. **L3 Runtime** — headless Q&A exits cleanly (`ok`)
4. **L4 Web CDP** — required only when L3 returns `web-only` (GUI plugin). Run `scripts/verify-webonly.sh`, then `python3 scripts/merge-webonly.py <results.tsv>`. Only L4 `ok` upgrades to verified.

Headless `ok` → verified without L4. L3 `web-only` is **not** a pass.

Ops helpers: `bash scripts/verify-full.sh` (L3 then L4), `python3 scripts/list-l4-queue.py` (true awaiting-L4 vs L4-fail vs old backlog).

It is **not** a GitHub `dsh-plugin` topic count, and **not** “manifest looks installable.”

Methodology: https://dshbase.com/audit/

## Data sync

- Source of truth: `ylwl1997/dshbase` → `src/data/plugins.json` (+ `packs.json`)
- Generator: `scripts/gen-catalog.py`
- CI: `.github/workflows/sync-catalog.yml` regenerates `catalog.json` on `plugins.json` / `packs.json` changes and pushes to this repo when `CATALOG_REPO_TOKEN` is set.

## Scene packs

Verified-only packs (every slot L3-verified): https://dshbase.com/packs/

## Submit plugins

https://github.com/ylwl1997/dshbase/issues/new?template=plugin-submission.yml
