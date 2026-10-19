"""MCP server tests: protocol robustness + tools."""
import json

from dna import mcp_server
from dna.ingest import python_parser, git_miner
from dna.model import dna as dna_mod
from dna.model import store as store_mod
from tests import FIXTURE


def seed(tmp_path, monkeypatch):
    monkeypatch.setattr(store_mod, "BASE", str(tmp_path))
    nodes = python_parser.parse_project(FIXTURE)
    dna = dna_mod.build("fixture", FIXTURE, nodes, git_miner.GitFacts())
    store_mod.save(dna)
    monkeypatch.setattr(store_mod, "find_slug", lambda start=None: "fixture")


def call(method, params=None, req_id=1):
    req = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        req["params"] = params
    return mcp_server.handle(req)


def test_malformed_input():
    resp = mcp_server.handle({"nope": True})
    assert resp["error"]["code"] == -32600
    resp = mcp_server.handle("not a dict")
    assert resp["error"]["code"] == -32600


def test_unknown_method_and_tool():
    assert call("bogus")["error"]["code"] == -32601
    r = call("tools/call", {"name": "bogus", "arguments": {}})
    assert r["error"]["code"] == -32601


def test_initialize_and_list():
    r = call("initialize")
    assert r["result"]["serverInfo"]["name"] == "dna"
    r = call("tools/list")
    names = [t["name"] for t in r["result"]["tools"]]
    assert names == ["dna_map", "dna_impact", "dna_decisions", "dna_plan"]


def test_dna_map(tmp_path, monkeypatch):
    seed(tmp_path, monkeypatch)
    r = call("tools/call", {"name": "dna_map", "arguments": {}})
    body = json.loads(r["result"]["content"][0]["text"])
    assert body["component_count"] == 6
    assert body["edge_count"] > 0


def test_dna_impact(tmp_path, monkeypatch):
    seed(tmp_path, monkeypatch)
    r = call("tools/call", {"name": "dna_impact",
                            "arguments": {"target": "utils"}})
    body = json.loads(r["result"]["content"][0]["text"])
    assert body["resolved"] == ["utils.py"]
    assert any(a["path"] == "service.py" for a in body["affected"])
    # missing target → -32602, not a crash
    r = call("tools/call", {"name": "dna_impact", "arguments": {}})
    assert r["error"]["code"] == -32602


def test_dna_decisions(tmp_path, monkeypatch):
    seed(tmp_path, monkeypatch)
    r = call("tools/call", {"name": "dna_decisions",
                            "arguments": {"limit": 5}})
    body = json.loads(r["result"]["content"][0]["text"])
    assert body["decisions"] == []
    assert body["total"] == 0
    r = call("tools/call", {"name": "dna_decisions",
                            "arguments": {"limit": -1}})
    assert r["error"]["code"] == -32602


def test_tool_never_crashes_on_garbage_args():
    r = call("tools/call", {"name": "dna_map", "arguments": "nope"})
    assert r["error"]["code"] == -32600


def test_dna_plan(tmp_path, monkeypatch):
    seed(tmp_path, monkeypatch)
    r = call("tools/call", {"name": "dna_plan",
                            "arguments": {"request": "service.py"}})
    body = json.loads(r["result"]["content"][0]["text"])
    assert body["resolved"] == ["service.py"]
    assert body["confidence"] == "high"
    assert any(a["path"] == "app.py" for a in body["affected"])
    assert "tests/test_service.py" in body["suggested_tests"]
    # missing request → -32602, not a crash
    r = call("tools/call", {"name": "dna_plan", "arguments": {}})
    assert r["error"]["code"] == -32602
