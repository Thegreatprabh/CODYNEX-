"""MCP server (stdio JSON-RPC): 4 tools for AI agents.

Tools:
  dna_map        — architecture summary (components, dep stats)
  dna_impact     — blast radius for a target (args: {target})
  dna_decisions  — mined decisions (args: {limit})
  dna_plan       — full change prediction for a natural-language
                   request (args: {request})

Malformed JSON-RPC → -32600, unknown tool → -32601, bad args → -32602.
Never crashes on bad input.
"""

import json
import sys

from . import __version__
from .model import store as store_mod
from .analysis import blast as blast_mod
from .analysis import plan as plan_mod


def _read_request(line):
    try:
        return json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None


def _response(req_id, result=None, error=None):
    resp = {"jsonrpc": "2.0", "id": req_id}
    if error is not None:
        resp["error"] = error
    else:
        resp["result"] = result
    return resp


def _err(code, message):
    return {"code": code, "message": message}


def _load_dna(args):
    slug = (args or {}).get("project") or store_mod.find_slug()
    if not slug:
        return None, "no DNA found: run `dna init` in a project first"
    dna = store_mod.load(slug)
    if dna is None:
        return None, f"no saved DNA for project {slug!r}"
    return dna, None


def tool_dna_map(args):
    dna, err = _load_dna(args)
    if err:
        return None, _err(-32602, err)
    comps = [
        {"path": c.path, "purpose": c.purpose, "exports": c.exports[:8],
         "lines": c.lines, "has_tests": c.has_tests,
         "inbound": c.inbound, "outbound": c.outbound}
        for c in sorted(dna.components.values(), key=lambda c: c.path)
    ]
    return {
        "project": dna.project,
        "components": comps,
        "component_count": len(comps),
        "edge_count": sum(len(v) for v in dna.dep_graph.values()),
        "commit_count": dna.commit_count,
    }, None


def tool_dna_impact(args):
    args = args or {}
    if "target" not in args or not isinstance(args["target"], str):
        return None, _err(-32602, "missing required string arg: target")
    dna, err = _load_dna(args)
    if err:
        return None, _err(-32602, err)
    try:
        resolved, affected = blast_mod.impact(dna, args["target"])
    except ValueError as e:
        return None, _err(-32602, str(e))
    return {
        "target": args["target"],
        "resolved": resolved,
        "affected": [
            {"path": n.path, "depth": n.depth, "risk": n.label,
             "score": n.score, "reasons": n.reasons}
            for n in affected
        ],
    }, None


def tool_dna_decisions(args):
    args = args or {}
    limit = args.get("limit", 10)
    if not isinstance(limit, int) or limit < 1:
        return None, _err(-32602, "limit must be a positive int")
    dna, err = _load_dna(args)
    if err:
        return None, _err(-32602, err)
    return {
        "project": dna.project,
        "decisions": dna.decisions[:limit],
        "total": len(dna.decisions),
    }, None


def tool_dna_plan(args):
    args = args or {}
    if "request" not in args or not isinstance(args["request"], str):
        return None, _err(-32602, "missing required string arg: request")
    dna, err = _load_dna(args)
    if err:
        return None, _err(-32602, err)
    try:
        plan = plan_mod.plan_change(dna, args["request"])
    except ValueError as e:
        return None, _err(-32602, str(e))
    return {
        "request": plan.request,
        "target": plan.target,
        "resolved": plan.resolved,
        "confidence": plan.confidence,
        "affected": [
            {"path": n.path, "depth": n.depth, "risk": n.label,
             "score": n.score, "reasons": n.reasons}
            for n in plan.affected
        ],
        "suggested_tests": plan.suggested_tests,
        "risk_summary": plan.risk_summary,
        "hotspots_in_blast": [
            {"path": p, "commits": n} for p, n in plan.hotspots_in_blast
        ],
    }, None


TOOLS = {
    "dna_map": {
        "fn": tool_dna_map,
        "description": "Architecture summary of the ingested project.",
        "inputSchema": {"type": "object", "properties": {
            "project": {"type": "string"}}},
    },
    "dna_impact": {
        "fn": tool_dna_impact,
        "description": "Predict blast radius of changing a component.",
        "inputSchema": {"type": "object", "properties": {
            "target": {"type": "string"},
            "project": {"type": "string"}}, "required": ["target"]},
    },
    "dna_decisions": {
        "fn": tool_dna_decisions,
        "description": "Architectural decisions mined from git history.",
        "inputSchema": {"type": "object", "properties": {
            "limit": {"type": "integer"},
            "project": {"type": "string"}}},
    },
    "dna_plan": {
        "fn": tool_dna_plan,
        "description": "Full change prediction for a natural-language request.",
        "inputSchema": {"type": "object", "properties": {
            "request": {"type": "string"},
            "project": {"type": "string"}}, "required": ["request"]},
    },
}


def handle(request):
    """Handle one JSON-RPC request dict. Returns response dict."""
    if not isinstance(request, dict) or request.get("jsonrpc") != "2.0" \
            or "method" not in request:
        return _response(request.get("id") if isinstance(request, dict) else None,
                         error=_err(-32600, "invalid request"))
    req_id = request.get("id")
    method = request["method"]

    if method == "initialize":
        return _response(req_id, result={
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "dna", "version": __version__},
            "capabilities": {"tools": {}},
        })
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    if method == "tools/list":
        return _response(req_id, result={"tools": [
            {"name": name, "description": t["description"],
             "inputSchema": t["inputSchema"]}
            for name, t in TOOLS.items()
        ]})
    if method == "tools/call":
        params = request.get("params") or {}
        name = params.get("name")
        tool = TOOLS.get(name)
        if tool is None:
            return _response(req_id, error=_err(-32601, f"unknown tool {name!r}"))
        args = params.get("arguments") or {}
        if not isinstance(args, dict):
            return _response(req_id, error=_err(-32600, "arguments must be object"))
        try:
            result, error = tool["fn"](args)
        except Exception as e:  # never crash the server
            return _response(req_id, error=_err(-32603, f"tool error: {e}"))
        if error is not None:
            return _response(req_id, error=error)
        return _response(req_id, result={
            "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
        })
    return _response(req_id, error=_err(-32601, f"unknown method {method!r}"))


def serve():
    """Serve stdio JSON-RPC until EOF."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        request = _read_request(line)
        if request is None:
            sys.stdout.write(json.dumps(
                _response(None, error=_err(-32600, "parse error"))) + "\n")
            sys.stdout.flush()
            continue
        resp = handle(request)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
