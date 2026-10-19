"""Intent extraction tests: docstring summary, README notes, test names."""
import os

from dna.ingest import python_parser
from dna.ingest import intent as intent_mod
from dna.model import dna as dna_mod
from dna.ingest import git_miner

FIXTURE_INTENT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "fixture_intent")


def test_summary_from_docstring():
    nodes = python_parser.parse_project(FIXTURE_INTENT)
    intents = intent_mod.extract_intent(FIXTURE_INTENT, nodes)
    assert intents["billing.py"]["summary"].startswith("Billing engine")


def test_readme_note_mentions_component():
    nodes = python_parser.parse_project(FIXTURE_INTENT)
    intents = intent_mod.extract_intent(FIXTURE_INTENT, nodes)
    note = intents["billing.py"]["readme_note"]
    assert "invoicing" in note.lower()
    assert len(note) <= 200
    # ledger is also mentioned in the README
    assert "double-entry" in intents["ledger.py"]["readme_note"]


def test_tested_behaviours_from_test_names():
    nodes = python_parser.parse_project(FIXTURE_INTENT)
    intents = intent_mod.extract_intent(FIXTURE_INTENT, nodes)
    behaviours = intents["billing.py"]["tested_behaviours"]
    assert "test_invoice_total" in behaviours
    assert "test_invoice_refund" in behaviours
    assert len(behaviours) <= 5
    # ledger has no tests importing it
    assert intents["ledger.py"]["tested_behaviours"] == []


def test_intents_wired_into_dna_and_persisted():
    nodes = python_parser.parse_project(FIXTURE_INTENT)
    dna = dna_mod.build("intent-fixture", FIXTURE_INTENT, nodes,
                        git_miner.GitFacts())
    assert "billing.py" in dna.intents
    d = dna.to_dict()
    assert d["intents"]["billing.py"]["summary"].startswith("Billing engine")
    dna2 = dna_mod.ProjectDNA.from_dict(d)
    assert dna2.intents["billing.py"]["tested_behaviours"] == \
        dna.intents["billing.py"]["tested_behaviours"]


def test_no_readme_no_crash(tmp_path):
    proj = tmp_path / "bare"
    proj.mkdir()
    (proj / "mod.py").write_text('"""Just a module."""\nX = 1\n')
    nodes = python_parser.parse_project(str(proj))
    intents = intent_mod.extract_intent(str(proj), nodes)
    assert intents["mod.py"] == {
        "summary": "Just a module.",
        "readme_note": "",
        "tested_behaviours": [],
    }
