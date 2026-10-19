"""Change planning: natural-language request -> full prediction.

plan_change(dna, request):
  1. Extract candidate target(s): whole-string resolution first via
     blast.resolve_target (confidence "high" on exact path/basename,
     "medium" on fuzzy substring/export match), else a keyword fallback
     over the request's words (confidence "low").
  2. Reuse blast.impact() per resolved path for the blast radius (merged).
  3. Suggest tests: test files inside the blast radius + test files
     importing anything in it.
  4. Return a structured Plan: target, confidence, affected[],
     suggested_tests[], risk_summary, hotspots_in_blast[].
"""

import os
import re
from dataclasses import dataclass, field

from . import blast as blast_mod

STOPWORDS = {
    "change", "the", "a", "an", "and", "or", "to", "of", "in", "on",
    "for", "with", "add", "remove", "update", "fix", "refactor",
    "modify", "please", "system", "code", "file", "files", "all",
    "should", "would", "could", "this", "that", "it", "its",
}


def _is_test_file(path):
    return re.search(r"(^|[/_])test", os.path.basename(path)) is not None


@dataclass
class Plan:
    request: str
    target: str                      # cleaned request string
    resolved: list = field(default_factory=list)   # component paths
    confidence: str = "low"          # high | medium | low
    affected: list = field(default_factory=list)   # [AffectedNode]
    suggested_tests: list = field(default_factory=list)
    risk_summary: dict = field(default_factory=dict)  # high/medium/low counts
    hotspots_in_blast: list = field(default_factory=list)  # [(path, churn)]


def _exact_match(dna, t):
    """True if t is exactly a component path or basename/stem."""
    for p in dna.components:
        if p.lower() == t:
            return True
        base = os.path.basename(p).lower()
        if base == t or os.path.splitext(base)[0] == t:
            return True
    return False


def extract_target(dna, request):
    """Resolve a natural-language request to (component paths, confidence).

    Raises ValueError when nothing matches.
    """
    cleaned = request.strip().strip("'\"").strip()
    if not cleaned:
        raise ValueError("empty change request")
    resolved = blast_mod.resolve_target(dna, cleaned)
    if resolved:
        conf = "high" if _exact_match(dna, cleaned.lower()) else "medium"
        return resolved, conf
    # keyword fallback: try each meaningful word
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", cleaned.lower())
    hits = []
    for w in words:
        if len(w) < 3 or w in STOPWORDS:
            continue
        for r in blast_mod.resolve_target(dna, w):
            if r not in hits:
                hits.append(r)
    if hits:
        return hits, "low"
    raise ValueError(f"no component matches change request {request!r}")


def _suggest_tests(dna, resolved, affected):
    """Test files in the blast radius or importing anything in it."""
    blast_paths = set(resolved) | {n.path for n in affected}
    tests = set()
    for p, deps in dna.dep_graph.items():
        if not _is_test_file(p):
            continue
        if p in blast_paths or any(d in blast_paths for d in deps):
            tests.add(p)
    return sorted(tests)


def plan_change(dna, request):
    """Full change prediction for a natural-language request."""
    resolved, confidence = extract_target(dna, request)
    merged = {}
    for r in resolved:
        _, affected = blast_mod.impact(dna, r)  # r is an exact path
        for n in affected:
            cur = merged.get(n.path)
            if cur is None or (n.score, -n.depth) > (cur.score, -cur.depth):
                merged[n.path] = n
    affected = sorted(merged.values(),
                      key=lambda n: (-n.score, n.depth, n.path))
    summary = {"high": 0, "medium": 0, "low": 0}
    for n in affected:
        summary[n.label] = summary.get(n.label, 0) + 1
    hotspots = sorted(
        ((p, dna.hotspots[p])
         for p in set(resolved) | {n.path for n in affected}
         if p in dna.hotspots),
        key=lambda x: -x[1],
    )
    return Plan(
        request=request,
        target=request.strip().strip("'\"").strip(),
        resolved=resolved,
        confidence=confidence,
        affected=affected,
        suggested_tests=_suggest_tests(dna, resolved, affected),
        risk_summary=summary,
        hotspots_in_blast=hotspots,
    )
