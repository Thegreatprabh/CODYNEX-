"""Blast + risks tests on the fixture project."""
import pytest

from dna.ingest import python_parser, git_miner
from dna.model import dna as dna_mod
from dna.analysis import blast as blast_mod
from dna.analysis import risks as risks_mod
from tests import FIXTURE


def build_dna():
    nodes = python_parser.parse_project(FIXTURE)
    facts = git_miner.GitFacts()  # no git in fixture
    # simulate a hotspot for scoring tests
    facts.hotspots = {"service.py": 5}
    return dna_mod.build("fixture", FIXTURE, nodes, facts)


def test_dep_graph():
    dna = build_dna()
    assert sorted(dna.dep_graph["service.py"]) == ["models.py", "utils.py"]
    assert sorted(dna.reverse_graph["utils.py"]) == ["app.py", "service.py"]


def test_impact_finds_transitive_dependents():
    dna = build_dna()
    resolved, affected = blast_mod.impact(dna, "utils")
    assert resolved == ["utils.py"]
    paths = [n.path for n in affected]
    # service and app depend on utils (directly); app also via service
    assert "service.py" in paths
    assert "app.py" in paths
    assert "main2.py" not in paths
    assert "utils.py" not in paths  # the target itself is excluded


def test_impact_resolves_export_name():
    dna = build_dna()
    resolved, _ = blast_mod.impact(dna, "checkout")
    assert resolved == ["service.py"]


def test_impact_unknown_target():
    dna = build_dna()
    with pytest.raises(ValueError):
        blast_mod.impact(dna, "no_such_thing_xyz")


def test_risk_scoring_reasons():
    dna = build_dna()
    _, affected = blast_mod.impact(dna, "utils")
    by_path = {n.path: n for n in affected}
    # service.py: covered by fixture tests (+0) + hotspot (+1) = 1 → low
    svc = by_path["service.py"]
    assert svc.score == 1
    assert svc.label == "low"
    assert "churn hotspot" in svc.reasons
    # app.py: no test coverage (+2) → medium
    app = by_path["app.py"]
    assert app.score == 2
    assert app.label == "medium"
    assert "no test coverage" in app.reasons


def test_risks_report():
    dna = build_dna()
    rep = risks_mod.report(dna)
    assert rep["component_count"] == 6  # 5 modules + tests/test_service.py
    assert rep["cycles"] == []
    # main2.py: no inbound, no tests → dead-code candidate
    # (test files are excluded from dead-code candidates)
    assert "main2.py" in rep["dead_code_candidates"]
    assert "tests/test_service.py" not in rep["dead_code_candidates"]
    # app/utils/models/main2 untested; test file itself excluded
    assert "service.py" not in rep["untested"]
    assert "app.py" in rep["untested"]
    assert rep["hotspots"][0] == ("service.py", 5)


def test_cycle_detection():
    graph = {"a.py": ["b.py"], "b.py": ["a.py"], "c.py": []}
    cycles = risks_mod.find_cycles(graph)
    assert cycles == [["a.py", "b.py"]]
