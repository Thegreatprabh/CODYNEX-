"""Global risk report: project-wide structural risks.

Finds:
  - circular import groups (strongly connected components, Tarjan)
  - files with zero inbound deps AND no tests (dead/unused risk;
    test files themselves are excluded)
  - god-files (>500 lines)
  - top churn hotspots
"""

import os
import re

GOD_FILE_LINES = 500


def is_test_file(path):
    return re.search(r"(^|[/_])test", os.path.basename(path)) is not None


def find_cycles(dep_graph):
    """Tarjan's SCC. Returns list of cycles (each a sorted list of paths)."""
    index_of, lowlink, on_stack = {}, {}, set()
    stack, result, counter = [], [], [0]

    def strongconnect(v):
        index_of[v] = lowlink[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on_stack.add(v)
        for w in dep_graph.get(v, []):
            if w not in dep_graph:
                continue  # dep on unparsed file; ignore
            if w not in index_of:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], index_of[w])
        if lowlink[v] == index_of[v]:
            scc = []
            while True:
                w = stack.pop()
                on_stack.discard(w)
                scc.append(w)
                if w == v:
                    break
            if len(scc) > 1:
                result.append(sorted(scc))
            elif v in dep_graph.get(v, []):
                result.append([v])  # self-import

    for v in dep_graph:
        if v not in index_of:
            strongconnect(v)
    return sorted(result)


def report(dna, god_lines=GOD_FILE_LINES, top_hotspots=10):
    """Return a dict risk report."""
    cycles = find_cycles(dna.dep_graph)
    dead = sorted(
        p for p, c in dna.components.items()
        if c.inbound == 0 and not c.has_tests
        and not p.endswith("__init__.py")
        and not is_test_file(p)
    )
    gods = sorted(
        ((p, c.lines) for p, c in dna.components.items() if c.lines > god_lines),
        key=lambda x: -x[1],
    )
    hotspots = sorted(dna.hotspots.items(), key=lambda x: -x[1])[:top_hotspots]
    untested = sorted(p for p, c in dna.components.items()
                      if not c.has_tests and not is_test_file(p))
    return {
        "cycles": cycles,
        "dead_code_candidates": dead,
        "god_files": gods,
        "hotspots": hotspots,
        "untested": untested,
        "component_count": len(dna.components),
        "edge_count": sum(len(v) for v in dna.dep_graph.values()),
    }
