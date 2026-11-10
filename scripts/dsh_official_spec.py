#!/usr/bin/env python3
"""Install spec for an official package that the installed dsh CLI depends on.

The runner installs `@deepseek-ai/dsh@latest`. Several `@deepseek-ai/dsh-*`
packages keep an older version on their own `latest` dist-tag, so
`dsh plugin add @deepseek-ai/dsh-base@latest` does not match the CLI.
This reads the exact dependency from the installed CLI's package.json.
It does not invent a version and it does not read scripts/dsh-overrides.yaml.

Usage:
  python3 scripts/dsh_official_spec.py @deepseek-ai/dsh-base
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def installed_dsh_manifest() -> dict:
    dsh_bin = shutil.which("dsh")
    if not dsh_bin:
        raise RuntimeError("dsh is not on PATH")
    # npm ships the bin at <package>/lib/bin.js (often via a symlink).
    manifest_path = Path(dsh_bin).resolve().parents[1] / "package.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"installed dsh package.json not found at {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"installed dsh package.json is not JSON: {manifest_path}") from exc
    if manifest.get("name") != "@deepseek-ai/dsh":
        raise RuntimeError(
            f"{manifest_path} is {manifest.get('name')!r}, expected @deepseek-ai/dsh"
        )
    return manifest


def _exact_version(declared: object) -> str:
    if not isinstance(declared, str):
        raise RuntimeError(f"dependency version must be a string, got {declared!r}")
    version = declared.strip()
    if (
        not version
        or any(ch.isspace() for ch in version)
        or version[0] in "^~><=*v"
        or ":" in version
        or not version[0].isdigit()
    ):
        raise RuntimeError(
            "refusing a non-exact dependency of installed @deepseek-ai/dsh: "
            f"{declared!r}"
        )
    return version


def official_spec(name: str, manifest: dict | None = None) -> str:
    package = name if name.startswith("@") else f"@deepseek-ai/{name}"
    data = installed_dsh_manifest() if manifest is None else manifest
    declared = (data.get("dependencies") or {}).get(package)
    if declared is None:
        raise RuntimeError(
            f"{package} is not a dependency of installed @deepseek-ai/dsh "
            f"{data.get('version')}"
        )
    return f"{package}@{_exact_version(declared)}"


def main(argv: list[str]) -> int:
    if len(argv) != 1 or not argv[0].strip():
        print(f"usage: {Path(sys.argv[0]).name} @deepseek-ai/dsh-base", file=sys.stderr)
        return 2
    try:
        print(official_spec(argv[0].strip()))
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
