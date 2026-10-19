"""Git history miner: decisions, bug history, churn hotspots.

Parses `git log` via subprocess. Degrades gracefully when the path
is not a git repo (returns empty facts, never raises).

Decisions: significant commits — messages starting with feat/refactor/
arch/docs/design (conventional-ish, heuristic).
Bug history: commits matching fix|bug|hotfix|patch|regression.
Hotspots: files ranked by commit-churn count.
"""

import re
import subprocess
from dataclasses import dataclass, field


@dataclass
class Decision:
    sha: str
    date: str
    message: str
    files: list = field(default_factory=list)


@dataclass
class BugFix:
    sha: str
    date: str
    message: str
    files: list = field(default_factory=list)


@dataclass
class GitFacts:
    decisions: list = field(default_factory=list)   # Decision
    bug_history: list = field(default_factory=list)  # BugFix
    hotspots: dict = field(default_factory=dict)     # file -> commit count
    is_repo: bool = False
    commit_count: int = 0


_DECISION_RE = re.compile(r"^(feat|refactor|arch|design|docs|perf)(\(.+\))?[:\s]", re.I)
_BUG_RE = re.compile(r"\b(fix|bug|hotfix|patch|regression|broken|crash)\b", re.I)

# Unit separator based log format: sha \x1f date \x1f subject \x1e files...
_LOG_FORMAT = "%H\x1f%ad\x1f%s"


def _run_git(path, *args, timeout=30):
    """Run git, return (ok, stdout). Never raises."""
    try:
        proc = subprocess.run(
            ["git", "-C", path, *args],
            capture_output=True, text=True, timeout=timeout,
        )
        return proc.returncode == 0, proc.stdout
    except (OSError, subprocess.SubprocessError):
        return False, ""


def mine(path, max_commits=500):
    """Mine git history at path. Returns GitFacts (empty if not a repo)."""
    facts = GitFacts()
    ok, _ = _run_git(path, "rev-parse", "--is-inside-work-tree")
    if not ok:
        return facts
    facts.is_repo = True

    ok, out = _run_git(
        path, "log", f"--max-count={max_commits}",
        f"--pretty=format:{_LOG_FORMAT}", "--date=short", "--name-only",
    )
    if not ok or not out.strip():
        return facts

    # entries: header line (with \x1f separators) followed by file lines.
    # Classify AFTER the entry is complete (files come after the header).
    def flush(current):
        if not current:
            return
        for f in current["files"]:
            facts.hotspots[f] = facts.hotspots.get(f, 0) + 1
        msg = current["subject"]
        if _DECISION_RE.match(msg):
            facts.decisions.append(Decision(
                sha=current["sha"], date=current["date"],
                message=msg, files=list(current["files"])))
        elif _BUG_RE.search(msg):
            facts.bug_history.append(BugFix(
                sha=current["sha"], date=current["date"],
                message=msg, files=list(current["files"])))

    current = None
    for line in out.split("\n"):
        if "\x1f" in line:
            flush(current)
            sha, date, subject = line.split("\x1f", 2)
            facts.commit_count += 1
            current = {"sha": sha[:8], "date": date,
                       "subject": subject.strip(), "files": []}
        elif line.strip() and current is not None:
            current["files"].append(line.strip())
    flush(current)
    return facts
