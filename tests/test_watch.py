"""Watcher tests: change detection, add/delete, stored DNA updates.

The poll loop is driven with a fake sleep that mutates the project
mid-watch and then raises KeyboardInterrupt for a clean exit.
All fast (<5s), zero network.
"""
import os
import shutil
import time

from dna import watch as watch_mod
from dna.model import store as store_mod
from tests import FIXTURE


def _copy_fixture(tmp_path):
    proj = tmp_path / "proj"
    shutil.copytree(FIXTURE, proj,
                    ignore=shutil.ignore_patterns("__pycache__"))
    return proj


def _run_watch(proj, tmp_path, mutate, max_polls=6):
    """Run watch_project with fake sleep; mutate(poll_no, proj) each poll."""
    store = tmp_path / "store"
    import pytest
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(store_mod, "BASE", str(store))
    real_sleep = time.sleep
    polls = {"n": 0}
    seen = []

    def fake_sleep(s):
        polls["n"] += 1
        mutate(polls["n"], proj)
        if polls["n"] >= max_polls:
            raise KeyboardInterrupt
        real_sleep(0.001)

    monkeypatch.setattr(time, "sleep", fake_sleep)
    try:
        updates = watch_mod.watch_project(
            str(proj), "wtest", interval=0.01,
            on_update=lambda paths: seen.extend(paths),
            max_iterations=10 ** 9)
        dna = store_mod.load("wtest")  # load while BASE is still patched
    finally:
        monkeypatch.undo()
    return updates, seen, dna


def test_watcher_detects_edit(tmp_path):
    proj = _copy_fixture(tmp_path)
    from dna.ingest import python_parser
    before = {}

    def mutate(n, proj):
        if n == 1:
            p = proj / "service.py"
            before["lines"] = python_parser.parse_file(str(p), "service.py").lines
        if n == 2:
            p = proj / "service.py"
            p.write_text(p.read_text() + "# touched by watcher test\n")
            # force a newer mtime (avoids coarse-granularity misses)
            t = time.time() + 5
            os.utime(p, (t, t))

    updates, seen, dna = _run_watch(proj, tmp_path, mutate)
    assert updates >= 1
    assert any("service.py" in p for p in seen)
    assert dna is not None
    assert dna.components["service.py"].lines == before["lines"] + 1


def test_watcher_handles_new_and_deleted_files(tmp_path):
    proj = _copy_fixture(tmp_path)

    def mutate(n, proj):
        if n == 2:
            (proj / "brand_new.py").write_text(
                '"""Brand new module."""\nVALUE = 42\n')
        if n == 3:
            (proj / "utils.py").unlink()

    updates, seen, dna = _run_watch(proj, tmp_path, mutate)
    assert updates >= 2
    assert "brand_new.py" in dna.components
    assert "utils.py" not in dna.components
    # dependents of utils no longer list it
    assert "utils.py" not in dna.dep_graph.get("service.py", [])
    assert any("brand_new.py" in p for p in seen)
    assert any("utils.py" in p for p in seen)


def test_watcher_clean_exit_on_ctrl_c(capsys, tmp_path):
    proj = _copy_fixture(tmp_path)
    updates, seen, dna = _run_watch(proj, tmp_path, lambda n, p: None,
                                    max_polls=2)
    assert updates == 0  # no changes made
    out = capsys.readouterr().out
    assert "watching" in out
    assert "stopped watching" in out
