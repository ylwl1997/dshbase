#!/usr/bin/env python3
"""Pilot L1–L3 plugin check for GitHub-hosted runners.

Reuses the install / dump-config / headless commands from
scripts/verify-runtime.sh and the package pin in scripts/dsh-overrides.yaml.
Writes a JSON report and a Markdown summary. Does not edit plugins.json,
does not call merge-verify.py, and does not talk to the catalog mirror.

Stages (same meanings as https://dshbase.com/audit/):
  L1  dsh plugin add into a clean profile, with dsh-base + dsh-headless
      pinned to DSH_VERSION (default 0.1.0-rc.8).
  L2  dsh --dump-config, and the plugin package is in dsh.profile.bundles.
  L3  headless prompt "Reply with exactly: OK".
      web-only (GUI service missing) is not a pass.
      A missing DEEPSEEK_API_KEY is needs-env, not a plugin failure.
  L4  skipped. verify-webonly.sh needs a host-local l3.mjs and a pinned
      Puppeteer Chrome that ubuntu-latest does not have.

Usage:
  python3 scripts/verify-pilot.py --self-check
  python3 scripts/verify-pilot.py --out-dir pilot-report
  python3 scripts/verify-pilot.py --only dsh-dir-tree --out-dir /tmp/pilot-report
  PILOT_PLUGINS=$'slug|spec\\n' python3 scripts/verify-pilot.py --out-dir pilot-report
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERRIDES = Path(__file__).resolve().parent / "dsh-overrides.yaml"
PLUGINS_JSON = ROOT / "src" / "data" / "plugins.json"

DSH_VERSION = os.environ.get("DSH_VERSION", "0.1.0-rc.8").strip() or "0.1.0-rc.8"
BASE_PKG = f"@deepseek-ai/dsh-base@{DSH_VERSION}"
HEADLESS_PKG = f"@deepseek-ai/dsh-headless@{DSH_VERSION}"
OFFICIAL_DEPS = {"@deepseek-ai/dsh-base", "@deepseek-ai/dsh-headless"}

L1_TIMEOUT = int(os.environ.get("PILOT_L1_TIMEOUT", "240"))
L2_TIMEOUT = int(os.environ.get("PILOT_L2_TIMEOUT", "180"))
L3_TIMEOUT = int(os.environ.get("PILOT_L3_TIMEOUT", "180"))
L3_PROMPT = "Reply with exactly: OK"

L4_REASON = (
    "Skipped. scripts/verify-webonly.sh drives L4 through ~/webverify/l3.mjs "
    "and a pinned Puppeteer Chrome path that are not in this repo and are not "
    "installed on ubuntu-latest. This pilot does not invent a CDP result."
)

# Historical allowBuilds seed from scripts/verify-runtime.sh. Further keys are
# appended only when pnpm prints them.
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
            "which matches this audit pin. No external account."
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
        lines.append(f'  "{key}": true')
    lines.append("overrides:")
    overlay = OVERRIDES.read_text(encoding="utf-8")
    if not overlay.endswith("\n"):
        overlay += "\n"
    return "\n".join(lines) + "\n" + overlay


def parse_allow_build_keys(log: str) -> list[str]:
    keys: list[str] = []
    for match in re.finditer(r"^\s{2}(\S+): true$", log, re.M):
        key = match.group(1).strip("'\"")
        if not key.startswith("@") or "/" in key:
            keys.append(key)
    ignored = re.search(r"Ignored build scripts:\s*(.+)$", log, re.M)
    if ignored:
        for part in ignored.group(1).split(","):
            part = part.strip().strip("'\"")
            if part:
                keys.append(part)
    seen: list[str] = []
    for key in keys:
        if key and key not in seen:
            seen.append(key)
    return seen


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


def verify_plugin(plugin: dict, home: Path, log_dir: Path, env: dict, secrets: list[str], key_present: bool) -> dict:
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
    l1_code = 1
    attempts = 0
    extra_keys: list[str] = []
    try:
        for attempt in range(1, 4):
            attempts = attempt
            code, text, dur = run_cmd(
                ["dsh", "plugin", "--profile", prof, "add", BASE_PKG, HEADLESS_PKG, spec],
                L1_TIMEOUT,
                log_path,
                env,
                secrets,
            )
            l1_ms += dur
            l1_text += "\n" + text
            l1_code = code
            if code == 0:
                break
            new_keys = parse_allow_build_keys(text)
            existing = (prof_dir / "pnpm-workspace.yaml").read_text(encoding="utf-8") if (prof_dir / "pnpm-workspace.yaml").is_file() else ""
            fresh = [key for key in new_keys if f'"{key}": true' not in existing and f"  {key}:" not in existing]
            if fresh and prof_dir.is_dir():
                for key in fresh:
                    if key not in extra_keys:
                        extra_keys.append(key)
                (prof_dir / "pnpm-workspace.yaml").write_text(workspace_text(extra_keys), encoding="utf-8")
                print(f"  L1 retry {attempt}: allowBuilds {', '.join(fresh)}", flush=True)
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
            why = "network-fail" if is_network_failure(l1_text) else "install-fail"
            if is_engine_mismatch(l1_text):
                why = "install-fail (engine mismatch against pinned dsh " + DSH_VERSION + ")"
            l1_error = snippet(l1_text) or why
            if why not in l1_error:
                l1_error = why + "\n" + l1_error
        result["stages"]["L1"] = stage(l1_status, l1_ms, l1_error, attempts=attempts)

        if l1_status != "pass":
            result["stages"]["L2"] = stage("skipped")
            result["stages"]["L3"] = stage("skipped")
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
        result["stages"]["L4"] = stage("skipped", error=L4_REASON)
    except Exception as exc:
        message = snippet(redact(str(exc), secrets)) or exc.__class__.__name__
        result["stages"].setdefault("L1", stage("fail", error=message))
        result["stages"].setdefault("L2", stage("skipped"))
        result["stages"].setdefault("L3", stage("skipped"))
        result["stages"].setdefault("L4", stage("skipped", error=L4_REASON))
        print(f"  {slug} raised {exc.__class__.__name__}: {message}", flush=True)
    finally:
        shutil.rmtree(prof_dir, ignore_errors=True)

    l1 = result["stages"]["L1"]["status"]
    l2 = result["stages"]["L2"]["status"]
    l3 = result["stages"]["L3"]["status"]
    result["verdict"] = verdict_for(l1, l2, l3)
    # A headless pass would qualify under the audit rule, but this pilot never
    # writes that claim back to the catalog.
    result["verifiedClaim"] = result["verdict"] == "l3-pass"
    result["durationMs"] = int((time.monotonic() - started) * 1000)
    print(f"== {slug} -> {result['verdict']} (L1 {l1}, L2 {l2}, L3 {l3})", flush=True)
    return result


def settle_hmr_race() -> str:
    """dsh 0.1.0-rc.8 checks ctx.get("hmr") immediately after loader.create().

    The HMR fiber is still LOADING at that point, so the service is missing and
    every headless prompt dies before the model call. One second is enough for
    the fiber to become ACTIVE on Node 22 and Node 24. The edit is local to the
    installed CLI and is marked so it runs once.
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
    insert = f"\t\tawait new Promise((resolve) => setTimeout(resolve, {delay})); // {marker}\n"
    notes = []
    patched = False
    for path in candidates:
        text = path.read_text(encoding="utf-8")
        if marker in text:
            notes.append(f"already settled ({path.name})")
            patched = True
            continue
        if needle not in text:
            continue
        path.write_text(text.replace(needle, insert + needle, 1), encoding="utf-8")
        notes.append(f"inserted {delay}ms settle in {path.name}")
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


