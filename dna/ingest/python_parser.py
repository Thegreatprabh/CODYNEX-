"""Python source parser: stdlib `ast` based file analysis.

For each .py file extracts:
  - imports (module names, resolved to local files where possible)
  - functions (names + docstring first line)
  - classes (names + docstring first line)
  - call edges: function-level calls resolved to local definitions
    where possible (Name/Attribute calls).

Honest limits (v0.1.0): Python only; dynamic imports / exec /
getattr-style calls are invisible; Attribute-call resolution is
best-effort (method calls on unknown receivers are skipped).

SKIP_DIRS is shared with the watcher (dna/watch.py).
"""

import ast
import os
from dataclasses import dataclass, field

#: Directories ignored by both the parser and the file watcher.
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules",
             ".tox", ".eggs", "build", "dist", ".mypy_cache"}


@dataclass
class FunctionInfo:
    name: str
    doc: str = ""
    calls: list = field(default_factory=list)  # names of called functions


@dataclass
class ClassInfo:
    name: str
    doc: str = ""
    methods: list = field(default_factory=list)


@dataclass
class FileNode:
    """Raw facts extracted from one Python file."""
    path: str                    # path relative to project root
    imports: list = field(default_factory=list)      # raw (level, dotted_name) tuples
    local_imports: list = field(default_factory=list)  # resolved to local .py paths
    functions: list = field(default_factory=list)    # FunctionInfo (top-level)
    classes: list = field(default_factory=list)      # ClassInfo
    methods: list = field(default_factory=list)      # FunctionInfo (methods)
    module_doc: str = ""         # module docstring, first line
    lines: int = 0
    error: str = ""              # non-empty if parse failed


def _docstring(node):
    """First line of docstring, or ''."""
    doc = ast.get_docstring(node) or ""
    return doc.strip().split("\n")[0][:120]


class _Visitor(ast.NodeVisitor):
    def __init__(self):
        self.imports = []
        self.functions = []
        self.classes = []
        self.methods = []          # FunctionInfo for methods (qualified names)
        self._func_stack = []
        self._class_depth = 0
        self._class_stack = []

    # -- imports --
    # Stored as (level, dotted_name) tuples: level=0 → absolute import,
    # level>0 → relative (number of leading dots). Full dotted path is
    # kept so the resolver can map it to a real file.
    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append((0, alias.name))
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            # `from x.y import z` -> dependency on module x.y
            # `from .x import z` -> level=1, module="x"
            self.imports.append((node.level, node.module))
            # `from pkg import submodule` ALSO loads pkg/submodule.py —
            # record the submodule path too (resolver drops it if absent,
            # e.g. when z is a function/class rather than a submodule).
            for alias in node.names:
                if alias.name != "*":
                    self.imports.append(
                        (node.level, node.module + "." + alias.name))
        elif node.level:
            # relative import without module: `from . import x`
            # each name is a submodule of the current package
            for alias in node.names:
                self.imports.append((node.level, alias.name))
        self.generic_visit(node)

    # -- defs --
    def visit_FunctionDef(self, node):
        info = FunctionInfo(name=node.name, doc=_docstring(node))
        self._func_stack.append(info)
        self.generic_visit(node)
        self._func_stack.pop()
        if len(self._func_stack) == 0 and self._class_depth == 0:
            # top-level function (nested funcs and methods excluded)
            self.functions.append(info)
        elif self._class_depth > 0 and self._class_stack:
            info.name = f"{self._class_stack[-1]}.{node.name}"
            self.methods.append(info)
        return info

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        info = ClassInfo(name=node.name, doc=_docstring(node))
        for stmt in node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                info.methods.append(stmt.name)
        self.classes.append(info)
        self._class_depth += 1
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()
        self._class_depth -= 1

    # -- calls --
    def visit_Call(self, node):
        name = None
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            # method call: obj.method() -> record "method" (best-effort)
            name = node.func.attr
        if name and self._func_stack:
            self._func_stack[-1].calls.append(name)
        self.generic_visit(node)


def _resolve_local(imports, file_dir, all_files):
    """Map raw imports to local .py paths (best effort).

    imports: list of (level, dotted_name) tuples from the visitor.
    all_files: set of project-relative paths like 'pkg/mod.py'.

    Absolute (`level == 0`): `a.b.c` -> 'a/b/c.py' or 'a/b/c/__init__.py'
    checked against the project tree.
    Relative (`level > 0`): climb `level - 1` directories up from the
    importing file's directory, then resolve the dotted path there.
    Falls back to basename matching for absolute imports.
    """
    resolved = []
    for level, mod in imports:
        if level == 0:
            base = mod.replace(".", os.sep)
            candidates = [
                base + ".py",
                os.path.join(base, "__init__.py"),
            ]
        else:
            pkg = file_dir
            for _ in range(level - 1):
                pkg = os.path.dirname(pkg)
            base = mod.replace(".", os.sep)
            candidates = [
                os.path.join(pkg, base + ".py"),
                os.path.join(pkg, base, "__init__.py"),
            ]
        hit = next((c for c in candidates if c in all_files), None)
        if hit is None and level == 0:
            # fallback: any file whose basename matches the last segment
            tail = mod.split(".")[-1]
            matches = [f for f in all_files
                       if os.path.basename(f) == tail + ".py"]
            hit = matches[0] if matches else None
        if hit:
            resolved.append(hit)
    # dedupe, preserve order
    seen, out = set(), []
    for r in resolved:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def parse_file(abs_path, rel_path):
    """Parse one file. Returns FileNode (error set on failure)."""
    node = FileNode(path=rel_path)
    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            src = f.read()
    except OSError as e:
        node.error = f"read error: {e}"
        return node
    node.lines = src.count("\n") + 1
    try:
        tree = ast.parse(src, filename=rel_path)
    except SyntaxError as e:
        node.error = f"syntax error: {e}"
        return node
    visitor = _Visitor()
    visitor.visit(tree)
    node.module_doc = _docstring(tree)
    node.imports = sorted(set(visitor.imports))
    node.functions = visitor.functions
    node.classes = visitor.classes
    node.methods = visitor.methods
    return node


def parse_project(root):
    """Walk root, parse every .py file (skipping junk dirs).

    Returns list[FileNode] with local_imports resolved.
    """
    py_files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.endswith(".py"):
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, root)
                py_files.append((full, rel))
    nodes = [parse_file(full, rel) for full, rel in sorted(py_files)]
    all_files = {n.path for n in nodes}
    for n in nodes:
        file_dir = os.path.dirname(n.path)
        n.local_imports = _resolve_local(n.imports, file_dir, all_files)
    return nodes
