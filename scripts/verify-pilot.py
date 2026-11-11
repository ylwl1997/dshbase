#!/usr/bin/env python3
"""Pilot plugin check for GitHub-hosted runners.

Reuses the install / dump-config / headless commands from
scripts/verify-runtime.sh. The CLI is official @deepseek-ai/dsh@latest.
Profile adds use the dsh-base and dsh-headless or dsh-web-app versions that
installed CLI declares (scripts/dsh_official_spec.py). Those packages' own
`latest` dist-tags can lag the CLI, so they are not installed as @latest.
Transitive @deepseek-ai/* versions stay on whatever those packages declare.
There is no pnpm overrides file freezing official packages.
Writes a JSON report and a Markdown summary. Does not edit plugins.json,
does not call merge-verify.py or merge-webonly.py, and does not talk to the
catalog mirror.

Git-hosted prepare, this verify pipeline only: when pnpm refuses a git
dependency's prepare script (ERR_PNPM_GIT_DEP_PREPARE_NOT_ALLOWED, the
onlyBuiltDependencies / allowBuilds gate), the exact key pnpm prints is
written under that profile's allowBuilds and the same `dsh plugin add` is
retried. The key is the resolved dep path, not the package name. This does
not relax engines.dsh checks and does not pass
`dsh plugin allow-version --accept-risk`. A retry that still ends on that
pnpm error is failureClass `prepare-blocked`, which is not an engine
mismatch and not a generic install-fail.

Stages (same meanings as https://dshbase.com/audit/):
  L1  dsh plugin add into a clean profile, with dsh-base plus either
      dsh-headless (default) or dsh-web-app (--l4), at the versions the
      installed CLI depends on. The report records `dsh --version`.
  L2  dsh --dump-config, and the plugin package is in dsh.profile.bundles.
  L3  headless prompt "Reply with exactly: OK".
      web-only (GUI service missing) is not a pass.
      A missing DEEPSEEK_API_KEY is needs-env, not a plugin failure.
      --l4 skips this call. The browser job does not read the API key.
  L4  --l4 only. Boot `dsh --profile <name> --host 127.0.0.1 --port <port>
      --no-open` and run scripts/l4-cdp.mjs (Playwright, system Chrome or
      bundled Chromium). wait_http and Playwright both open the exact
      `dsh web: http://…/?token=…` URL printed in that process log. The
      tokenless root is not requested, and a token is never invented.
      With no dedicated selector, text, or route probe, a pass is the
      generic shell-mounted criteria: that token URL was used, the shell
      mounted, boot did not fail, and the server stayed alive. A missing
      probe is not a failure. A configured probe still has to match.
      No ~/webverify path. A pass is browser evidence, not a catalog
      Verified badge.

Usage:
  python3 scripts/verify-pilot.py --self-check
  python3 scripts/verify-pilot.py --out-dir pilot-report
  python3 scripts/verify-pilot.py --l4 --out-dir pilot-report
  python3 scripts/verify-pilot.py --only dsh-dir-tree --out-dir /tmp/pilot-report
  PILOT_PLUGINS=$'slug|spec\\n' python3 scripts/verify-pilot.py --out-dir pilot-report
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGINS_JSON = ROOT / "src" / "data" / "plugins.json"

# Dist-tag of the CLI. Profile package specs are filled from the installed
# CLI before any plugin add (see bind_official_packages).
DSH_DIST_TAG = "latest"
BASE_PKG = ""
HEADLESS_PKG = ""
WEB_PKG = ""
OFFICIAL_DEPS = {
    "@deepseek-ai/dsh-base",
    "@deepseek-ai/dsh-headless",
    "@deepseek-ai/dsh-web-app",
}
L4_SCRIPT = Path(__file__).resolve().parent / "l4-cdp.mjs"

L1_TIMEOUT = int(os.environ.get("PILOT_L1_TIMEOUT", "240"))
L2_TIMEOUT = int(os.environ.get("PILOT_L2_TIMEOUT", "180"))
L3_TIMEOUT = int(os.environ.get("PILOT_L3_TIMEOUT", "180"))
WEB_BOOT_TIMEOUT = int(os.environ.get("PILOT_WEB_BOOT_TIMEOUT", "90"))
L4_TIMEOUT = int(os.environ.get("PILOT_L4_TIMEOUT", "60"))
L3_PROMPT = "Reply with exactly: OK"

L4_REASON = (
    "Skipped in this L1–L3 job. Web CDP is scripts/l4-cdp.mjs, run with "
    "--l4 (workflow .github/workflows/verify-pilot-l4.yml). It uses Playwright "
    "and the runner's Chrome or Playwright's Chromium. This job does not invent "
    "a CDP result."
)
L3_SKIPPED_FOR_L4 = (
    "Skipped. This is the web CDP job, so it does not send a headless prompt "
    "and does not read DEEPSEEK_API_KEY. Actions run 42562689033 already "
    "classified @yumiku/dsh-commandcode-quota as web-only (waiting for service: "
    "webServer) before any model answer."
)

# Registry packages whose lifecycle scripts this verify install already trusts.
# Git-hosted prepare keys are not seeded: pnpm requires the resolved dep path
# (package name plus the commit tarball URL), which exists only after the first
# attempt. parse_allow_build_keys copies that exact key. Scope is this
# repository's verify install, not an engines.dsh exemption.
ALLOW_BUILD_SEED = [
    "@deepseek-ai/dsh-subprocess-local",
    "@google/genai",
    "koffi",
    "node-pty",
    "protobufjs",
]

DEFAULT_PLUGINS = [
    {
        "slug": "dsh-plugin-observatory",
        "installSpec": "dsh-plugin-observatory@0.1.0",
        "catalogTest": "verified",
        "role": (
            "Historical headless L3 pass on dsh 0.1.0-rc.6 (install + load + Q&A). "
            "Peers @deepseek-ai/dsh-tools and dsh-invariants at >=0.1.0-rc.6 <0.2.0, "
            "which may not include current official latest. No external account."
        ),
    },
    {
        "slug": "dsh-sherlock",
        "installSpec": "dsh-sherlock@0.1.1",
        "catalogTest": "listed",
        "role": (
            "Issue #300 intake. Public username tools, no plugin API key. "
            "Declares dsh >=0.2.1-rc.3 <0.4.0 and node >=24.9.0 <25."
        ),
    },
    {
        "slug": "dsh-processing-status",
        "installSpec": "github:OStarsO/dsh-processing-status#v1.0.0",
        "catalogTest": "listed",
        "role": (
            "Issue #299 intake. Web client only (composer line + settings switch). "
            "No network and no account. Pin matches the catalog note."
        ),
    },
    {
        "slug": "vacum972-dsh-usage-billing",
        "installSpec": "@vacum972/dsh-usage-billing@0.1.3",
        "catalogTest": "listed",
        "role": (
            "Issue #297 intake. Web usage capsule. Remaining balance needs a "
            "signed-in DeepSeek account; this pilot does not sign in. "
            "Declares dsh >=0.2.1-rc.5 <0.3.0-0."
        ),
    },
    {
        "slug": "yumiku-dsh-commandcode-quota",
        "installSpec": "@yumiku/dsh-commandcode-quota@1.1.1",
        "catalogTest": "verified",
        "role": (
            "Catalog test=verified from metadata only (issues #292 and #298); "
            "dshbase did not run L1–L4. Live quota needs a Command Code API key, "
            "which this pilot does not set. Declares dsh >=0.2.0 <0.3.0."
        ),
    },
]

# Browser probes. selectorsAny is OR. A route probe asks the page to fetch a
# same-origin path and requires JSON, which is how a host row proves it left
# "waiting for service: webServer". Live account data is not required.
# A slug with no entry here has no dedicated probe. l4_ready then uses the
# generic shell-mounted criteria. Do not add a probe solely to avoid that path.
L4_PLUGINS = [
    {
        "slug": "yumiku-dsh-commandcode-quota",
        "installSpec": "@yumiku/dsh-commandcode-quota@1.1.1",
        "catalogTest": "verified",
        "role": (
            "Known web-only from Actions run 42562689033: headless L3 stopped at "
            "pending (waiting for service: webServer) before a model answer. "
            "Web client is a Settings tab plus a floating capsule (.dcq-float). "
            "Host routes include GET /dsh-commandcode/api/key, which returns JSON "
            "and never the key. This run does not set a Command Code key. "
            "Catalog test=verified is metadata-only and is not confirmed here."
        ),
        "l4": {
            "dismiss": ["Continue", "继续"],
            "openText": ["Configure later", "稍后配置", "Settings", "设置"],
            "selectorsAny": [".dcq-float", "#dcq-style"],
            "textAny": ["Command Code"],
            "forbid": ["#dcq-boot-error"],
            "route": "/dsh-commandcode/api/key",
            "routeExpect": "json",
            "note": "First-run notice is dismissed. Capsule, style, or the Command Code label counts. The key route answers JSON without a Command Code key.",
        },
    },
    {
        "slug": "dsh-processing-status",
        "installSpec": "github:OStarsO/dsh-processing-status#v1.0.0",
        "catalogTest": "listed",
        "role": (
            "Optional. Web client only (composer status line + settings switch). "
            "Headless L3 on run 42562689033 failed inside watchUserPatches "
            "(hmr.registerConfig), not with waiting-for-webServer. The status "
            "line renders only while a task is running, so the idle-page signal "
            "is the style tag the client inserts on apply."
        ),
        "l4": {
            "selectorsAny": ['style[data-plugin="dsh-processing-status"]'],
            "forbid": [],
            "note": "Status line stays unmounted until a task is running. Style tag means the client applied.",
        },
    },
    {
        "slug": "vacum972-dsh-usage-billing",
        "installSpec": "@vacum972/dsh-usage-billing@0.1.3",
        "catalogTest": "listed",
        "role": (
            "Optional. Headless L3 passed on run 42562689033, so L4 is not "
            "required for the audit rule. The package also ships a web composer "
            "pill (data-composer-stat=billing). Remaining balance needs a "
            "signed-in DeepSeek account; this run does not sign in."
        ),
        "l4": {
            "selectorsAny": ['[data-composer-stat="billing"]', ".ub-pill"],
            "forbid": [],
            "note": "Pill is the composer dock. No account session is started.",
        },
    },
    {
        "slug": "dsh-kimino-theme",
        "installSpec": "github:niiang/dsh-kimino-theme#v68.4.2",
        "catalogTest": "verified",
        "role": (
            "Idle web skin. package.json has no engines.dsh field. The client "
            "injects the theme service and does not call hmr.registerConfig. "
            "On apply, bundle/client.js at v68.4.2 sets html[data-kimino-theme=on], "
            "appends style#kimino-theme (data-plugin=dsh-kimino-theme), and mounts "
            "[data-kimino-backdrop] while live wallpaper is on (the default). "
            "No account. An earlier L4 pass was recorded on dsh 0.1.0-rc.8, where "
            "ctx.theme.overrideTokens existed on @deepseek-ai/dsh-client-ui-theme. "
            "dsh-caption-balance declares dsh >=0.2.2-rc.1; dsh-balance-ball "
            "declares dsh >=0.2.0 and reads an OAuth balance. Neither is this run."
        ),
        "l4": {
            "selectorsAny": [
                'html[data-kimino-theme="on"]',
                "#kimino-theme",
                'style[data-plugin="dsh-kimino-theme"]',
                "[data-kimino-backdrop]",
            ],
            "forbid": [],
            "note": "Selectors are from bundle/client.js at tag v68.4.2. No sign-in. The backdrop div is appended when live wallpaper is on.",
        },
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def redact(text: str, secrets: list[str]) -> str:
    out = text or ""
    for secret in secrets:
        if secret:
            out = out.replace(secret, "***")
    out = re.sub(r"\bsk-[A-Za-z0-9]{8,}\b", "sk-***", out)
    out = re.sub(
        r"(DEEPSEEK_API_KEY\s*[:=]\s*)\S+",
        r"\1***",
        out,
    )
    return out


def snippet(text: str, limit: int = 500) -> str:
    lines = [ln.rstrip() for ln in (text or "").splitlines() if ln.strip()]
    tail = "\n".join(lines[-12:])
    if len(tail) > limit:
        tail = tail[-limit:]
    return tail


def stage(status: str, duration_ms: int = 0, error: str = "", **extra) -> dict:
    row = {"status": status, "durationMs": duration_ms, "error": error}
    row.update(extra)
    return row


def parse_plugin_lines(text: str) -> list[dict]:
    rows = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "\t" in line:
            parts = [p.strip() for p in line.split("\t")]
        else:
            parts = [p.strip() for p in line.split("|")]
        slug = parts[0]
        spec = parts[1] if len(parts) > 1 else ""
        role = parts[2] if len(parts) > 2 else ""
        if not slug:
            continue
        rows.append({"slug": slug, "installSpec": spec, "catalogTest": "", "role": role})
    return rows


def lookup_catalog(slug: str) -> dict | None:
    if not PLUGINS_JSON.is_file():
        return None
    data = json.loads(PLUGINS_JSON.read_text(encoding="utf-8"))
    for items in data.values():
        if not isinstance(items, list):
            continue
        for plugin in items:
            if plugin.get("slug") == slug or plugin.get("name") == slug:
                spec = ""
                if plugin.get("npm") and plugin.get("pkg"):
                    ver = str(plugin.get("ver") or "").strip()
                    spec = f"{plugin['pkg']}@{ver}" if ver else plugin["pkg"]
                else:
                    match = re.search(r"github\.com/([^/\s]+/[^/\s#]+)", plugin.get("url") or "", re.I)
                    if match:
                        spec = "github:" + match.group(1).rstrip("/")
                return {
                    "slug": plugin.get("slug") or slug,
                    "installSpec": spec,
                    "catalogTest": plugin.get("test") or "",
                    "role": "Resolved from src/data/plugins.json for this dispatch.",
                }
    return None


def resolve_plugins(explicit: str, only: list[str] | None) -> list[dict]:
    if explicit.strip():
        chosen = parse_plugin_lines(explicit)
    else:
        chosen = [dict(row) for row in DEFAULT_PLUGINS]
    if only:
        wanted = set(only)
        chosen = [row for row in chosen if row["slug"] in wanted]
        missing = wanted - {row["slug"] for row in chosen}
        for slug in sorted(missing):
            found = lookup_catalog(slug)
            if found:
                chosen.append(found)
            else:
                chosen.append({
                    "slug": slug,
                    "installSpec": "",
                    "catalogTest": "",
                    "role": "Requested by --only but not in the pilot set or catalog.",
                })
    resolved = []
    for row in chosen:
        if not row.get("installSpec"):
            found = lookup_catalog(row["slug"])
            if found and found.get("installSpec"):
                row["installSpec"] = found["installSpec"]
                row["catalogTest"] = row.get("catalogTest") or found.get("catalogTest") or ""
                if not row.get("role"):
                    row["role"] = found.get("role") or ""
        resolved.append(row)
    return resolved


def bind_official_packages() -> None:
    """Set BASE/HEADLESS/WEB from the installed @deepseek-ai/dsh@latest CLI."""
    global BASE_PKG, HEADLESS_PKG, WEB_PKG
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from dsh_official_spec import official_spec

    manifest_specs = {
        "base": official_spec("@deepseek-ai/dsh-base"),
        "headless": official_spec("@deepseek-ai/dsh-headless"),
        "web": official_spec("@deepseek-ai/dsh-web-app"),
    }
    BASE_PKG = manifest_specs["base"]
    HEADLESS_PKG = manifest_specs["headless"]
    WEB_PKG = manifest_specs["web"]


def profile_name(slug: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]", "", slug)[:40] or "plugin"
    return f"p_{safe}"


def workspace_text(extra_keys: list[str] | None = None) -> str:
    keys = list(ALLOW_BUILD_SEED)
    for key in extra_keys or []:
        if key and key not in keys:
            keys.append(key)
    lines = [
        "packages:",
        "  - .",
        "",
        "nodeLinker: hoisted",
        "autoInstallPeers: false",
        "allowBuilds:",
    ]
    for key in keys:
        lines.append(f"  {json.dumps(key, ensure_ascii=False)}: true")
    # No pnpm overrides. Official @deepseek-ai/* versions come from the
    # packages @latest declares, not from a frozen list in this repo.
    return "\n".join(lines) + "\n"


def _unquote_yaml(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        quote = text[0]
        text = text[1:-1]
        if quote == '"':
            text = text.replace('\\"', '"').replace("\\\\", "\\")
    return text


def _looks_like_version(value: str) -> bool:
    return bool(value) and value[0].isdigit() and "://" not in value


def package_name_only(spec: str) -> str:
    """Drop a trailing semver from pnpm's printed `name@version` phrase."""
    if spec.startswith("@"):
        name, sep, version = spec[1:].rpartition("@")
        if sep and name and _looks_like_version(version):
            return "@" + name
        return spec
    name, sep, version = spec.rpartition("@")
    if sep and name and _looks_like_version(version):
        return name
    return spec


