"""Intended-behaviour model: what each component is FOR (not what it does).

Sources, in order of trust:
  1. Module docstring (first line) -> primary intent summary.
  2. Project README (README.md / README.txt / README.rst at root): a line
     mentioning the component's basename/stem -> readme_note (<=200 chars).
  3. Test files importing the component: their `def test_*` names ->
     tested_behaviours (<=5), i.e. behaviours the author bothered to pin.
"""

import ast
import os
import re

README_NAMES = ("README.md", "README.txt", "README.rst")
MAX_README_NOTE = 200
MAX_BEHAVIOURS = 5


def _is_test_file(path):
    return re.search(r"(^|[/_])test", os.path.basename(path)) is not None


def _readme_text(root):
    for name in README_NAMES:
        p = os.path.join(root, name)
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8", errors="replace") as f:
                    return f.read()
            except OSError:
                return ""
    return ""


def _readme_note(readme, path):
    """First README line mentioning the component's stem/basename (<=200 chars)."""
    stem = os.path.splitext(os.path.basename(path))[0].lower()
    base = os.path.basename(path).lower()
    for line in readme.splitlines():
        low = line.lower()
        if stem and stem in low or base in low:
            note = " ".join(line.split())  # collapse whitespace
            return note[:MAX_README_NOTE]
    return ""


def _test_names(abs_path):
    """Names of `def test_*` functions in a test file (best effort)."""
    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            tree = ast.parse(f.read(), filename=abs_path)
    except (OSError, SyntaxError):
        return []
    names = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name.startswith("test_"):
            names.append(node.name)
    return names


def extract_intent(root, nodes):
    """Build {path: intent-dict} for every parsed node.

    intent-dict: {"summary": str, "readme_note": str,
                  "tested_behaviours": [str, ...]}
    """
    readme = _readme_text(root)
    by_path = {n.path: n for n in nodes}

    # map component -> test files importing it
    importers = {}
    for n in nodes:
        if n.error or not _is_test_file(n.path):
            continue
        for dep in n.local_imports:
            importers.setdefault(dep, []).append(n.path)

    intents = {}
    for n in nodes:
        if n.error:
            continue
        behaviours = []
        for t in importers.get(n.path, []):
            behaviours.extend(
                _test_names(os.path.join(root, t)))
        # dedupe, preserve order, cap
        seen, uniq = set(), []
        for b in behaviours:
            if b not in seen:
                seen.add(b)
                uniq.append(b)
        intents[n.path] = {
            "summary": (n.module_doc or "").strip(),
            "readme_note": _readme_note(readme, n.path),
            "tested_behaviours": uniq[:MAX_BEHAVIOURS],
        }
    return intents
