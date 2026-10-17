#!/usr/bin/env python3
"""Thin wrapper around sync-dshso.py (kept for older docs / muscle memory).

Daily / Actions path: prefer `python scripts/sync-dshso.py`.

This wrapper forwards argv to sync-dshso and defaults to allowing adds
(historically merge-dshso imported missing plugins). Pass --no-add /
--max-add / --dry-run through as needed.

See sync-dshso.py docstring for source, dedup (repo identity only), and CI notes.
New entries default to test=listed (same as sync-dshso); refresh never downgrades.
"""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.argv[0] = os.path.join(HERE, "sync-dshso.py")
runpy.run_path(os.path.join(HERE, "sync-dshso.py"), run_name="__main__")