def _yaml_list_items(header: str, log: str) -> list[str]:
    found: list[str] = []
    lines = log.splitlines()
    index = 0
    while index < len(lines):
        if lines[index].strip() != header:
            index += 1
            continue
        index += 1
        while index < len(lines):
            line = lines[index]
            if not line.strip():
                break
            item = re.match(r"^[ \t]*-[ \t]+(.+?)\s*$", line)
            if not item:
                break
            value = _unquote_yaml(item.group(1))
            if value:
                found.append(value)
            index += 1
    return found


def parse_allow_build_keys(log: str) -> list[str]:
    """Keys pnpm told us to put in allowBuilds / onlyBuiltDependencies.

    Git-hosted prepare (pnpm 10.26 and later) prints the resolved dep path,
    not the package name:

        onlyBuiltDependencies:
          - "<name>@<resolved git or codeload url>"

    dsh says to copy that exact key under allowBuilds. Older hints still use
    `key: true` and `Ignored build scripts:`.
    """
    keys: list[str] = []
    for match in re.finditer(r"(?m)^[ \t]{2,}(\S+):[ \t]*true[ \t]*$", log):
        key = _unquote_yaml(match.group(1))
        # A leading @ without a slash is not a package key. @scope/name and
        # git dep paths both contain a slash.
        if not key.startswith("@") or "/" in key:
            keys.append(key)
    ignored = re.search(r"Ignored build scripts:\s*(.+)$", log, re.M)
    if ignored:
        for part in ignored.group(1).split(","):
            part = _unquote_yaml(part.strip())
            if part:
                keys.append(part)
    listed = _yaml_list_items("onlyBuiltDependencies:", log)
    keys.extend(listed)
    # The YAML example is the dep path pnpm actually checks. The prose
    # "fetched from" URL sometimes omits the commit, so it is only a fallback
    # when pnpm did not print that list.
    if not listed:
        for match in re.finditer(
            r'Failed to prepare git-hosted package fetched from "([^"]+)"\s*:\s*'
            r'The git-hosted package "([^"]+)" needs to execute build scripts',
            log,
        ):
            fetch_url, printed = match.group(1).strip(), match.group(2).strip()
            name = package_name_only(printed)
            if name and fetch_url:
                keys.append(f"{name}@{fetch_url}")
    seen: list[str] = []
    for key in keys:
        if key and key not in seen:
            seen.append(key)
    return seen


def is_prepare_blocked(log: str) -> bool:
    """pnpm refused a git-hosted prepare script.

    dsh prints an allowBuilds hint for every git-spec failure, including a
    missing repository, so that sentence alone is not this class.
    """
    return re.search(
        r"ERR_PNPM_GIT_DEP_PREPARE_NOT_ALLOWED|"
        r"needs to execute build scripts but is not in the "
        r".(?:onlyBuiltDependencies|allowBuilds). allowlist",
        log,
    ) is not None


def l1_failure_class(log: str) -> str:
    """Separate a prepare gate from an engine mismatch and a real install failure.

    An engines.dsh rejection wins when both appear, so it is never relabeled
    as prepare-blocked and never waived.
    """
    if is_engine_mismatch(log):
        return "engine-mismatch"
    if is_prepare_blocked(log):
        return "prepare-blocked"
    if is_network_failure(log):
        return "network-fail"
    return "install-fail"


def l1_failure_why(log: str) -> str:
    kind = l1_failure_class(log)
    if kind == "engine-mismatch":
        return "install-fail (engine mismatch against official @deepseek-ai/dsh@latest)"
    if kind == "prepare-blocked":
        return (
            "prepare-blocked (pnpm refused the git-hosted prepare script via "
            "onlyBuiltDependencies/allowBuilds; the verify pipeline retry did not clear it. "
            "This is not an engines.dsh rejection and not evidence the plugin package is broken.)"
        )
    if kind == "network-fail":
        return "network-fail"
    return "install-fail"


def is_network_failure(log: str) -> bool:
    return re.search(
        r"failed to connect|could not connect|ENOTFOUND|ETIMEDOUT|UND_ERR|"
        r"ECONNRESET|ECONNREFUSED|network is unreachable|git ls-remote.*fatal|EAI_AGAIN",
        log,
        re.I,
    ) is not None


def is_engine_mismatch(log: str) -> bool:
    return re.search(
        r"EBADENGINE|ERR_PNPM_UNSUPPORTED_ENGINE|Unsupported engine|"
        r"does not satisfy the required engines",
        log,
        re.I,
    ) is not None


def is_missing_harness_key(log: str) -> bool:
    return re.search(
        r"MISSING_CREDENTIAL|no API key for provider|DEEPSEEK_API_KEY",
        log,
        re.I,
    ) is not None


def is_plugin_credential(log: str) -> bool:
    return re.search(
        r"COMMAND_CODE_API_KEY|COMMANDCODE_API_KEY|COMMAND_API_KEY",
        log,
    ) is not None


