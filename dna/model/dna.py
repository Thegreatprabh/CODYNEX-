"""ProjectDNA: the structured, continuously-updated model of a codebase.

Built from ingest facts (FileNode list + GitFacts). Components carry a
one-line purpose summary (from module docstring or filename heuristic),
their exports, and a test-coverage flag (does a test file import them?).
"""

import os
import re
from dataclasses import dataclass, field

from ..ingest import intent as intent_mod


@dataclass
class Component:
    path: str
    purpose: str = ""          # one-line summary
    exports: list = field(default_factory=list)  # function/class names
    lines: int = 0
    has_tests: bool = False    # a test file imports this component
    inbound: int = 0           # # of local files importing it
    outbound: int = 0          # # of local files it imports


@dataclass
class ProjectDNA:
    project: str                          # slug / name
    root: str                             # absolute path ingested
    components: dict = field(default_factory=dict)  # path -> Component
    dep_graph: dict = field(default_factory=dict)    # path -> [paths it imports]
    reverse_graph: dict = field(default_factory=dict)  # path -> [paths importing it]
    decisions: list = field(default_factory=list)   # dicts: sha/date/message/files
    bug_history: list = field(default_factory=list)  # dicts
    hotspots: dict = field(default_factory=dict)    # path -> churn count
    commit_count: int = 0
    errors: list = field(default_factory=list)      # parse errors: {path, error}
    intents: dict = field(default_factory=dict)     # path -> intent dict
    # intent dict: {"summary": str, "readme_note": str,
    #               "tested_behaviours": [str, ...]}

    # -- serialization --
    def to_dict(self):
        return {
            "project": self.project,
            "root": self.root,
            "components": {p: {
                "path": c.path, "purpose": c.purpose, "exports": c.exports,
                "lines": c.lines, "has_tests": c.has_tests,
                "inbound": c.inbound, "outbound": c.outbound,
            } for p, c in self.components.items()},
            "dep_graph": self.dep_graph,
            "reverse_graph": self.reverse_graph,
            "decisions": self.decisions,
            "bug_history": self.bug_history,
            "hotspots": self.hotspots,
            "commit_count": self.commit_count,
            "errors": self.errors,
            "intents": self.intents,
        }

    @classmethod
    def from_dict(cls, d):
        comps = {}
        for p, c in d.get("components", {}).items():
            comps[p] = Component(**c)
        return cls(
            project=d.get("project", ""),
            root=d.get("root", ""),
            components=comps,
            dep_graph=d.get("dep_graph", {}),
            reverse_graph=d.get("reverse_graph", {}),
            decisions=d.get("decisions", []),
            bug_history=d.get("bug_history", []),
            hotspots=d.get("hotspots", {}),
            commit_count=d.get("commit_count", 0),
            errors=d.get("errors", []),
            intents=d.get("intents", {}),
        )


_PURPOSE_HINTS = [
    (re.compile(r"test[_-]|[_-]test"), "tests"),
    (re.compile(r"cli|main|__main__"), "entry point / CLI"),
    (re.compile(r"config|settings"), "configuration"),
    (re.compile(r"model|schema|entity"), "data models"),
    (re.compile(r"util|helper|common"), "shared utilities"),
    (re.compile(r"api|route|view|handler"), "API / request handling"),
    (re.compile(r"db|store|repo|migrat"), "persistence layer"),
]


def _purpose(rel_path, file_node):
    """One-line purpose: module docstring first, else filename heuristic."""
    if file_node.module_doc:
        return file_node.module_doc
    base = os.path.basename(rel_path)
    for rx, hint in _PURPOSE_HINTS:
        if rx.search(base):
            return hint
    exports = [f.name for f in file_node.functions] + \
              [c.name for c in file_node.classes]
    if exports:
        return "module: " + ", ".join(exports[:4])
    return "module"


def build(project, root, file_nodes, git_facts):
    """Assemble ProjectDNA from ingest facts."""
    dna = ProjectDNA(project=project, root=root)

    # components + dep graph
    for n in file_nodes:
        if n.error:
            dna.errors.append({"path": n.path, "error": n.error})
            continue
        exports = [f.name for f in n.functions] + [c.name for c in n.classes]
        dna.components[n.path] = Component(
            path=n.path, purpose=_purpose(n.path, n),
            exports=exports, lines=n.lines,
        )
        dna.dep_graph[n.path] = sorted(n.local_imports)

    # drop dangling edges (deleted files / parse errors): an edge must
    # point at a component that exists in the model
    valid = set(dna.components)
    for p in dna.dep_graph:
        dna.dep_graph[p] = [d for d in dna.dep_graph[p] if d in valid]

    # reverse graph + inbound/outbound counts
    for p in dna.components:
        dna.reverse_graph.setdefault(p, [])
    for src, deps in dna.dep_graph.items():
        for dep in deps:
            if dep in dna.components:
                dna.reverse_graph.setdefault(dep, []).append(src)
    for p, c in dna.components.items():
        c.outbound = len(dna.dep_graph.get(p, []))
        c.inbound = len(dna.reverse_graph.get(p, []))

    # test coverage flag: a test file is one whose path looks like a test
    # AND that imports the component
    test_files = [p for p in dna.components
                  if re.search(r"(^|[/_])test", os.path.basename(p))]
    for t in test_files:
        for dep in dna.dep_graph.get(t, []):
            if dep in dna.components:
                dna.components[dep].has_tests = True

    # git facts
    dna.decisions = [
        {"sha": d.sha, "date": d.date, "message": d.message, "files": d.files}
        for d in git_facts.decisions
    ]
    dna.bug_history = [
        {"sha": b.sha, "date": b.date, "message": b.message, "files": b.files}
        for b in git_facts.bug_history
    ]
    dna.hotspots = dict(git_facts.hotspots)
    dna.commit_count = git_facts.commit_count
    # intended-behaviour model (docstring + README + test names)
    try:
        dna.intents = intent_mod.extract_intent(root, file_nodes)
    except OSError:
        dna.intents = {}
    return dna
