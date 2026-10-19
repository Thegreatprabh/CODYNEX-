"""Blast-radius prediction: what breaks if this component changes?

impact(target):
  1. Resolve the target string to component(s) via fuzzy name matching
     (basename, dotted path, or export name — heuristic, documented).
  2. Reverse-BFS over reverse_graph → every transitive dependent.
  3. Score each affected node for risk:
       no test coverage      +2
       churn hotspot         +1
       depth > 3             +1
       in a circular dep     +2
  4. Return ranked list with reasons.

Risk labels: 0-1 low, 2-3 medium, 4+ high.
"""

from collections import deque
from dataclasses import dataclass, field
import os


@dataclass
class AffectedNode:
    path: str
    depth: int
    score: int
    reasons: list = field(default_factory=list)
    label: str = "low"


def _label(score):
    if score >= 4:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


def resolve_target(dna, target):
    """Fuzzy-resolve a target string to component path(s).

    Matches, in order: exact path, basename, basename-without-ext,
    substring of path, export (function/class) name. Returns list.
    """
    t = target.strip().lower()
    paths = list(dna.components.keys())
    # exact path
    exact = [p for p in paths if p.lower() == t]
    if exact:
        return exact
    # basename / stem
    import os
    stem_hits = [p for p in paths
                 if os.path.basename(p).lower() == t
                 or os.path.splitext(os.path.basename(p))[0].lower() == t]
    if stem_hits:
        return stem_hits
    # substring of path
    sub = [p for p in paths if t in p.lower()]
    if sub:
        return sub
    # export name (function/class defined in the file)
    exp = [p for p, c in dna.components.items()
           if t in (e.lower() for e in c.exports)]
    return exp


def _reaches(dna, src, dst, visited):
    """True if dst reachable from src following dep_graph (excluding src itself)."""
    for dep in dna.dep_graph.get(src, []):
        if dep == dst:
            return True
        if dep not in visited:
            visited.add(dep)
            if _reaches(dna, dep, dst, visited):
                return True
    return False


def _in_cycle(dna, path):
    """True if path can reach itself via imports (circular dependency)."""
    return _reaches(dna, path, path, set())


def impact(dna, target):
    """Predict blast radius of changing `target`.

    Returns (resolved_paths, [AffectedNode...] ranked by score desc).
    Raises ValueError if the target resolves to nothing.
    """
    resolved = resolve_target(dna, target)
    if not resolved:
        raise ValueError(f"target {target!r} matches no component")

    # reverse BFS from all resolved nodes
    depth = {}
    queue = deque()
    for r in resolved:
        depth[r] = 0
        queue.append(r)
    while queue:
        node = queue.popleft()
        for dependent in dna.reverse_graph.get(node, []):
            if dependent not in depth:
                depth[dependent] = depth[node] + 1
                queue.append(dependent)

    hotspot_paths = set(dna.hotspots.keys())
    results = []
    for path, d in depth.items():
        if path in resolved:
            continue  # the change itself isn't "affected"
        comp = dna.components.get(path)
        score, reasons = 0, []
        if comp:
            base = os.path.basename(path)
            is_test = base.startswith("test_") or base.endswith("_test.py")
            if not comp.has_tests and not is_test:
                score += 2
                reasons.append("no test coverage")
            if d > 3:
                score += 1
                reasons.append(f"transitive depth {d}")
        else:
            score += 2
            reasons.append("unknown component (parse error?)")
        if path in hotspot_paths:
            score += 1
            reasons.append("churn hotspot")
        if _in_cycle(dna, path):
            score += 2
            reasons.append("circular dependency")
        results.append(AffectedNode(
            path=path, depth=d, score=score,
            reasons=reasons or ["direct/transitive dependent"],
            label=_label(score),
        ))
    results.sort(key=lambda n: (-n.score, n.depth, n.path))
    return resolved, results
