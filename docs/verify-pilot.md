# Plugin verify pilot (GitHub-hosted runner)

This is a pilot, not the badge writer. It runs the same L1–L3 commands as
`scripts/verify-runtime.sh` on `ubuntu-latest` and uploads a report. It does
not edit `src/data/plugins.json` and it does not use `CATALOG_REPO_TOKEN`.

**Verified** on the public audit pages means L1 install + L2 load + L3 headless
on official `@deepseek-ai/dsh@latest`. If L3 is `web-only`, L4 web CDP is required
before a badge. This pilot installs that dist-tag, records the resolved
`dsh --version`, and does not write badges. It does not freeze a semver.
Earlier passes were recorded on dsh `0.1.0-rc.8`.

L4 for GitHub-hosted runners is `scripts/l4-cdp.mjs` (Playwright). It does not
use `~/webverify/l3.mjs` or a pinned Puppeteer Chrome path. `ubuntu-latest`
already has Google Chrome; Playwright's Chromium is the fallback. Headless
mode does not need xvfb. The L1–L3 workflow does not run L4. The browser
workflow is `.github/workflows/verify-pilot-l4.yml`.

## What it runs

| Slug | Install spec | Why it is in the set |
|---|---|---|
| `dsh-plugin-observatory` | `dsh-plugin-observatory@0.1.0` | Historical headless L3 pass on dsh 0.1.0-rc.6. Peers are `>=0.1.0-rc.6 <0.2.0`, which may not include current official latest. No account. |
| `dsh-sherlock` | `dsh-sherlock@0.1.1` | Issue #300, listed. Public tools, no plugin key. Declares dsh >=0.2.1-rc.3 and Node >=24.9 <25. |
| `dsh-processing-status` | `github:OStarsO/dsh-processing-status#v1.0.0` | Issue #299, listed. Web client only, no account. |
| `vacum972-dsh-usage-billing` | `@vacum972/dsh-usage-billing@0.1.3` | Issue #297, listed. Balance needs a signed-in DeepSeek account; this run does not sign in. |
| `yumiku-dsh-commandcode-quota` | `@yumiku/dsh-commandcode-quota@1.1.1` | Catalog says verified from metadata only. Live quota needs a Command Code key, which is not set. |

A missing `DEEPSEEK_API_KEY` is recorded as `needs-env` on L3. That is not a
plugin failure and it is not Verified. `web-only` is not Verified.

## Run on Actions

Workflow: `.github/workflows/verify-pilot.yml`.

- A push to `cursor/dsh-verify-pilot-2277` that changes the workflow or `scripts/verify-pilot.py` starts a run. `workflow_dispatch` is listed in the Actions tab only after this file is on the default branch.
- After merge: Actions → **Plugin verify pilot** → Run workflow. The optional `plugins` input is one `slug|install-spec` per line. Leave it empty for the table above.
- Optional repository secret `DEEPSEEK_API_KEY` turns L3 into a real model call. Do not put the key in the workflow file.

Artifacts: `verify-pilot-report` (`report.json`, `summary.md`, per-plugin logs).

## L4 browser job

Workflow: `.github/workflows/verify-pilot-l4.yml` (**Plugin verify pilot L4**).

Default set:

| Slug | What the browser looks for |
|---|---|
| `yumiku-dsh-commandcode-quota` | Known web-only (`waiting for service: webServer` on Actions run 42562689033). Pass means the shell mounted, `.dcq-float` or `#dcq-style` is in the page, and `GET /dsh-commandcode/api/key` returns JSON. No Command Code key is set. |
| `dsh-processing-status` | Optional. The status line is hidden until a task runs. The idle signal is `style[data-plugin="dsh-processing-status"]`. |
| `vacum972-dsh-usage-billing` | Optional. Headless L3 already passed, so L4 is not required. The probe is the composer pill `[data-composer-stat="billing"]`. |
| `dsh-kimino-theme` | Idle skin, no account. `github:niiang/dsh-kimino-theme#v68.4.2`. No `engines.dsh` field. Probe is `html[data-kimino-theme="on"]`, `#kimino-theme`, `style[data-plugin="dsh-kimino-theme"]`, or `[data-kimino-backdrop]`. |

L3 is not repeated. `DEEPSEEK_API_KEY` is not read. `l4-pass` in the artifact is not a catalog Verified badge, and a metadata `test=verified` row is not confirmed by this job.

- `workflow_dispatch` is listed after this file is on the default branch. A push to `cursor/dsh-verify-l4-cdp-7249` that changes the workflow or the L4 scripts starts one run before that.
- Optional `plugins` input: one `slug|install-spec` per line. Known slugs keep the probes above. Leave it empty for the table.
- Artifacts: `verify-pilot-l4-report` (`report.json`, `summary.md`, logs, screenshots).

Making L4 the default for web-only intakes is a follow-up, not this job. Headless L3 stays the check for terminal plugins. Run L4 only after L3 returns `web-only`, keep it on `workflow_dispatch` until more than the quota plugin is green, and keep `merge-webonly.py` as the only badge writer.

## Run locally

```bash
npm install -g pnpm@10 @deepseek-ai/dsh@latest
dsh --version
python3 scripts/verify-pilot.py --self-check
python3 scripts/verify-pilot.py --only dsh-plugin-observatory --out-dir /tmp/pilot-report

# L4 needs Playwright plus Chrome or Playwright's Chromium. It drops DEEPSEEK_API_KEY.
npm install --prefix /tmp/l4-browser playwright@1.65.0
L4_BROWSER_DIR=/tmp/l4-browser python3 scripts/verify-pilot.py --l4 --only yumiku-dsh-commandcode-quota --out-dir /tmp/pilot-l4
```

Node 24.9 or newer matches the sherlock engine. The script still runs L1–L2 on older Node and records the engine error when pnpm refuses the package.

`scripts/dsh-overrides.yaml` used to pin every official `@deepseek-ai/dsh-*` package to `0.1.0-rc.8`. That file is gone. Do not install those packages at their own `latest` dist-tag either. Checked while making this change: `@deepseek-ai/dsh-base`, `@deepseek-ai/dsh-headless`, `@deepseek-ai/dsh-web-app`, and `@deepseek-ai/dsh-client-ui-theme` all had `latest` at `0.0.1-rc.1`, while the installed `@deepseek-ai/dsh@latest` CLI depended on the copies published under each package's `next` tag. `dsh plugin add @deepseek-ai/dsh-base@latest` was rejected as incompatible. `scripts/dsh_official_spec.py` reads the exact versions from that installed CLI. Transitive packages stay on the versions those packages declare. There is no overrides file.

On dsh 0.1.0-rc.8 the headless prompt created the HMR plugin and then immediately asked for the service, while that fiber was still loading. The script still inserts a one-second settle into the installed CLI (`pilot-hmr-settle`) when that old `profile-boot` pattern is present, and it skips user-patch watching when `registerConfig` is missing. Official latest moved that watcher out of `profile-boot-*.js`, so the edit does not apply and the CLI is left unchanged. The edit stays on the runner. It is not a catalog change.
