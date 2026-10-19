"""Sandbox verification: apply a patch in an isolated copy and run tests.

  1. Copy the project tree to a temp dir (skipping .git, __pycache__,
     .venv/venv, node_modules, .tox, build, dist).
  2. Apply a unified-diff patch (minimal stdlib parser).
  3. Run `python -m pytest -q` with a timeout; capture pass/fail + summary.

Safety note: this RUNS the project's own test suite. Only verify
projects you trust — same trust level as running their tests locally.

Returns a VerifyResult dataclass. apply_patch returns (files, error)
and never raises on bad input.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field

SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules",
             ".tox", ".eggs", "build", "dist", ".mypy_cache", ".dna"}

DEFAULT_TIMEOUT = 300


@dataclass
class VerifyResult:
    applied: bool = False
    files_patched: list = field(default_factory=list)
    patch_error: str = ""
    tests_ran: bool = False
    passed: bool = False
    passed_count: int = 0
    failed_count: int = 0
    error_count: int = 0
    summary: str = ""
    output_tail: str = ""
    timed_out: bool = False


# ---------- unified diff parser ----------

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def _strip_prefix(path):
    for prefix in ("a/", "b/"):
        if path.startswith(prefix):
            return path[len(prefix):]
    return path


def parse_diff(text):
    """Parse unified diff → list of (path, hunks).

    Each hunk is (old_start_1based, old_block, new_block) where old_block
    is the expected original content (context + deletions) and new_block
    is the replacement (context + additions). Raises ValueError on
    malformed diff.
    """
    files = []
    cur_path, cur_hunks = None, None
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("--- "):
            if i + 1 >= len(lines) or not lines[i + 1].startswith("+++ "):
                raise ValueError("diff missing +++ line after ---")
            new_path = _strip_prefix(lines[i + 1][4:].strip().split("\t")[0])
            if new_path == "/dev/null":
                raise ValueError("new-file creation diffs not supported in v0.1.0")
            if cur_path is not None:
                files.append((cur_path, cur_hunks))
            cur_path, cur_hunks = new_path, []
            i += 2
            continue
        m = _HUNK_RE.match(line)
        if m and cur_path is not None:
            old_start = int(m.group(1))
            old_block, new_block = [], []
            i += 1
            while i < len(lines):
                hunk_line = lines[i]
                if hunk_line.startswith("--- ") or _HUNK_RE.match(hunk_line):
                    break
                if not hunk_line or hunk_line[0] not in (" ", "-", "+",
                                                         "\\"):
                    break
                if hunk_line.startswith("\\"):
                    i += 1  # "\ No newline at end of file" marker
                    continue
                marker, content = hunk_line[0], hunk_line[1:]
                if marker == " ":
                    old_block.append(content)
                    new_block.append(content)
                elif marker == "-":
                    old_block.append(content)
                else:  # "+"
                    new_block.append(content)
                i += 1
            cur_hunks.append((old_start, old_block, new_block))
            continue
        i += 1
    if cur_path is not None:
        files.append((cur_path, cur_hunks))
    if not files:
        raise ValueError("no file hunks found in diff")
    for path, hunks in files:
        if not hunks:
            raise ValueError(f"no hunks for file {path}")
    return files


def apply_patch(root, diff_text):
    """Apply a unified diff to files under root.

    Returns (patched_files, error). Each hunk's old block is verified
    against the file before splicing; hunks apply bottom-up. Never
    raises on bad input.
    """
    try:
        files = parse_diff(diff_text)
    except ValueError as e:
        return [], f"patch parse error: {e}"
    patched = []
    for rel_path, hunks in files:
        abs_path = os.path.join(root, rel_path)
        if not os.path.isfile(abs_path):
            return [], f"patch target not found: {rel_path}"
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                src = f.read().split("\n")
        except OSError as e:
            return [], f"cannot read {rel_path}: {e}"
        # bottom-up so earlier hunk positions stay valid
        for old_start, old_block, new_block in sorted(hunks, reverse=True):
            idx = old_start - 1
            if idx < 0 or idx + len(old_block) > len(src):
                return [], (f"hunk out of range in {rel_path} "
                            f"(start={old_start})")
            actual = src[idx:idx + len(old_block)]
            if actual != old_block:
                return [], (f"hunk context mismatch in {rel_path} "
                            f"at line {old_start}")
            src[idx:idx + len(old_block)] = new_block
        try:
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write("\n".join(src))
        except OSError as e:
            return [], f"cannot write {rel_path}: {e}"
        patched.append(rel_path)
    return patched, ""


# ---------- sandbox ----------

def _copy_tree(src, dst):
    """Copy project tree, skipping junk dirs."""
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        rel = os.path.relpath(dirpath, src)
        target_dir = os.path.join(dst, rel) if rel != "." else dst
        os.makedirs(target_dir, exist_ok=True)
        for fn in filenames:
            shutil.copy2(os.path.join(dirpath, fn),
                         os.path.join(target_dir, fn))


_SUMMARY_RE = re.compile(
    r"(?P<passed>\d+) passed|(?P<failed>\d+) failed|(?P<error>\d+) error",
)


def _parse_pytest_summary(output):
    """Extract counts from pytest's final summary line."""
    passed = failed = errors = 0
    for line in output.split("\n"):
        if "passed" in line or "failed" in line or "error" in line:
            for m in _SUMMARY_RE.finditer(line):
                if m.group("passed"):
                    passed = int(m.group("passed"))
                elif m.group("failed"):
                    failed = int(m.group("failed"))
                elif m.group("error"):
                    errors = int(m.group("error"))
    return passed, failed, errors


def verify_patch(project_root, diff_text, timeout=DEFAULT_TIMEOUT,
                 python=None):
    """Copy project → apply patch → run pytest. Returns VerifyResult."""
    result = VerifyResult()
    python = python or sys.executable
    tmp = tempfile.mkdtemp(prefix="dna-verify-")
    try:
        _copy_tree(project_root, tmp)
        patched, err = apply_patch(tmp, diff_text)
        if err:
            result.patch_error = err
            return result
        result.applied = True
        result.files_patched = patched

        try:
            proc = subprocess.run(
                [python, "-m", "pytest", "-q"],
                cwd=tmp, capture_output=True, text=True, timeout=timeout,
            )
            timed_out = False
        except subprocess.TimeoutExpired as e:
            result.timed_out = True
            result.tests_ran = True
            out = (e.stdout or "") + (e.stderr or "")
            if isinstance(out, bytes):
                out = out.decode("utf-8", "replace")
            result.output_tail = "\n".join(out.split("\n")[-30:])
            result.summary = f"timed out after {timeout}s"
            return result
        except OSError as e:
            result.summary = f"could not run pytest: {e}"
            return result

        out = proc.stdout + proc.stderr
        result.tests_ran = True
        result.output_tail = "\n".join(out.split("\n")[-30:])
        p, f, e = _parse_pytest_summary(out)
        result.passed_count, result.failed_count, result.error_count = p, f, e
        result.passed = (proc.returncode == 0)
        if result.passed:
            result.summary = f"{p} passed"
        else:
            result.summary = (f"{p} passed, {f} failed, {e} errors "
                              f"(exit {proc.returncode})")
        return result
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
