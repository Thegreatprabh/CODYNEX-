"""Git miner tests: fake git log via monkeypatched subprocess."""
from dna.ingest import git_miner

FAKE_LOG = (
    "a1b2c3d4\x1f2026-01-01\x1ffeat: add checkout flow\n"
    "\n"
    "service.py\n"
    "models.py\n"
    "b2c3d4e5\x1f2026-01-02\x1ffix: refund rounding bug\n"
    "\n"
    "service.py\n"
    "c3d4e5f6\x1f2026-01-03\x1frefactor: split utils\n"
    "\n"
    "utils.py\n"
    "d4e5f6a7\x1f2026-01-04\x1fupdate readme\n"
    "\n"
    "README.md\n"
)


class FakeProc:
    def __init__(self, stdout, rc=0):
        self.stdout = stdout
        self.returncode = rc


def _fake_run_factory(log_stdout):
    def fake_run(cmd, **kwargs):
        if "rev-parse" in cmd:
            return FakeProc("")
        if "log" in cmd:
            return FakeProc(log_stdout)
        return FakeProc("", rc=1)
    return fake_run


def test_mines_decisions_and_bugs(monkeypatch):
    monkeypatch.setattr(git_miner.subprocess, "run",
                        _fake_run_factory(FAKE_LOG))
    facts = git_miner.mine("/fake/path")
    assert facts.is_repo
    assert facts.commit_count == 4
    assert len(facts.decisions) == 2  # feat + refactor
    assert facts.decisions[0].message == "feat: add checkout flow"
    assert facts.decisions[0].files == ["service.py", "models.py"]
    assert len(facts.bug_history) == 1
    assert facts.bug_history[0].message == "fix: refund rounding bug"
    # "update readme" is neither
    assert facts.hotspots["service.py"] == 2
    assert facts.hotspots["utils.py"] == 1


def test_not_a_repo(monkeypatch):
    def fake_run(cmd, **kwargs):
        return FakeProc("", rc=128)
    monkeypatch.setattr(git_miner.subprocess, "run", fake_run)
    facts = git_miner.mine("/fake/path")
    assert not facts.is_repo
    assert facts.decisions == []
    assert facts.commit_count == 0


def test_git_missing(monkeypatch):
    def boom(cmd, **kwargs):
        raise OSError("no git")
    monkeypatch.setattr(git_miner.subprocess, "run", boom)
    facts = git_miner.mine("/fake/path")
    assert not facts.is_repo  # degrades gracefully