def run_cmd(args: list[str], timeout: int, log_path: Path, env: dict, secrets: list[str]) -> tuple[int, str, int]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    header = "$ " + " ".join(args) + "\n"
    try:
        completed = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            env=env,
            check=False,
        )
        raw = completed.stdout or b""
        code = completed.returncode
        if code is None:
            code = 1
    except subprocess.TimeoutExpired as exc:
        raw = exc.stdout or b""
        if isinstance(raw, str):
            raw = raw.encode()
        raw += f"\n[timeout after {timeout}s]\n".encode()
        code = 124
    text = redact(raw.decode("utf-8", "replace"), secrets)
    with log_path.open("a", encoding="utf-8", errors="replace") as handle:
        handle.write(redact(header, secrets))
        handle.write(text)
        if not text.endswith("\n"):
            handle.write("\n")
    duration_ms = int((time.monotonic() - started) * 1000)
    return code, text, duration_ms


def read_activation(profile_dir: Path) -> tuple[list[str], list[str]]:
    manifest_path = profile_dir / "package.json"
    if not manifest_path.is_file():
        return [], []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [], []
    deps = set((manifest.get("dependencies") or {}).keys()) - OFFICIAL_DEPS
    bundles = set(((manifest.get("dsh") or {}).get("profile") or {}).get("bundles") or [])
    activated = sorted(dep for dep in deps if dep in bundles)
    inactive = sorted(dep for dep in deps if dep not in bundles)
    return activated, inactive


def activation_summary(output: str) -> str:
    """Prefer the loader's one-line reasons over a trailing stack."""
    kept: list[str] = []
    for line in output.splitlines():
        text = line.strip()
        if not text or text.startswith("at ") or text.startswith("at\t"):
            continue
        if any(token in text for token in (
            "did not activate",
            "waiting for service",
            "failed to load",
            "pending (",
            "MISSING_CREDENTIAL",
            "no API key",
        )):
            if text not in kept:
                kept.append(text)
    return "\n".join(kept[:8])


def classify_l3(code: int, output: str, key_present: bool) -> tuple[str, str]:
    # The prompt itself contains "OK". Only an answer line counts.
    answer = "\n".join(ln for ln in output.splitlines() if L3_PROMPT not in ln)
    if code == 0 and re.search(r"\bOK\b", answer):
        return "pass", ""
    summary = activation_summary(output) or snippet(output)
    if "waiting for service" in output.lower():
        # Same rule as scripts/verify-runtime.sh: a pending GUI/client service
        # (webServer, storage, workspace, connection, ...) is web-only, not a pass.
        return "web-only", summary
    if (not key_present) and is_missing_harness_key(output):
        return "needs-env", summary or "DEEPSEEK_API_KEY is not set, so the headless model call cannot run."
    if is_plugin_credential(output) and code != 0:
        return "needs-env", summary or "Plugin asked for an account credential this pilot does not have."
    if code == 124:
        return "fail", summary or "runtime-fail (timeout)"
    return "fail", summary or "runtime-fail"


def verdict_for(l1: str, l2: str, l3: str) -> str:
    if l1 != "pass":
        return "fail"
    if l2 == "needs-env" or l3 == "needs-env":
        return "needs-env"
    if l2 != "pass":
        return "fail"
    if l3 == "pass":
        return "l3-pass"
    if l3 == "web-only":
        return "web-only"
    if l3 == "skipped":
        return "incomplete"
    return "fail"


def verdict_for_l4(l1: str, l2: str, l4: str) -> str:
    if l1 != "pass" or l2 != "pass":
        return "fail"
    if l4 == "pass":
        return "l4-pass"
    if l4 == "skipped":
        return "incomplete"
    return "l4-fail"


def _has_dedicated_l4_probe(expect: dict) -> bool:
    """True when this plugin configured a selector, text, or route condition."""
    if list(expect.get("selectorsAny") or []):
        return True
    if list(expect.get("textAny") or []):
        return True
    if str(expect.get("route") or "").strip():
        return True
    return False


# Recorded on a generic pass. The token URL was already required by
# wait_for_web_token before l4_ready runs; this sentence says which criteria
# produced the pass.
_GENERIC_L4_PASS_DETAIL = (
    "Generic L4 pass using shell-mounted criteria, not a dedicated selector probe. "
    "The printed dsh web token URL was used, the web shell mounted, boot did not fail, "
    "and the server stayed alive."
)


def _generic_l4_failure_reason(cdp: dict) -> str:
    """Name every generic criterion that failed. A missing probe is not one of them."""
    reasons = []
    if not cdp.get("shellMounted"):
        extra = str(cdp.get("bootText") or cdp.get("detail") or "").strip()
        reasons.append("shell not mounted" + (f" ({extra})" if extra else ""))
    if cdp.get("bootFailed"):
        extra = str(cdp.get("bootText") or "").strip()
        reasons.append("boot failed" + (f" ({extra})" if extra else ""))
    # Fail closed when boot_and_probe did not record the web process as alive.
    if not cdp.get("serverAlive"):
        reasons.append("server not alive")
    return "L4 generic criteria failed: " + "; ".join(reasons) + "."


def l4_ready(cdp: dict, expect: dict) -> tuple[bool, str]:
    """Decide the browser probe. Facts come from l4-cdp.mjs; this is the verdict.

    A dedicated probe is selectorsAny, textAny, or route. Those conditions
    still have to match, and a miss is a failure. Shell and boot failures
    on that path are unchanged. serverAlive is not part of a dedicated pass.

    With no dedicated probe, the generic shell-mounted criteria apply:
    shell mounted, boot did not fail, and serverAlive. Missing probe
    configuration is not a failure. serverAlive is stamped by boot_and_probe
    from the web process; a caller that omits it fails the generic check.
    """
    if cdp.get("harnessError"):
        return False, str(cdp["harnessError"])
    if not _has_dedicated_l4_probe(expect):
        if not cdp.get("shellMounted") or cdp.get("bootFailed") or not cdp.get("serverAlive"):
            return False, _generic_l4_failure_reason(cdp)
        return True, _GENERIC_L4_PASS_DETAIL
    if not cdp.get("shellMounted"):
        return False, cdp.get("bootText") or cdp.get("detail") or "Web shell did not mount."
    if cdp.get("bootFailed"):
        return False, cdp.get("bootText") or "Web boot overlay reported a failure."
    found = cdp.get("selectors") or {}
    forbidden = [sel for sel in (expect.get("forbid") or []) if found.get(sel)]
    if forbidden:
        return False, "Plugin boot error UI present: " + ", ".join(forbidden)
    wanted = list(expect.get("selectorsAny") or [])
    texts = list(expect.get("textAny") or [])
    text_hits = cdp.get("texts") or {}
    selector_hit = any(found.get(sel) for sel in wanted)
    text_hit = any(text_hits.get(text) for text in texts)
    if (wanted or texts) and not selector_hit and not text_hit:
        buttons = ", ".join(cdp.get("buttons") or []) or "none"
        missing = []
        if wanted:
            missing.append("selectors " + ", ".join(wanted))
        if texts:
            missing.append("text " + ", ".join(texts))
        scripts = cdp.get("pluginResponses") or []
        extra = ""
        if scripts:
            extra = " Scripts: " + " | ".join(str(item) for item in scripts[:8])
        route_info = cdp.get("route") or {}
        route_note = ""
        if route_info.get("json"):
            route_note = f" Host route returned JSON {route_info.get('status')}."
        return False, "Plugin client UI was not in the page (" + "; ".join(missing) + ")." + route_note + " Buttons: " + buttons + extra
    route = expect.get("route") or ""
    info = cdp.get("route") or {}
    if route and expect.get("routeExpect") == "json" and not info.get("json"):
        return False, f"Route {route} did not return JSON (status {info.get('status')})."
    notes = []
    hit = [sel for sel in wanted if found.get(sel)]
    if hit:
        notes.append("selectors " + ", ".join(hit))
    seen = [text for text in texts if text_hits.get(text)]
    if seen:
        notes.append("text " + ", ".join(seen))
    if route and info.get("json"):
        notes.append(f"route {route} JSON {info.get('status')}")
    if expect.get("note"):
        notes.append(str(expect["note"]))
    return True, "; ".join(notes)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def stop_process_group(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except OSError:
        proc.terminate()
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return
        time.sleep(0.2)
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, OSError):
        proc.kill()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


# A complete `dsh web: <url>` line. The URL must already be on its own line so
# a torn write cannot yield a shortened token. The token is not synthesized.
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
_DSH_WEB_URL_RE = re.compile(r"dsh web:[ \t]+(https?://[^\s]+)[ \t]*\r?\n")


def extract_web_token_url(text: str) -> str:
    """Exact printed `dsh web:` URL that already carries a token, or ''."""
    raw = text or ""
    marker = "--- L4 web boot ---"
    if marker in raw:
        raw = raw.split(marker, 1)[-1]
    cleaned = _ANSI_RE.sub("", raw.replace("\r\n", "\n"))
    found = ""
    for match in _DSH_WEB_URL_RE.finditer(cleaned):
        url = match.group(1)
        if _url_has_token(url):
            found = url
    return found


def _url_has_token(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False
    try:
        pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    except ValueError:
        return False
    return any(key == "token" and value != "" for key, value in pairs)


def _read_log(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _timeout_label(timeout: float) -> str:
    if float(timeout).is_integer():
        return f"{int(timeout)}s"
    return f"{timeout:.1f}s"


def http_status(url: str, timeout: float = 3) -> int | None:
    """HTTP status of `url` itself. Redirects are not followed.

    On @deepseek-ai/dsh@0.2.2-rc.1 the printed token URL answers 303 See
    Other and sets the session cookie. Following that redirect without the
    cookie requests the tokenless root, which answers 401. urllib.request
    follows the 303 and then raises HTTPError, and HTTPError is a URLError,
    so the status < 500 check never saw either response.
    """
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return None
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    conn_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    conn = conn_cls(parsed.hostname, port, timeout=timeout)
    try:
        conn.request(
            "GET",
            path,
            headers={"Host": parsed.netloc, "Connection": "close", "Accept": "*/*"},
        )
        response = conn.getresponse()
        status = int(response.status)
        response.read(64)
        return status
    except (TimeoutError, OSError, http.client.HTTPException, ValueError):
        return None
    finally:
        conn.close()


def wait_http(url: str, proc: subprocess.Popen, timeout: float) -> bool:
    """True when `url` itself returns an HTTP status below 500.

    A direct 401 is below 500. The tokenless root on dsh 0.2.2-rc.1 is a
    fast 401, so this must be called with the printed token URL, not `/`.
    """
    deadline = time.monotonic() + max(0.0, timeout)
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return False
        remaining = deadline - time.monotonic()
        status = http_status(url, timeout=min(3.0, max(0.2, remaining)))
        if status is not None and status < 500:
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(0.5, remaining))
    return False


def wait_for_web_token(log_path: Path, proc: subprocess.Popen, timeout: float) -> tuple[str, str]:
    """Wait until the boot log prints a token URL and that URL accepts HTTP.

    Returns (url, error). `error` is empty on success. The tokenless root is
    not requested. If the log has no token URL, wait out `timeout` and return
    a human-readable reason. The token is never invented.
    """
    deadline = time.monotonic() + max(0.0, timeout)
    token_seen = ""
    while True:
        token_url = extract_web_token_url(_read_log(log_path))
        if token_url:
            token_seen = token_url
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            if wait_http(token_url, proc, remaining):
                return token_url, ""
            if proc.poll() is not None:
                return "", (
                    "Web process exited after printing a dsh web token URL, "
                    "before that URL accepted HTTP."
                )
            return "", (
                "Web server printed a dsh web token URL but that URL did not "
                f"accept HTTP before the boot timeout ({_timeout_label(timeout)})."
            )
        if proc.poll() is not None:
            return "", "Web process exited before it printed a dsh web token URL."
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(0.25, remaining))
    if token_seen:
        return "", (
            "Web server printed a dsh web token URL but that URL did not "
            f"accept HTTP before the boot timeout ({_timeout_label(timeout)})."
        )
    return "", (
        "Web boot did not print a dsh web token URL "
        "(expected a line like `dsh web: http://127.0.0.1:<port>/?token=...`) "
        f"before the boot timeout ({_timeout_label(timeout)})."
    )


