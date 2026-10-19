"""Parser tests: imports, functions, classes, call edges."""
import os

from dna.ingest import python_parser
from tests import FIXTURE


def nodes():
    return {n.path: n for n in python_parser.parse_project(FIXTURE)}


def test_finds_all_files():
    ns = nodes()
    assert "app.py" in ns
    assert "service.py" in ns
    assert "models.py" in ns
    assert "utils.py" in ns
    assert "main2.py" in ns


def test_imports_resolved_to_local():
    ns = nodes()
    assert sorted(ns["service.py"].local_imports) == ["models.py", "utils.py"]
    assert sorted(ns["app.py"].local_imports) == ["service.py", "utils.py"]
    assert ns["utils.py"].local_imports == []
    assert ns["main2.py"].local_imports == []


def test_functions_extracted():
    ns = nodes()
    names = [f.name for f in ns["service.py"].functions]
    assert names == ["create_user", "checkout", "refund"]
    # methods must NOT leak into top-level functions
    assert all("." not in f.name for f in ns["service.py"].functions)


def test_classes_extracted():
    ns = nodes()
    names = [c.name for c in ns["models.py"].classes]
    assert names == ["User", "Order"]


def test_call_edges():
    ns = nodes()
    by_name = {f.name: f for f in ns["service.py"].functions}
    # checkout calls slugify + money (Name calls)
    assert "slugify" in by_name["checkout"].calls
    assert "money" in by_name["checkout"].calls
    # refund calls money
    assert "money" in by_name["refund"].calls


def test_module_doc():
    ns = nodes()
    assert ns["models.py"].module_doc.startswith("Fixture: models")


def test_broken_file_degrades():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        bad = os.path.join(d, "bad.py")
        with open(bad, "w") as f:
            f.write("def broken(:\n")
        ok = os.path.join(d, "ok.py")
        with open(ok, "w") as f:
            f.write("x = 1\n")
        ns = {n.path: n for n in python_parser.parse_project(d)}
        assert ns["bad.py"].error.startswith("syntax error")
        assert ns["ok.py"].error == ""


def test_dotted_imports_keep_full_path():
    """Regression: `from pkg.sub import x` must not be truncated to `pkg`."""
    import ast
    src = (
        "import pkg.sub\n"
        "from pkg.sub import thing\n"
        "from .sibling import other\n"
        "from . import cousin\n"
        "from ..toplevel import up\n"
    )
    v = python_parser._Visitor()
    v.visit(ast.parse(src))
    got = sorted(set(v.imports))
    assert (0, "pkg.sub") in got
    assert (1, "sibling") in got
    assert (1, "cousin") in got
    assert (2, "toplevel") in got


def test_resolve_absolute_and_relative():
    """Absolute `pkg.sub` -> pkg/sub.py; relative `.sibling` -> pkg/sibling.py."""
    all_files = {
        "pkg/__init__.py",
        "pkg/sub.py",
        "pkg/sibling.py",
        "pkg/cousin.py",
        "pkg/toplevel.py",
        "toplevel.py",
        "other.py",
    }
    r = python_parser._resolve_local
    # absolute import inside pkg/mod.py
    assert r([(0, "pkg.sub")], "pkg", all_files) == ["pkg/sub.py"]
    # relative imports inside pkg/mod.py
    assert r([(1, "sibling")], "pkg", all_files) == ["pkg/sibling.py"]
    assert r([(1, "cousin")], "pkg", all_files) == ["pkg/cousin.py"]
    # level-2 relative: `from ..toplevel import x` in pkg/deep/mod.py
    # -> parent package pkg -> pkg/toplevel.py
    assert r([(2, "toplevel")], "pkg/deep", all_files) == ["pkg/toplevel.py"]
    # level-3 relative: `from ...toplevel import x` -> project root
    assert r([(3, "toplevel")], "pkg/deep", all_files) == ["toplevel.py"]
    # basename fallback for absolute
    assert r([(0, "other")], "pkg", all_files) == ["other.py"]
    # unresolvable -> dropped, never raises
    assert r([(0, "nope.missing")], "pkg", all_files) == []


def test_from_package_import_submodule():
    """`from pkg import sub` must resolve to pkg/sub.py (both files load)."""
    import ast
    src = "from dna.analysis import plan\n"
    v = python_parser._Visitor()
    v.visit(ast.parse(src))
    assert (0, "dna.analysis") in v.imports
    assert (0, "dna.analysis.plan") in v.imports
    all_files = {"dna/analysis/__init__.py", "dna/analysis/plan.py"}
    got = python_parser._resolve_local(v.imports, "dna", all_files)
    assert "dna/analysis/__init__.py" in got
    assert "dna/analysis/plan.py" in got
