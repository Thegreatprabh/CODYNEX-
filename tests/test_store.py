"""Store tests: round-trip + slug + marker."""
import os
import stat

from dna.ingest import python_parser, git_miner
from dna.model import dna as dna_mod
from dna.model import store as store_mod
from tests import FIXTURE


def build_dna():
    nodes = python_parser.parse_project(FIXTURE)
    return dna_mod.build("fixture-proj", FIXTURE, nodes, git_miner.GitFacts())


def test_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(store_mod, "BASE", str(tmp_path))
    dna = build_dna()
    saved = store_mod.save(dna)
    assert os.path.isfile(saved)
    assert stat.S_IMODE(os.stat(os.path.dirname(saved)).st_mode) == 0o700
    loaded = store_mod.load("fixture-proj")
    assert loaded is not None
    assert loaded.project == "fixture-proj"
    assert set(loaded.components) == set(dna.components)
    assert loaded.dep_graph == dna.dep_graph
    assert loaded.reverse_graph == dna.reverse_graph
    assert loaded.components["service.py"].purpose == \
        dna.components["service.py"].purpose


def test_load_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(store_mod, "BASE", str(tmp_path))
    assert store_mod.load("nope") is None


def test_slugify():
    assert store_mod.slugify("My Project!") == "my-project"
    assert store_mod.slugify("  ") == "project"


def test_marker_walkup(tmp_path, monkeypatch):
    monkeypatch.setattr(store_mod, "BASE", str(tmp_path))
    proj = tmp_path / "proj"
    sub = proj / "sub" / "deep"
    sub.mkdir(parents=True)
    store_mod.mark_project(str(proj), "proj")
    assert store_mod.find_slug(str(sub)) == "proj"
    assert store_mod.find_slug(str(tmp_path)) is None
