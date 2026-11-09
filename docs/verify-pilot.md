# Plugin verify pilot (GitHub-hosted runner)

This is a pilot, not the badge writer. It runs the same L1–L3 commands as
`scripts/verify-runtime.sh` on `ubuntu-latest` and uploads a report. It does
not edit `src/data/plugins.json` and it does not use `CATALOG_REPO_TOKEN`.

**Verified** on the public audit pages means L1 install + L2 load + L3 headless
on dsh `0.1.0-rc.8`. If L3 is `web-only`, L4 web CDP is required. This pilot
pins that runtime. L4 is skipped: `scripts/verify-webonly.sh` needs
`~/webverify/l3.mjs` and a pinned Puppeteer Chrome that are not in this repo.

## What it runs

| Slug | Install spec | Why it is in the set |
|---|---|---|
| `dsh-plugin-observatory` | `dsh-plugin-observatory@0.1.0` | Already verified by a headless L3 pass on dsh 0.1.0-rc.6. Peers match 0.1.0-rc.8. No account. |
| `dsh-sherlock` | `dsh-sherlock@0.1.1` | Issue #300, listed. Public tools, no plugin key. Declares dsh >=0.2.1-rc.3 and Node >=24.9 <25. |
| `dsh-processing-status` | `github:OStarsO/dsh-processing-status#v1.0.0` | Issue #299, listed. Web client only, no account. |
| `vacum972-dsh-usage-billing` | `@vacum972/dsh-usage-billing@0.1.3` | Issue #297, listed. Balance needs a signed-in DeepSeek account; this run does not sign in. |
| `yumiku-dsh-commandcode-quota` | `@yumiku/dsh-commandcode-quota@1.1.1` | Catalog says verified from metadata only. Live quota needs a Command Code key, which is not set. |

A missing `DEEPSEEK_API_KEY` is recorded as `needs-env` on L3. That is not a
plugin failure and it is not Verified. `web-only` is not Verified.

## Run on Actions

Workflow: `.github/workflows/verify-pilot.yml`.

- A push to `cursor/dsh-verify-pilot-2277` that changes the workflow, `scripts/verify-pilot.py`, or `scripts/dsh-overrides.yaml` starts a run. `workflow_dispatch` is listed in the Actions tab only after this file is on the default branch.
- After merge: Actions → **Plugin verify pilot** → Run workflow. The optional `plugins` input is one `slug|install-spec` per line. Leave it empty for the table above.
- Optional repository secret `DEEPSEEK_API_KEY` turns L3 into a real model call. Do not put the key in the workflow file.

Artifacts: `verify-pilot-report` (`report.json`, `summary.md`, per-plugin logs).

## Run locally

```bash
npm install -g pnpm@10 @deepseek-ai/dsh@0.1.0-rc.8
python3 scripts/verify-pilot.py --self-check
python3 scripts/verify-pilot.py --only dsh-plugin-observatory --out-dir /tmp/pilot-report
```

Node 24.9 or newer matches the sherlock engine. The script still runs L1–L2 on older Node and records the engine error when pnpm refuses the package.

On dsh 0.1.0-rc.8 the headless prompt creates the HMR plugin and then immediately asks for the service, while that fiber is still loading. The script inserts a one-second settle into the installed CLI (`pilot-hmr-settle`) so L3 can reach the model call. Without it, every headless prompt dies with `user patch-layer watching requires the Cordis HMR service`. That edit stays on the runner. It is not a catalog change.
