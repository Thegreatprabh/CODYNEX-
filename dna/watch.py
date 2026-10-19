"""Continuously-updated DNA: polling file watcher (stdlib only).

watch_project() snapshots .py mtimes, and on every change re-parses ONLY
the changed files, rebuilds the ProjectDNA from the in-memory node cache,
and re-saves. New files, deleted files, and Ctrl+C are handled.

No watchdog dependency — os.path.getmtime + time.sleep only.
"""

import os
import time

from .ingest import python_parser, git_miner
from .ingest.python_parser import SKIP_DIRS
from .model import dna as dna_mod
from .model import store as store_mod


def snapshot(root):
    """Map {relative .py path: mtime} for root (same skips as the parser)."""
    snap = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.endswith(".py"):
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, root)
                try:
                    snap[rel] = os.path.getmtime(full)
                except OSError:
                    pass  # vanished mid-walk; next pass will settle it
    return snap


def _apply_update(root, slug, nodes, facts, changed, deleted):
    """Re-parse changed files, drop deleted ones, rebuild + save DNA."""
    for rel in changed:
        nodes[rel] = python_parser.parse_file(
            os.path.join(root, rel), rel)
    for rel in deleted:
        nodes.pop(rel, None)
    dna = dna_mod.build(slug, root, list(nodes.values()), facts)
    store_mod.save(dna)
    return dna


def watch_project(root, slug, interval=2.0, on_update=None, max_iterations=None):
    """Watch root for .py changes, keeping the stored DNA up to date.

    Returns the number of update cycles that detected changes.
    max_iterations caps the poll loop (used by tests; None = forever).
    KeyboardInterrupt exits cleanly.
    """
    root = os.path.abspath(root)
    print(f"ingesting {root} ...", flush=True)
    nodes = {n.path: n for n in python_parser.parse_project(root)}
    facts = git_miner.mine(root)
    dna = dna_mod.build(slug, root, list(nodes.values()), facts)
    store_mod.save(dna)
    old = snapshot(root)
    print(f"watching {len(old)} files in {root} "
          f"(every {interval:g}s) — Ctrl+C to stop", flush=True)

    updates = 0
    iterations = 0
    try:
        while True:
            time.sleep(interval)
            iterations += 1
            new = snapshot(root)
            changed = sorted(p for p, m in new.items()
                             if p not in old or old[p] != m)
            deleted = sorted(p for p in old if p not in new)
            if changed or deleted:
                _apply_update(root, slug, nodes, facts, changed, deleted)
                updates += 1
                parts = []
                if changed:
                    parts.append(f"~{len(changed)} changed")
                if deleted:
                    parts.append(f"-{len(deleted)} deleted")
                print(f"update #{updates}: {', '.join(parts)} → DNA saved "
                      f"({len(nodes)} files)", flush=True)
                if on_update is not None:
                    on_update(changed + deleted)
            old = new
            if max_iterations is not None and iterations >= max_iterations:
                break
    except KeyboardInterrupt:
        print("\nstopped watching — DNA is up to date.", flush=True)
    return updates