def l4_browser_command(url: str, expect: dict, out_json: Path, screenshot: Path) -> list[str]:
    """argv for scripts/l4-cdp.mjs. `--url` is passed through unchanged."""
    return [
        "node",
        str(L4_SCRIPT),
        "--url",
        url,
        "--out",
        str(out_json),
        "--screenshot",
        str(screenshot),
        "--timeout",
        str(L4_TIMEOUT * 1000),
        "--expect",
        json.dumps(expect, ensure_ascii=False),
    ]


def run_l4_browser(url: str, expect: dict, out_json: Path, screenshot: Path, log_path: Path, env: dict, secrets: list[str]) -> tuple[int, dict, int]:
    code, text, duration = run_cmd(
        l4_browser_command(url, expect, out_json, screenshot),
        L4_TIMEOUT + 30,
        log_path,
        env,
        secrets,
    )
    cdp: dict = {}
    if out_json.is_file():
        try:
            cdp = json.loads(out_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cdp = {"harnessError": "l4-cdp.mjs wrote invalid JSON", "detail": snippet(text)}
    elif code == 124:
        cdp = {"harnessError": "", "shellMounted": False, "detail": "CDP script timed out"}
    else:
        cdp = {"harnessError": snippet(text) or f"l4-cdp.mjs exited {code} without a result", "shellMounted": False}
    if code == 2 and not cdp.get("harnessError"):
        cdp["harnessError"] = snippet(text) or "browser failed to start"
    return code, cdp, duration


def boot_and_probe(prof: str, expect: dict, log_dir: Path, log_path: Path, env: dict, secrets: list[str]) -> dict:
    """Start the web profile and run the vendored CDP script. Caller owns cleanup."""
    port = free_port()
    handle = log_path.open("a", encoding="utf-8")
    handle.write(f"\n--- L4 web boot ---\n$ dsh --profile {prof} --host 127.0.0.1 --port {port} --no-open\n")
    handle.flush()
    proc = subprocess.Popen(
        ["dsh", "--profile", prof, "--host", "127.0.0.1", "--port", str(port), "--no-open"],
        stdout=handle,
        stderr=subprocess.STDOUT,
        env=env,
        start_new_session=True,
    )
    started = time.monotonic()
    try:
        # Probe the printed token URL only. The tokenless root is not a
        # readiness check: on dsh 0.2.2-rc.1 it answers 401, and urllib
        # used to hide that status until the boot timeout elapsed.
        token_url, boot_error = wait_for_web_token(log_path, proc, WEB_BOOT_TIMEOUT)
        boot_ms = int((time.monotonic() - started) * 1000)
        if boot_error:
            tail = ""
            if log_path.is_file():
                tail = snippet(log_path.read_text(encoding="utf-8", errors="replace").split("--- L4 web boot ---", 1)[-1])
            alive = proc.poll() is None
            error = boot_error if not tail else boot_error + "\n" + tail
            return stage(
                "fail",
                boot_ms,
                error,
                url=token_url,
                serverAlive=alive,
                harness=False,
            )
        out_json = log_dir / f"{profile_name_file(prof)}-l4.json"
        screenshot = log_dir / f"{profile_name_file(prof)}-l4.png"
        code, cdp, dur = run_l4_browser(token_url, expect, out_json, screenshot, log_path, env, secrets)
        # Same snapshot the stage records. Generic L4 fails closed without it.
        alive = proc.poll() is None
        judged = dict(cdp)
        judged["serverAlive"] = alive
        ready, detail = l4_ready(judged, expect)
        harness = bool(cdp.get("harnessError")) or code == 2
        status = "pass" if ready else "fail"
        error = "" if ready else detail
        route = cdp.get("route") or {}
        if route.get("bodySnippet"):
            route = dict(route)
            route["bodySnippet"] = redact(str(route["bodySnippet"]), secrets)[:400]
        return stage(
            status,
            boot_ms + dur,
            error,
            url=token_url,
            browser=cdp.get("browser") or "",
            shellMounted=bool(cdp.get("shellMounted")),
            bootFailed=bool(cdp.get("bootFailed")),
            selectors=cdp.get("selectors") or {},
            route=route or None,
            consoleErrors=[redact(item, secrets) for item in (cdp.get("consoleErrors") or [])],
            pageErrors=[redact(item, secrets) for item in (cdp.get("pageErrors") or [])],
            screenshot=str(screenshot) if screenshot.is_file() else "",
            pluginResponses=cdp.get("pluginResponses") or [],
            serverAlive=alive,
            harness=harness,
            detail=detail,
        )
    finally:
        stop_process_group(proc)
        handle.close()


def profile_name_file(prof: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "", prof)[:60] or "plugin"


def verify_plugin(plugin: dict, home: Path, log_dir: Path, env: dict, secrets: list[str], key_present: bool, l4_mode: bool = False) -> dict:
    slug = plugin["slug"]
    spec = plugin.get("installSpec") or ""
    prof = profile_name(slug)
    prof_dir = home / "profiles" / prof
    log_path = log_dir / f"{prof}.log"
    started = time.monotonic()
    print(f"== {slug} ({spec or 'no spec'}) profile={prof}", flush=True)

    result = {
        "slug": slug,
        "installSpec": spec,
        "catalogTest": plugin.get("catalogTest") or "",
        "role": plugin.get("role") or "",
        "profile": prof,
        "log": str(log_path),
        "stages": {},
        "activatedPackages": [],
        "inactivePackages": [],
        "verifiedClaim": False,
    }

    if not spec:
        result["stages"] = {
            "L1": stage("skipped", error="No install spec."),
            "L2": stage("skipped"),
            "L3": stage("skipped"),
            "L4": stage("skipped", error=L4_REASON),
        }
        result["verdict"] = "fail"
        result["durationMs"] = int((time.monotonic() - started) * 1000)
        return result

    if prof_dir.exists():
        shutil.rmtree(prof_dir, ignore_errors=True)
    prof_dir.mkdir(parents=True, exist_ok=True)
    (prof_dir / "pnpm-workspace.yaml").write_text(workspace_text(), encoding="utf-8")

    l1_ms = 0
    l1_text = ""
    l1_last = ""
    l1_code = 1
    attempts = 0
    extra_keys: list[str] = []
    try:
        for attempt in range(1, 4):
            attempts = attempt
            runtime_pkg = WEB_PKG if l4_mode else HEADLESS_PKG
            code, text, dur = run_cmd(
                ["dsh", "plugin", "--profile", prof, "add", BASE_PKG, runtime_pkg, spec],
                L1_TIMEOUT,
                log_path,
                env,
                secrets,
            )
            l1_ms += dur
            l1_text += "\n" + text
            l1_last = text
            l1_code = code
            if code == 0:
                break
            # Git prepare and other pnpm build gates: copy the exact key pnpm
            # printed into this profile's allowBuilds and retry the same add.
            # Engines.dsh failures have no such key and are not retried here.
            new_keys = parse_allow_build_keys(text)
            existing = (prof_dir / "pnpm-workspace.yaml").read_text(encoding="utf-8") if (prof_dir / "pnpm-workspace.yaml").is_file() else ""
            fresh = [key for key in new_keys if f'"{key}": true' not in existing and f"  {key}:" not in existing]
            if fresh and prof_dir.is_dir():
                for key in fresh:
                    if key not in extra_keys:
                        extra_keys.append(key)
                (prof_dir / "pnpm-workspace.yaml").write_text(workspace_text(extra_keys), encoding="utf-8")
                label = "git prepare allowBuilds" if is_prepare_blocked(text) else "allowBuilds"
                print(f"  L1 retry {attempt}: {label} {', '.join(fresh)}", flush=True)
                continue
            if is_network_failure(text) and attempt < 3:
                time.sleep(5)
                continue
            break

        if l1_code == 0:
            l1_status = "pass"
            l1_error = ""
            if is_engine_mismatch(l1_text):
                l1_error = "Install exited 0 but the log mentions an engine mismatch."
        else:
            l1_status = "fail"
            # Classify the last attempt. An earlier prepare gate that the retry
            # got past must not hide a later engines.dsh rejection, and an
            # engines rejection must not be called a generic install-fail.
            why = l1_failure_why(l1_last)
            l1_error = snippet(l1_last) or why
            if why not in l1_error:
                l1_error = why + "\n" + l1_error
        stage_extra: dict = {"attempts": attempts}
        if extra_keys:
            stage_extra["allowBuilds"] = list(extra_keys)
        if l1_status != "pass":
            stage_extra["failureClass"] = l1_failure_class(l1_last)
        result["stages"]["L1"] = stage(l1_status, l1_ms, l1_error, **stage_extra)

        if l1_status != "pass":
            result["stages"]["L2"] = stage("skipped")
            result["stages"]["L3"] = stage("skipped")
            if l4_mode:
                result["stages"]["L4"] = stage("skipped", error="L1 did not pass, so the browser was not started.")
        else:
            code, text, dur = run_cmd(
                ["dsh", "--profile", prof, "--dump-config"],
                L2_TIMEOUT,
                log_path,
                env,
                secrets,
            )
            activated, inactive = read_activation(prof_dir)
            result["activatedPackages"] = activated
            result["inactivePackages"] = inactive
            if code != 0:
                if (not key_present) and is_missing_harness_key(text):
                    l2_status, l2_error = "needs-env", "DEEPSEEK_API_KEY is not set."
                elif is_plugin_credential(text):
                    l2_status, l2_error = "needs-env", snippet(text) or "Plugin credential missing."
                else:
                    l2_status, l2_error = "fail", snippet(text) or "load-fail"
            elif not activated:
                l2_status = "fail"
                l2_error = (
                    "dump-config exited 0 but no added dependency joined dsh.profile.bundles "
                    f"(inactive: {', '.join(inactive) or 'none'}). Treated as not loaded."
                )
            else:
                l2_status = "pass"
                l2_error = ""
                if inactive:
                    l2_error = "Also installed but not activated: " + ", ".join(inactive)
            result["stages"]["L2"] = stage(l2_status, dur, l2_error)

            if l2_status != "pass":
                result["stages"]["L3"] = stage("skipped")
                if l4_mode:
                    result["stages"]["L4"] = stage("skipped", error="L2 did not pass, so the browser was not started.")
            elif l4_mode:
                result["stages"]["L3"] = stage("skipped", error=L3_SKIPPED_FOR_L4)
                expect = dict(plugin.get("l4") or {})
                print(f"  L4 web CDP {slug}", flush=True)
                result["stages"]["L4"] = boot_and_probe(prof, expect, log_dir, log_path, env, secrets)
            else:
                code, text, dur = run_cmd(
                    ["dsh", "--profile", prof, L3_PROMPT],
                    L3_TIMEOUT,
                    log_path,
                    env,
                    secrets,
                )
                l3_status, l3_error = classify_l3(code, text, key_present)
                result["stages"]["L3"] = stage(
                    l3_status,
                    dur,
                    l3_error,
                    backend="deepseek" if key_present else "unset",
                )
        if "L4" not in result["stages"]:
            result["stages"]["L4"] = stage("skipped", error=L4_REASON)
    except Exception as exc:
        message = snippet(redact(str(exc), secrets)) or exc.__class__.__name__
        result["stages"].setdefault("L1", stage("fail", error=message))
        result["stages"].setdefault("L2", stage("skipped"))
        result["stages"].setdefault("L3", stage("skipped"))
        result["stages"].setdefault("L4", stage("fail" if l4_mode else "skipped", error=message if l4_mode else L4_REASON))
        print(f"  {slug} raised {exc.__class__.__name__}: {message}", flush=True)
    finally:
        shutil.rmtree(prof_dir, ignore_errors=True)

    l1 = result["stages"]["L1"]["status"]
    l2 = result["stages"]["L2"]["status"]
    l3 = result["stages"]["L3"]["status"]
    l4 = result["stages"]["L4"]["status"]
    if l4_mode:
        result["verdict"] = verdict_for_l4(l1, l2, l4)
    else:
        result["verdict"] = verdict_for(l1, l2, l3)
    # Evidence only. merge-verify.py and merge-webonly.py are not run, and an
    # L4 pass in this file is not a catalog Verified badge.
    result["verifiedClaim"] = False if l4_mode else result["verdict"] == "l3-pass"
    result["durationMs"] = int((time.monotonic() - started) * 1000)
    print(f"== {slug} -> {result['verdict']} (L1 {l1}, L2 {l2}, L3 {l3}, L4 {l4})", flush=True)
    return result


def settle_hmr_race() -> str:
    """Best-effort edit for the 0.1.0-rc.8 headless HMR race.

    That CLI checked ctx.get("hmr") immediately after loader.create(), while
    the fiber was still LOADING, so every headless prompt died before the
    model call. Web profiles disabled the hmr row; the fallback service then
    had no registerConfig, and that throw killed a server that was already
    listening. When the installed profile-boot bundle still contains that
    pattern, insert a one-second settle and skip user-patch watching if
    registerConfig is missing. Official latest moved this watcher out of
    profile-boot-*.js; the function then leaves the CLI unchanged. The edit
    stays on the runner. It is not a catalog change.
    """
    dsh_bin = shutil.which("dsh")
    if not dsh_bin:
        return "dsh not on PATH"
    lib = Path(dsh_bin).resolve().parent
    candidates = sorted(lib.glob("profile-boot-*.js"))
    if not candidates:
        return "profile-boot bundle not found; HMR race left unchanged"
    delay = os.environ.get("PILOT_HMR_SETTLE_MS", "1000").strip() or "1000"
    if not delay.isdigit():
        delay = "1000"
    marker = "pilot-hmr-settle"
    needle = "\t\tawait watchUserPatches(ctx, {\n\t\t\tbinName: NAME,\n\t\t\tfilename: composed.profile.patchPath,"
    delay_line = f"\t\tawait new Promise((resolve) => setTimeout(resolve, {delay})); // {marker}\n"
    watch_block = (
        "\t\tawait watchUserPatches(ctx, {\n"
        "\t\t\tbinName: NAME,\n"
        "\t\t\tfilename: composed.profile.patchPath,\n"
        "\t\t\tcompose: composeLive\n"
        "\t\t});\n"
        "\t\tawait watchUserPatches(ctx, {\n"
        "\t\t\tbinName: NAME,\n"
        "\t\t\tfilename: homePatchPath(),\n"
        "\t\t\tcompose: composeLive\n"
        "\t\t});"
    )
    guarded = (
        "\t\tif (typeof ctx.get(\"hmr\")?.registerConfig === \"function\") { // "
        + marker
        + "\n"
        + watch_block
        + "\n\t\t}"
    )
    notes = []
    patched = False
    for path in candidates:
        text = path.read_text(encoding="utf-8")
        original = text
        if delay_line not in text and needle in text:
            text = text.replace(needle, delay_line + needle, 1)
            notes.append(f"inserted {delay}ms settle in {path.name}")
        if "registerConfig === \"function\"" not in text and watch_block in text:
            text = text.replace(watch_block, guarded, 1)
            notes.append(f"skip user-patch watch when registerConfig is missing ({path.name})")
        if text != original:
            path.write_text(text, encoding="utf-8")
            patched = True
        elif marker in text or "registerConfig === \"function\"" in text:
            notes.append(f"already settled ({path.name})")
            patched = True
    if not patched:
        names = ", ".join(path.name for path in candidates)
        return f"pattern not found in {names}; HMR race left unchanged"
    return "; ".join(notes)


def tool_version(cmd: list[str], env: dict) -> str:
    try:
        completed = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30, env=env, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"unavailable ({exc})"
    text = (completed.stdout or b"").decode("utf-8", "replace").strip()
    first = text.splitlines()[0] if text else ""
    if completed.returncode != 0:
        return first or f"exit {completed.returncode}"
    return first


def recommendation_l4(report: dict) -> str:
    plugins = report["plugins"]
    passed = [p["slug"] for p in plugins if p["verdict"] == "l4-pass"]
    failed = [p["slug"] for p in plugins if p["verdict"] == "l4-fail"]
    other = [p["slug"] for p in plugins if p["verdict"] not in ("l4-pass", "l4-fail")]
    quota = next((p for p in plugins if p["slug"] == "yumiku-dsh-commandcode-quota"), None)
    lines = [
        f"L4 browser check ran {len(plugins)} plugin(s) on {report['runner']}. "
        f"l4-pass ({len(passed)}): {', '.join(passed) or 'none'}. "
        f"l4-fail ({len(failed)}): {', '.join(failed) or 'none'}. "
        f"Other ({len(other)}): {', '.join(other) or 'none'}.",
        "Catalog badges were not changed. merge-webonly.py was not run. "
        "An l4-pass in this file is evidence only and is not a Verified badge. "
        "The browser check does not send a model prompt, so DEEPSEEK_API_KEY was not used.",
    ]
    if quota and quota["verdict"] == "l4-pass":
        lines.append(
            "The known web-only plugin @yumiku/dsh-commandcode-quota is no longer "
            "stuck on webServer: the web shell mounted and the browser saw the "
            "plugin client plus a JSON host route. Recommend making this L4 job the "
            "default follow-up for intakes whose headless L3 is web-only, still as "
            "workflow_dispatch rather than on every catalog sync, until two or three "
            "more web-only plugins pass the same kind of probe. Keep the badge write "
            "on merge-webonly.py. A metadata test=verified row is not confirmed here."
        )
    elif quota:
        route = ((quota.get("stages") or {}).get("L4") or {}).get("route") or {}
        if route.get("json"):
            lines.append(
                "The web shell mounted and the plugin host route returned JSON, so the "
                "entry is not still stuck on webServer. The client UI was not in the page "
                "on the resolved official latest. Do not make L4 the default badge step, and do not "
                "write Verified, until that client is visible. Keep this job on "
                "workflow_dispatch as a report for web-only intakes."
            )
        else:
            lines.append(
                "The known web-only plugin did not pass L4. Do not make the browser job "
                "the default for web-only intakes until @yumiku/dsh-commandcode-quota is "
                "green. The failure is in this report. It is not a Verified result and it "
                "does not clear the existing metadata badge."
            )
    else:
        lines.append(
            "This run did not include @yumiku/dsh-commandcode-quota. Do not generalize "
            "from the optional plugins alone; the web-only case is the one that was "
            "blocked on webServer."
        )
    lines.append(
        "Headless L3 stays the check for plugins that answer in the terminal. "
        "L4 should stay limited to web-only results: a browser boot is slower, and a "
        "model round-trip is a separate check that needs DEEPSEEK_API_KEY. This job "
        "does not send that prompt. This job follows official @deepseek-ai/dsh@latest "
        "and records the resolved version. Do not freeze that runtime from this report."
    )
    return " ".join(lines)


def _l1_is(plugin: dict, kind: str) -> bool:
    row = (plugin.get("stages") or {}).get("L1") or {}
    if row.get("failureClass") == kind:
        return True
    error = (row.get("error") or "").lower()
    if kind == "engine-mismatch":
        return "engine mismatch" in error
    if kind == "prepare-blocked":
        return error.startswith("prepare-blocked")
    return False


def recommendation(report: dict) -> str:
    if report.get("mode") == "l4":
        return recommendation_l4(report)
    plugins = report["plugins"]
    n = len(plugins)
    l3_pass = sum(1 for p in plugins if p["verdict"] == "l3-pass")
    l1_pass = sum(1 for p in plugins if p["stages"].get("L1", {}).get("status") == "pass")
    web_only = sum(1 for p in plugins if p["verdict"] == "web-only")
    needs_env = sum(1 for p in plugins if p["verdict"] == "needs-env")
    engine = sum(1 for p in plugins if _l1_is(p, "engine-mismatch"))
    prepare_blocked = sum(1 for p in plugins if _l1_is(p, "prepare-blocked"))
    lines = [
        f"Ran {n} plugin(s) on {report['runner']}. L1 passed for {l1_pass}. "
        f"Headless L3 passed for {l3_pass}. Web-only: {web_only}. Needs credentials: {needs_env}. "
        f"Engine-mismatch install failures: {engine}. "
        f"Git prepare blocked by pnpm allowlist: {prepare_blocked}.",
        "Catalog badges were not changed. web-only is not Verified. needs-env is not Verified. "
        "An L3 pass in this file is evidence only; merge-verify.py was not run.",
        "A prepare-blocked L1 is ERR_PNPM_GIT_DEP_PREPARE_NOT_ALLOWED "
        "(onlyBuiltDependencies / allowBuilds): pnpm refused a git-hosted prepare script. "
        "That is a verify-pipeline allowlist miss, not an engines.dsh rejection and not evidence "
        "the plugin package is broken. This job copies the exact key pnpm prints into that "
        "profile's allowBuilds and retries the same install. The allow covers git-hosted prepare "
        "inside this repository's verify install only. It does not relax engine checks and it "
        "does not run allow-version --accept-risk.",
    ]
    if report["deepseekApiKeyPresent"]:
        lines.append("DEEPSEEK_API_KEY was present, so L3 called the DeepSeek model.")
    else:
        lines.append(
            "DEEPSEEK_API_KEY was absent. L1 and L2 still run. L3 cannot be a real model answer "
            "until the repository secret is set and the workflow is re-run. Do not read a "
            "needs-env L3 as a plugin defect."
        )
    if engine:
        resolved = report.get("dshVersionActual") or "unknown"
        lines.append(
            "The runners install official @deepseek-ai/dsh@latest and record the resolved "
            f"CLI version ({resolved}). Several November 2026 intakes declare dsh >=0.2.x. "
            "An engine mismatch means the plugin's range does not include that resolved "
            "release, so it is not verified on the current official runtime."
        )
    if report.get("githubActions"):
        lines.append(
            "This run executed on a GitHub-hosted ubuntu runner, using the same L1–L3 commands "
            "as scripts/verify-runtime.sh."
        )
    lines.append(
        "L4 browser checks are scripts/l4-cdp.mjs via --l4 and "
        ".github/workflows/verify-pilot-l4.yml. This L1–L3 job does not run them and does "
        "not invent a CDP result. Do not freeze the audit runtime, and do not treat an L3 "
        "pass here as a catalog write."
    )
    return " ".join(lines)


def render_markdown(report: dict) -> str:
    lines = [
        "# DSH plugin verify pilot",
        "",
        f"- Started: {report['startedAt']}",
        f"- Finished: {report['finishedAt']}",
        f"- Runner: {report['runner']}",
        f"- Node: {report['node']}",
        f"- pnpm: {report['pnpm']}",
        f"- dsh requested: {report['dshVersionRequested']}",
        f"- dsh actual: {report['dshVersionActual']}",
        f"- profile packages: {report.get('officialPackages') or ''}",
        f"- HMR workaround: {report.get('hmrWorkaround', '')}",
        f"- DEEPSEEK_API_KEY present: {str(report['deepseekApiKeyPresent']).lower()}",
        f"- Mode: {report.get('mode') or 'l3'}",
        f"- Catalog updated: false",
        "",
        (
            "This run is L4 only. L3 was not called and DEEPSEEK_API_KEY was not used. "
            "`l4-pass` means a dedicated selector, text, or route probe matched, "
            "or there was no dedicated probe and the generic shell-mounted criteria passed "
            "(printed token URL, shell mounted, boot did not fail, server stayed alive). "
            "It does not change the catalog Verified badge."
            if report.get("mode") == "l4"
            else
            "Verified on dshbase requires L1 + L2 + L3 `pass` on official @deepseek-ai/dsh@latest. "
            "The resolved version is the `dsh actual` line above. "
            "L3 `web-only` is not a pass; L4 is a separate browser job. "
            "`needs-env` means a credential was missing."
        ),
        "",
        "| Plugin | Install spec | Catalog test | L1 | L2 | L3 | L4 | Verdict | Duration |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for plugin in report["plugins"]:
        stages = plugin["stages"]
        seconds = plugin.get("durationMs", 0) / 1000
        lines.append(
            "| {slug} | `{spec}` | {catalog} | {l1} | {l2} | {l3} | {l4} | {verdict} | {sec:.0f}s |".format(
                slug=plugin["slug"],
                spec=plugin["installSpec"] or "",
                catalog=plugin.get("catalogTest") or "—",
                l1=stages["L1"]["status"],
                l2=stages["L2"]["status"],
                l3=stages["L3"]["status"],
                l4=stages["L4"]["status"],
                verdict=plugin["verdict"],
                sec=seconds,
            )
        )
    lines += ["", "## Per plugin", ""]
    for plugin in report["plugins"]:
        lines.append(f"### {plugin['slug']}")
        lines.append("")
        if plugin.get("role"):
            lines.append(plugin["role"])
            lines.append("")
        lines.append(f"- Verdict: `{plugin['verdict']}` (verifiedClaim={str(plugin['verifiedClaim']).lower()})")
        if plugin.get("activatedPackages"):
            lines.append("- Activated: " + ", ".join(f"`{name}`" for name in plugin["activatedPackages"]))
        if plugin.get("inactivePackages"):
            lines.append("- Not activated: " + ", ".join(f"`{name}`" for name in plugin["inactivePackages"]))
        for name in ("L1", "L2", "L3", "L4"):
            row = plugin["stages"][name]
            lines.append(f"- {name}: `{row['status']}` ({row.get('durationMs', 0)} ms)")
            if name == "L1":
                if row.get("failureClass"):
                    lines.append(f"  - failure class: `{row['failureClass']}`")
                allowed = row.get("allowBuilds") or []
                if allowed:
                    shown = ", ".join(f"`{item}`" for item in allowed)
                    lines.append(f"  - allowBuilds added for this install: {shown}")
            if name == "L4":
                if row.get("browser"):
                    lines.append(f"  - browser: `{row['browser']}`")
                if row.get("url"):
                    lines.append(f"  - url: `{row['url']}`")
                if row.get("detail"):
                    lines.append(f"  - detail: {row['detail']}")
                if row.get("screenshot"):
                    lines.append(f"  - screenshot: `{row['screenshot']}`")
            if row.get("error"):
                lines.append("")
                lines.append("```")
                lines.append(row["error"].rstrip())
                lines.append("```")
        lines.append("")
    lines += ["## Recommendation", "", report["recommendation"], ""]
    if report.get("runUrl"):
        lines += [f"Actions run: {report['runUrl']}", ""]
    return "\n".join(lines)


def write_report(report: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "summary.md").write_text(render_markdown(report), encoding="utf-8")


def _self_check_web_token() -> None:
    """URL extraction, and wait_http / Playwright both receiving that URL."""
    printed = "http://127.0.0.1:41621/?token=Ab_cd-12EFghij"
    sample = (
        "$ dsh --profile p_dsh-kimino-theme --host 127.0.0.1 --port 41621 --no-open\n"
        "[kimino-theme] host half active (4/4 asset routes registered)\n"
        f"dsh web: {printed}\n"
    )
    assert extract_web_token_url(sample) == printed
    stale = (
        "dsh web: http://127.0.0.1:1/?token=stale\n"
        "--- L4 web boot ---\n"
        f"dsh web: {printed}\n"
    )
    assert extract_web_token_url(stale) == printed
    later = (
        "dsh web: http://127.0.0.1:1/?token=first\n"
        "dsh web: http://127.0.0.1:2/?token=second\n"
    )
    assert extract_web_token_url(later) == "http://127.0.0.1:2/?token=second"
    https_url = "https://127.0.0.1:8443/ui/?token=abc&x=1"
    assert extract_web_token_url(f"dsh web: {https_url}\n") == https_url
    colored = "\x1b[32mdsh web: http://127.0.0.1:9/?token=abc_DEF-01\x1b[0m\n"
    assert extract_web_token_url(colored) == "http://127.0.0.1:9/?token=abc_DEF-01"
    assert extract_web_token_url("dsh web: http://127.0.0.1:9/?token=partial") == ""
    assert extract_web_token_url("dsh web: http://127.0.0.1:9/\n") == ""
    assert extract_web_token_url("dsh web: http://127.0.0.1:9/?token=\n") == ""
    assert extract_web_token_url("dsh web: listening on 127.0.0.1 over plain HTTP\n") == ""
    assert extract_web_token_url("dsh web: opening the default browser; pass --no-open to disable\n") == ""
    assert extract_web_token_url("token=not-a-url\n") == ""

    paths: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            paths.append(self.path)
            extra: list[tuple[str, str]] = []
            if self.path.startswith("/?token=down"):
                status = 503
            elif self.path.startswith("/?token=nope"):
                status = 401
            elif "token=" in self.path:
                status = 303
                extra = [("Location", "./")]
            else:
                status = 401
            body = b"" if status == 303 else b"no\n"
            self.send_response(status)
            for key, value in extra:
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            if body:
                self.wfile.write(body)

        def log_message(self, fmt: str, *args: object) -> None:
            return

    class Alive:
        def poll(self) -> None:
            return None

    class Dead:
        def poll(self) -> int:
            return 1

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = int(server.server_address[1])
        token_url = f"http://127.0.0.1:{port}/?token=Ab_cd-12EFghij"
        nope_url = f"http://127.0.0.1:{port}/?token=nope"
        down_url = f"http://127.0.0.1:{port}/?token=down"
        assert http_status(token_url, timeout=2) == 303
        assert wait_http(token_url, Alive(), 2) is True
        assert http_status(nope_url, timeout=2) == 401
        # A direct 401 is status < 500, so it counts as HTTP. The boot loop
        # must still not pass the tokenless root: that root is this 401.
        assert wait_http(nope_url, Alive(), 2) is True
        assert wait_http(down_url, Alive(), 0.7) is False
        assert paths and all("token=" in item for item in paths)
        assert not any(item.split("?", 1)[0] == "/" and "token=" not in item for item in paths)

        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "boot.log"
            log_path.write_text("--- L4 web boot ---\n$ dsh --no-open\n", encoding="utf-8")

            def write_later() -> None:
                time.sleep(0.3)
                with log_path.open("a", encoding="utf-8") as handle:
                    handle.write(f"dsh web: {token_url}\n")

            threading.Thread(target=write_later, daemon=True).start()
            started = time.monotonic()
            got, err = wait_for_web_token(log_path, Alive(), 5)
            elapsed = time.monotonic() - started
            assert err == "", err
            assert got == token_url
            assert elapsed < 3, elapsed
            cmd = l4_browser_command(
                got,
                {"selectorsAny": [".widget"]},
                Path(tmp) / "out.json",
                Path(tmp) / "shot.png",
            )
            assert cmd[cmd.index("--url") + 1] == token_url
            cdp_source = L4_SCRIPT.read_text(encoding="utf-8")
            assert 'const url = arg("--url")' in cdp_source
            assert "page.goto(url," in cdp_source

            before = len(paths)
            bare = Path(tmp) / "bare.log"
            bare.write_text(
                "--- L4 web boot ---\n"
                "dsh web: listening on 127.0.0.1 over plain HTTP\n"
                "dsh web: http://127.0.0.1:9/\n",
                encoding="utf-8",
            )
            missing, reason = wait_for_web_token(bare, Alive(), 0.6)
            assert missing == ""
            assert "did not print a dsh web token URL" in reason
            assert len(paths) == before

            before = len(paths)
            dead_log = Path(tmp) / "dead.log"
            dead_log.write_text(f"--- L4 web boot ---\ndsh web: {token_url}\n", encoding="utf-8")
            exited, why = wait_for_web_token(dead_log, Dead(), 2)
            assert exited == "" and "exited after printing" in why
            assert len(paths) == before

            early = Path(tmp) / "early.log"
            early.write_text("--- L4 web boot ---\n", encoding="utf-8")
            gone, why = wait_for_web_token(early, Dead(), 2)
            assert gone == "" and "exited before it printed" in why
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def self_check() -> None:
    assert classify_l3(0, "OK\n", False)[0] == "pass"
    assert classify_l3(0, "Reply with exactly: OK\n", False)[0] == "fail"
    assert classify_l3(0, "Reply with exactly: OK\nOK\n", True)[0] == "pass"
    assert classify_l3(0, "sure, OK!", True)[0] == "pass"
    assert classify_l3(1, "entry waiting for service: webServer", False)[0] == "web-only"
    status, err = classify_l3(
        1,
        "Error: dsh: 1 entry did not activate\n"
        "dsh-dir-tree: pending (waiting for service: connection)\n"
        "    at boot (file:///x.js:1:1)\n",
        False,
    )
    assert status == "web-only" and "connection" in err and "at boot" not in err
    status, _err = classify_l3(1, 'llm-deepseek: no API key for provider route "x" MISSING_CREDENTIAL', False)
    assert status == "needs-env"
    assert classify_l3(1, "boom", True)[0] == "fail"
    assert verdict_for("pass", "pass", "pass") == "l3-pass"
    assert verdict_for("pass", "pass", "web-only") == "web-only"
    assert verdict_for("pass", "pass", "needs-env") == "needs-env"
    assert verdict_for("fail", "skipped", "skipped") == "fail"
    assert verdict_for("pass", "fail", "skipped") == "fail"
    assert verdict_for_l4("pass", "pass", "pass") == "l4-pass"
    assert verdict_for_l4("pass", "pass", "fail") == "l4-fail"
    assert verdict_for_l4("fail", "skipped", "skipped") == "fail"
    ready, note = l4_ready(
        {
            "shellMounted": True,
            "selectors": {".dcq-float": True, "#dcq-boot-error": False},
            "route": {"status": 200, "json": True},
        },
        {
            "selectorsAny": [".dcq-float", "#dcq-style"],
            "forbid": ["#dcq-boot-error"],
            "route": "/dsh-commandcode/api/key",
            "routeExpect": "json",
        },
    )
    assert ready and ".dcq-float" in note and "JSON 200" in note
    missed, why = l4_ready(
        {"shellMounted": True, "selectors": {".dcq-float": False}, "route": {"status": 200, "json": True}},
        {"selectorsAny": [".dcq-float"], "route": "/x", "routeExpect": "json"},
    )
    assert not missed and "selectors" in why
    loading, why = l4_ready({"shellMounted": False, "bootText": "Loading plugins"}, {"selectorsAny": [".x"]})
    assert not loading and "Loading" in why
    broken, why = l4_ready({"harnessError": "no browser"}, {"selectorsAny": [".x"]})
    assert not broken and why == "no browser"
    # No dedicated probe. Generic shell-mounted criteria, not a probe-missing failure.
    generic_cdp = {
        "shellMounted": True,
        "bootFailed": False,
        "serverAlive": True,
        "selectors": {},
        "detail": "shell mounted",
    }
    generic_ok, generic_note = l4_ready(generic_cdp, {})
    assert generic_ok, generic_note
    assert verdict_for_l4("pass", "pass", "pass" if generic_ok else "fail") == "l4-pass"
    assert "No L4 probe configured" not in generic_note
    assert "shell-mounted criteria" in generic_note
    assert "dedicated selector probe" in generic_note
    assert "shell mounted, boot did not fail, and the server stayed alive" in generic_note
    note_only, note_only_why = l4_ready(generic_cdp, {"note": "not a probe"})
    assert note_only and "shell-mounted criteria" in note_only_why
    shell_down, shell_why = l4_ready(
        {"shellMounted": False, "bootFailed": False, "serverAlive": True, "bootText": "Loading plugins"},
        {},
    )
    assert not shell_down and verdict_for_l4("pass", "pass", "fail") == "l4-fail"
    assert "shell not mounted" in shell_why and "Loading plugins" in shell_why
    assert "boot failed" not in shell_why and "server not alive" not in shell_why
    assert "No L4 probe configured" not in shell_why
    boot_down, boot_why = l4_ready(
        {"shellMounted": True, "bootFailed": True, "serverAlive": True, "bootText": "overlay failed"},
        {},
    )
    assert not boot_down and "boot failed" in boot_why and "overlay failed" in boot_why
    assert "shell not mounted" not in boot_why and "server not alive" not in boot_why
    assert "No L4 probe configured" not in boot_why
    server_down, server_why = l4_ready(
        {"shellMounted": True, "bootFailed": False, "serverAlive": False},
        {},
    )
    assert not server_down and server_why == "L4 generic criteria failed: server not alive."
    assert "No L4 probe configured" not in server_why
    missing_alive, missing_why = l4_ready({"shellMounted": True, "bootFailed": False}, {})
    assert not missing_alive and "server not alive" in missing_why
    all_down, all_why = l4_ready(
        {"shellMounted": False, "bootFailed": True, "serverAlive": False, "bootText": "failed"},
        {},
    )
    assert not all_down
    assert "shell not mounted" in all_why and "boot failed" in all_why and "server not alive" in all_why
    assert "No L4 probe configured" not in all_why
    harness_generic, harness_why = l4_ready(
        {"harnessError": "no browser", "shellMounted": False, "serverAlive": True},
        {},
    )
    assert not harness_generic and harness_why == "no browser"
    # Dedicated probes stay required. A miss is a probe miss, including when
    # the generic shell facts would otherwise pass. serverAlive is not consulted.
    kimino_expect = {
        "selectorsAny": [
            'html[data-kimino-theme="on"]',
            "#kimino-theme",
            'style[data-plugin="dsh-kimino-theme"]',
            "[data-kimino-backdrop]",
        ],
    }
    kimino_hit, kimino_note = l4_ready(
        {"shellMounted": True, "selectors": {"#kimino-theme": True}},
        kimino_expect,
    )
    assert kimino_hit and "#kimino-theme" in kimino_note
    assert "shell-mounted criteria" not in kimino_note
    kimino_miss, kimino_why = l4_ready(
        {
            "shellMounted": True,
            "bootFailed": False,
            "serverAlive": True,
            "selectors": {
                'html[data-kimino-theme="on"]': False,
                "#kimino-theme": False,
                'style[data-plugin="dsh-kimino-theme"]': False,
                "[data-kimino-backdrop]": False,
            },
        },
        kimino_expect,
    )
    assert not kimino_miss and "selectors" in kimino_why
    assert "shell-mounted criteria" not in kimino_why
    assert "No L4 probe configured" not in kimino_why
    assert verdict_for_l4("pass", "pass", "pass" if kimino_miss else "fail") == "l4-fail"
    text_hit, text_note = l4_ready(
        {"shellMounted": True, "serverAlive": False, "texts": {"Hello": True}},
        {"textAny": ["Hello"]},
    )
    assert text_hit and "Hello" in text_note
    text_miss, text_why = l4_ready(
        {"shellMounted": True, "serverAlive": True, "texts": {"Hello": False}},
        {"textAny": ["Hello"]},
    )
    assert not text_miss and "text Hello" in text_why
    route_miss, route_why = l4_ready(
        {"shellMounted": True, "serverAlive": True, "route": {"status": 404, "json": False}},
        {"route": "/plugins/events", "routeExpect": "json"},
    )
    assert not route_miss and "did not return JSON" in route_why
    route_hit, route_note = l4_ready(
        {"shellMounted": True, "serverAlive": False, "route": {"status": 200, "json": True}},
        {"route": "/plugins/events", "routeExpect": "json"},
    )
    assert route_hit and "JSON 200" in route_note
    dedicated_alive_off, dedicated_note = l4_ready(
        {
            "shellMounted": True,
            "serverAlive": False,
            "selectors": {".dcq-float": True},
            "route": {"status": 200, "json": True},
        },
        {"selectorsAny": [".dcq-float"], "route": "/x", "routeExpect": "json"},
    )
    assert dedicated_alive_off and ".dcq-float" in dedicated_note
    forbid_hit, forbid_why = l4_ready(
        {"shellMounted": True, "selectors": {"#dcq-boot-error": True, ".dcq-float": True}},
        {"selectorsAny": [".dcq-float"], "forbid": ["#dcq-boot-error"]},
    )
    assert not forbid_hit and forbid_why.startswith("Plugin boot error UI present")
    advice = recommendation({
        "mode": "l4",
        "runner": "self-check",
        "deepseekApiKeyPresent": False,
        "plugins": [{
            "slug": "yumiku-dsh-commandcode-quota",
            "verdict": "l4-pass",
            "stages": {"L1": {"status": "pass", "error": ""}},
        }],
    })
    assert "not a Verified badge" in advice and "default follow-up" in advice and "DEEPSEEK_API_KEY was not used" in advice
    keys = parse_allow_build_keys("  '@scope/pkg': true\nIgnored build scripts: left-pad@1.0.0, other@2\n")
    assert "@scope/pkg" in keys and "left-pad@1.0.0" in keys
    tui_key = (
        "@deepseek-harness-tui/dsh-tui@https://codeload.github.com/ccch1mneyyy/"
        "dsh-TUI/tar.gz/4c6131e763945cd5d7047d4ae841d4163bdf090f"
    )
    sidebar_key = (
        "dsh-better-sidebar@https://codeload.github.com/omdsh-dev/"
        "DSH-better-sidebar/tar.gz/bd6363021dd4af8ca9df239e0c59df35b873d6b4"
    )
    univer_key = (
        "dsh-univer-office@https://codeload.github.com/dream-num/"
        "dsh-univer-office/tar.gz/b7dea7cb03e4bfeeba2b1a6723e30eaa6b264ba2"
    )
    genui_key = (
        "@changfenhuang/dsh-genui@https://codeload.github.com/omdsh-dev/"
        "dsh-genui/tar.gz/8ed3999147d0d1a4815706d087a6f6e1fca9268f"
    )
    # Wave-1 pnpm text: onlyBuiltDependencies list, not `key: true`. The dsh
    # hint mentions allowBuilds for every git failure and must not add a key.
    tui_log = (
        "ERR_PNPM_GIT_DEP_PREPARE_NOT_ALLOWED Failed to prepare git-hosted package "
        'fetched from "https://codeload.github.com/ccch1mneyyy/dsh-TUI/tar.gz/'
        '4c6131e763945cd5d7047d4ae841d4163bdf090f": The git-hosted package '
        '"@deepseek-harness-tui/dsh-tui@0.19.0" needs to execute build scripts but '
        'is not in the "onlyBuiltDependencies" allowlist.\n'
        "onlyBuiltDependencies:\n"
        f'  - "{tui_key}"\n'
        "dsh: git-hosted plugins build on install via their prepare script, which "
        "pnpm blocks until allowed — add the exact key pnpm printed above under "
        "allowBuilds in /tmp/pnpm-workspace.yaml, then re-run\n"
    )
    assert parse_allow_build_keys(tui_log) == [tui_key]
    assert is_prepare_blocked(tui_log)
    assert l1_failure_class(tui_log) == "prepare-blocked"
    tui_why = l1_failure_why(tui_log)
    assert tui_why.startswith("prepare-blocked")
    assert "engine mismatch" not in tui_why.lower()
    prose_only = (
        "Failed to prepare git-hosted package fetched from "
        '"https://codeload.github.com/omdsh-dev/DSH-better-sidebar/tar.gz/'
        'bd6363021dd4af8ca9df239e0c59df35b873d6b4": The git-hosted package '
        '"dsh-better-sidebar@0.30.1" needs to execute build scripts but is not '
        'in the "onlyBuiltDependencies" allowlist.'
    )
    assert sidebar_key in parse_allow_build_keys(prose_only)
    file_log = (
        'ERR_PNPM_GIT_DEP_PREPARE_NOT_ALLOWED Failed to prepare git-hosted package '
        'fetched from "file:///tmp/tiny-prepare": The git-hosted package '
        '"tiny-prepare@1.0.0" needs to execute build scripts but is not in the '
        '"onlyBuiltDependencies" allowlist.\n'
        "onlyBuiltDependencies:\n"
        '  - "tiny-prepare@git+file:///tmp/tiny-prepare#d3b25e219bf5fd48c1f7de6f368cab9306d3e84f"\n'
    )
    assert parse_allow_build_keys(file_log) == [
        "tiny-prepare@git+file:///tmp/tiny-prepare#d3b25e219bf5fd48c1f7de6f368cab9306d3e84f"
    ]
    assert univer_key in parse_allow_build_keys(
        "onlyBuiltDependencies:\n"
        f"  - {univer_key}\n"
    )
    assert genui_key in parse_allow_build_keys(
        "allowBuilds:\n"
        f"  {genui_key}: true\n"
    )
    quoted_map = (
        "allowBuilds:\n"
        f'  "{genui_key}": true\n'
    )
    assert parse_allow_build_keys(quoted_map) == [genui_key]
    missing_repo = (
        "fatal: repository 'https://github.com/example/missing.git/' not found\n"
        "dsh: git-hosted plugins build on install via their prepare script, which "
        "pnpm blocks until allowed — add the exact key pnpm printed above under "
        "allowBuilds in /tmp/pnpm-workspace.yaml, then re-run\n"
    )
    assert parse_allow_build_keys(missing_repo) == []
    assert not is_prepare_blocked(missing_repo)
    assert l1_failure_class(missing_repo) == "install-fail"
    engine_log = (
        "ERR_PNPM_UNSUPPORTED_ENGINE dsh-plugin-observatory requires "
        "@deepseek-ai/dsh-invariants >=0.1.0-rc.6 <0.2.0\n"
        + tui_log
    )
    assert l1_failure_class(engine_log) == "engine-mismatch"
    assert "engine mismatch" in l1_failure_why(engine_log)
    workspace = workspace_text([tui_key])
    assert f'  {json.dumps(tui_key)}: true' in workspace
    assert "allow-version" not in workspace
    assert "onlyBuiltDependencies:" not in workspace
    class_report = recommendation({
        "runner": "self-check",
        "deepseekApiKeyPresent": False,
        "dshVersionActual": "0.2.2-rc.1",
        "plugins": [
            {
                "slug": "dsh-TUI",
                "verdict": "fail",
                "stages": {"L1": {
                    "status": "fail",
                    "error": tui_why,
                    "failureClass": "prepare-blocked",
                }},
            },
            {
                "slug": "dsh-plugin-observatory",
                "verdict": "fail",
                "stages": {"L1": {
                    "status": "fail",
                    "error": l1_failure_why(engine_log),
                    "failureClass": "engine-mismatch",
                }},
            },
        ],
    })
    assert "Git prepare blocked by pnpm allowlist: 1." in class_report
    assert "Engine-mismatch install failures: 1." in class_report
    assert "allow-version --accept-risk" in class_report
    assert "not an engines.dsh rejection" in class_report
    parsed = parse_plugin_lines("slug-a|pkg@1.0.0|note\n# c\nslug-b\tpkgb\n")
    assert parsed[0]["slug"] == "slug-a" and parsed[0]["installSpec"] == "pkg@1.0.0"
    assert parsed[1]["slug"] == "slug-b" and parsed[1]["installSpec"] == "pkgb"
    red = redact("key=sk-abcdefghijklmnopqrstuvwxyz DEEPSEEK_API_KEY: supersecret", ["supersecret"])
    assert "supersecret" not in red and "sk-abcdefghijklmnopqrstuvwxyz" not in red
    sample = {
        "startedAt": "t0",
        "finishedAt": "t1",
        "runner": "self-check",
        "node": "v24",
        "pnpm": "10",
        "dshVersionRequested": DSH_DIST_TAG,
        "dshVersionActual": "resolved-at-runtime",
        "hmrWorkaround": "self-check",
        "deepseekApiKeyPresent": False,
        "runUrl": "",
        "plugins": [{
            "slug": "example",
            "installSpec": "example@1",
            "catalogTest": "listed",
            "role": "sample",
            "verdict": "web-only",
            "verifiedClaim": False,
            "durationMs": 1500,
            "activatedPackages": [],
            "inactivePackages": [],
            "stages": {
                "L1": stage("pass", 10),
                "L2": stage("pass", 20),
                "L3": stage("web-only", 30, error="waiting for service"),
                "L4": stage("skipped", error=L4_REASON),
            },
        }],
        "recommendation": "sample recommendation",
    }
    md = render_markdown(sample)
    assert "example" in md and "web-only" in md and "Catalog updated: false" in md
    assert "sample recommendation" in md
    l4_sample = dict(sample)
    l4_sample["mode"] = "l4"
    l4_plugin = dict(sample["plugins"][0])
    l4_plugin["slug"] = "dsh-pet"
    l4_plugin["verdict"] = "l4-pass"
    l4_plugin["stages"] = {
        "L1": stage("pass", 10),
        "L2": stage("pass", 20),
        "L3": stage("skipped"),
        "L4": stage(
            "pass",
            30,
            detail=_GENERIC_L4_PASS_DETAIL,
            shellMounted=True,
            bootFailed=False,
            serverAlive=True,
        ),
    }
    l4_sample["plugins"] = [l4_plugin]
    l4_md = render_markdown(l4_sample)
    assert "dsh-pet" in l4_md and "l4-pass" in l4_md
    assert "shell-mounted criteria" in l4_md
    assert "dedicated selector probe" in l4_md
    assert "No L4 probe configured" not in l4_md
    _self_check_web_token()
    print("self-check ok", flush=True)


def build_env(home: Path, secrets: list[str]) -> dict:
    env = os.environ.copy()
    env["DSH_HOME"] = str(home)
    env["CI"] = "true"
    env.setdefault("npm_config_fund", "false")
    # Never let a credential file from the developer machine leak into the run.
    env.pop("NPM_TOKEN", None)
    key = env.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        env.pop("DEEPSEEK_API_KEY", None)
    else:
        env["DEEPSEEK_API_KEY"] = key
        cred = home / ".credentials.yaml"
        home.mkdir(parents=True, exist_ok=True)
        escaped = key.replace("\\", "\\\\").replace('"', '\\"')
        cred.write_text(f'DEEPSEEK_API_KEY: "{escaped}"\n', encoding="utf-8")
        os.chmod(cred, 0o600)
        secrets.append(key)
    return env


def attach_l4_probes(plugins: list[dict]) -> None:
    known = {row["slug"]: row for row in L4_PLUGINS}
    for plugin in plugins:
        row = known.get(plugin["slug"])
        if not row:
            continue
        plugin["l4"] = dict(row.get("l4") or {})
        if not plugin.get("role"):
            plugin["role"] = row.get("role") or ""
        if not plugin.get("catalogTest"):
            plugin["catalogTest"] = row.get("catalogTest") or ""


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Pilot dsh plugin verification. Does not edit the catalog.")
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--l4", action="store_true", help="Boot dsh-web-app and run scripts/l4-cdp.mjs. Skips the headless model call.")
    parser.add_argument("--out-dir", default="pilot-report")
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--plugins-file", default="")
    args = parser.parse_args(argv)

    if args.self_check:
        self_check()
        return 0

    explicit = ""
    if args.plugins_file:
        explicit = Path(args.plugins_file).read_text(encoding="utf-8")
    elif os.environ.get("PILOT_PLUGINS"):
        explicit = os.environ["PILOT_PLUGINS"]
    if args.l4 and not explicit.strip() and not args.only:
        plugins = [dict(row) for row in L4_PLUGINS]
    else:
        plugins = resolve_plugins(explicit, args.only or None)
        if args.l4:
            attach_l4_probes(plugins)
    if not plugins:
        print("no plugins selected", file=sys.stderr)
        return 2

    # The browser job must not turn a developer key into a model call.
    if args.l4:
        os.environ.pop("DEEPSEEK_API_KEY", None)

    home = Path(os.environ.get("DSH_HOME") or "/tmp/dsh-pilot-home").resolve()
    if home.exists():
        shutil.rmtree(home, ignore_errors=True)
    home.mkdir(parents=True, exist_ok=True)
    secrets: list[str] = []
    env = build_env(home, secrets)
    key_present = bool(env.get("DEEPSEEK_API_KEY"))

    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    log_dir = out_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    dsh_actual = tool_version(["dsh", "--version"], env)
    if dsh_actual.startswith("unavailable") or dsh_actual.startswith("exit"):
        print(f"dsh CLI not usable: {dsh_actual}", file=sys.stderr)
        return 2
    print(f"dsh dist-tag {DSH_DIST_TAG} resolved to {dsh_actual}", flush=True)
    try:
        bind_official_packages()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"profile packages: base {BASE_PKG}; headless {HEADLESS_PKG}; web {WEB_PKG}", flush=True)
    hmr_note = settle_hmr_race()
    print(f"hmr: {hmr_note}", flush=True)

    server = os.environ.get("GITHUB_SERVER_URL", "").rstrip("/")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    run_url = f"{server}/{repo}/actions/runs/{run_id}" if server and repo and run_id else ""

    report = {
        "reportVersion": 1,
        "pilot": "gha-ubuntu-latest-l4" if args.l4 else "gha-ubuntu-latest",
        "mode": "l4" if args.l4 else "l3",
        "startedAt": utc_now(),
        "finishedAt": "",
        "runner": os.environ.get("RUNNER_NAME") or os.environ.get("RUNNER_OS") or "local",
        "node": tool_version(["node", "--version"], env),
        "pnpm": tool_version(["pnpm", "--version"], env),
        "dshVersionRequested": DSH_DIST_TAG,
        "dshVersionActual": dsh_actual,
        "officialPackages": {
            "base": BASE_PKG,
            "headless": HEADLESS_PKG,
            "web": WEB_PKG,
        },
        "hmrWorkaround": hmr_note,
        "deepseekApiKeyPresent": key_present,
        "githubActions": os.environ.get("GITHUB_ACTIONS") == "true",
        "catalogUpdated": False,
        "l4": (
            {
                "status": "ran",
                "script": "scripts/l4-cdp.mjs",
                "browser": "playwright; system Chrome or bundled Chromium",
                "modelCall": False,
            }
            if args.l4
            else {"status": "skipped", "reason": L4_REASON}
        ),
        "runUrl": run_url,
        "plugins": [],
        "recommendation": "",
    }
    if "unavailable" in report["pnpm"]:
        print("pnpm is required on PATH (dsh plugin forwards to pnpm)", file=sys.stderr)
        return 2

    for plugin in plugins:
        report["plugins"].append(verify_plugin(plugin, home, log_dir, env, secrets, key_present, l4_mode=args.l4))
    report["finishedAt"] = utc_now()
    report["recommendation"] = recommendation(report)
    write_report(report, out_dir)
    print(f"wrote {out_dir / 'report.json'}", flush=True)
    print(report["recommendation"], flush=True)
    shutil.rmtree(home, ignore_errors=True)
    if not args.l4:
        return 0
    if any(plugin["stages"].get("L4", {}).get("harness") for plugin in report["plugins"]):
        print("L4 harness failed to start a browser", file=sys.stderr)
        return 2
    attempted = any(plugin["stages"].get("L4", {}).get("status") in ("pass", "fail") for plugin in report["plugins"])
    if not attempted:
        print("L4 was not attempted", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