def recommendation(report: dict) -> str:
    plugins = report["plugins"]
    n = len(plugins)
    l3_pass = sum(1 for p in plugins if p["verdict"] == "l3-pass")
    l1_pass = sum(1 for p in plugins if p["stages"].get("L1", {}).get("status") == "pass")
    web_only = sum(1 for p in plugins if p["verdict"] == "web-only")
    needs_env = sum(1 for p in plugins if p["verdict"] == "needs-env")
    engine = sum(
        1 for p in plugins
        if "engine mismatch" in (p["stages"].get("L1", {}).get("error") or "").lower()
    )
    lines = [
        f"Ran {n} plugin(s) on {report['runner']}. L1 passed for {l1_pass}. "
        f"Headless L3 passed for {l3_pass}. Web-only: {web_only}. Needs credentials: {needs_env}. "
        f"Engine-mismatch install failures: {engine}.",
        "Catalog badges were not changed. web-only is not Verified. needs-env is not Verified. "
        "An L3 pass in this file is evidence only; merge-verify.py was not run.",
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
        lines.append(
            f"The audit pages pin dsh {DSH_VERSION}. Several November 2026 intakes declare "
            "dsh >=0.2.x. An engine mismatch on this pin means the plugin is not verified on "
            "the published audit runtime."
        )
    if report.get("githubActions"):
        lines.append(
            "This run executed on a GitHub-hosted ubuntu runner, using the same L1–L3 commands "
            "as scripts/verify-runtime.sh."
        )
    lines.append(
        "L4 still depends on scripts/verify-webonly.sh and a host-local browser script that "
        "ubuntu-latest does not have. Keep that CDP step on the existing long-lived verify "
        "host until the script is vendored. Do not retune the audit pin, and do not treat "
        "Actions as the only verifier, until a follow-up covers a 0.2.x runtime for intakes "
        "that declare dsh >=0.2."
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
        f"- HMR workaround: {report.get('hmrWorkaround', '')}",
        f"- DEEPSEEK_API_KEY present: {str(report['deepseekApiKeyPresent']).lower()}",
        f"- Catalog updated: false",
        "",
        "Verified on dshbase requires L1 + L2 + L3 `pass` on the pinned runtime. "
        "L3 `web-only` is not a pass; L4 would be required and was skipped. "
        "`needs-env` means a credential was missing.",
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
    keys = parse_allow_build_keys("  '@scope/pkg': true\nIgnored build scripts: left-pad@1.0.0, other@2\n")
    assert "@scope/pkg" in keys and "left-pad@1.0.0" in keys
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
        "dshVersionRequested": DSH_VERSION,
        "dshVersionActual": DSH_VERSION,
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


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Pilot L1–L3 dsh plugin verification. Does not edit the catalog.")
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--out-dir", default="pilot-report")
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--plugins-file", default="")
    args = parser.parse_args(argv)

    if args.self_check:
        self_check()
        return 0

    if not OVERRIDES.is_file():
        print(f"missing {OVERRIDES}", file=sys.stderr)
        return 2

    explicit = ""
    if args.plugins_file:
        explicit = Path(args.plugins_file).read_text(encoding="utf-8")
    elif os.environ.get("PILOT_PLUGINS"):
        explicit = os.environ["PILOT_PLUGINS"]
    plugins = resolve_plugins(explicit, args.only or None)
    if not plugins:
        print("no plugins selected", file=sys.stderr)
        return 2

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
    if DSH_VERSION not in dsh_actual:
        print(f"warning: requested dsh {DSH_VERSION} but CLI reports {dsh_actual}", flush=True)
    hmr_note = settle_hmr_race()
    print(f"hmr: {hmr_note}", flush=True)

    server = os.environ.get("GITHUB_SERVER_URL", "").rstrip("/")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    run_url = f"{server}/{repo}/actions/runs/{run_id}" if server and repo and run_id else ""

    report = {
        "reportVersion": 1,
        "pilot": "gha-ubuntu-latest",
        "startedAt": utc_now(),
        "finishedAt": "",
        "runner": os.environ.get("RUNNER_NAME") or os.environ.get("RUNNER_OS") or "local",
        "node": tool_version(["node", "--version"], env),
        "pnpm": tool_version(["pnpm", "--version"], env),
        "dshVersionRequested": DSH_VERSION,
        "dshVersionActual": dsh_actual,
        "hmrWorkaround": hmr_note,
        "deepseekApiKeyPresent": key_present,
        "githubActions": os.environ.get("GITHUB_ACTIONS") == "true",
        "catalogUpdated": False,
        "l4": {"status": "skipped", "reason": L4_REASON},
        "runUrl": run_url,
        "plugins": [],
        "recommendation": "",
    }
    if "unavailable" in report["pnpm"]:
        print("pnpm is required on PATH (dsh plugin forwards to pnpm)", file=sys.stderr)
        return 2

    for plugin in plugins:
        report["plugins"].append(verify_plugin(plugin, home, log_dir, env, secrets, key_present))
    report["finishedAt"] = utc_now()
    report["recommendation"] = recommendation(report)
    write_report(report, out_dir)
    print(f"wrote {out_dir / 'report.json'}", flush=True)
    print(report["recommendation"], flush=True)
    shutil.rmtree(home, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
