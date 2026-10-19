"""Change-planning tests: target extraction, confidence, suggestions."""
import pytest

from dna.ingest import python_parser, git_miner
from dna.model import dna as dna_mod
from dna.analysis import plan as plan_mod
from tests import FIXTURE


def build_dna():
    nodes = python_parser.parse_project(FIXTURE)
    return dna_mod.build("fixture", FIXTURE, nodes, git_miner.GitFacts())


def test_plan_exact_target_high_confidence():
    dna = build_dna()
    plan = plan_mod.plan_change(dna, "service.py")
    assert plan.resolved == ["service.py"]
    assert plan.confidence == "high"
    paths = [n.path for n in plan.affected]
    assert "app.py" in paths
    assert "service.py" not in paths  # target excluded from affected
    assert "tests/test_service.py" in plan.suggested_tests


def test_plan_quoted_target():
    dna = build_dna()
    plan = plan_mod.plan_change(dna, '"service.py"')
    assert plan.resolved == ["service.py"]
    assert plan.confidence == "high"


def test_plan_natural_language_keyword_fallback():
    dna = build_dna()
    plan = plan_mod.plan_change(dna, "change the checkout system")
    # "checkout" is an export of service.py; the rest are stopwords
    assert plan.resolved == ["service.py"]
    assert plan.confidence == "low"
    assert plan.affected  # blast radius still computed


def test_plan_basename_exact_high_confidence():
    dna = build_dna()
    plan = plan_mod.plan_change(dna, "utils")
    assert plan.resolved == ["utils.py"]
    assert plan.confidence == "high"  # basename/stem exact match


def test_plan_substring_medium_confidence():
    dna = build_dna()
    plan = plan_mod.plan_change(dna, "serv")
    assert "service.py" in plan.resolved
    assert plan.confidence == "medium"  # fuzzy substring match


def test_plan_risk_summary_and_hotspots():
    dna = build_dna()
    dna.hotspots["service.py"] = 7
    plan = plan_mod.plan_change(dna, "change the checkout system")
    assert set(plan.risk_summary) == {"high", "medium", "low"}
    assert sum(plan.risk_summary.values()) == len(plan.affected)
    assert ("service.py", 7) in plan.hotspots_in_blast


def test_plan_unknown_request_raises():
    dna = build_dna()
    with pytest.raises(ValueError):
        plan_mod.plan_change(dna, "xyznonexistent123")
    with pytest.raises(ValueError):
        plan_mod.plan_change(dna, "   ")


def test_plan_suggests_tests_importing_blast():
    dna = build_dna()
    plan = plan_mod.plan_change(dna, "utils.py")
    # tests/test_service.py imports service.py which is in utils' blast radius
    assert "tests/test_service.py" in plan.suggested_tests
