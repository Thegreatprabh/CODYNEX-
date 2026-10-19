<div align="center">

# 🧬 CODYNEX Engine

![Typing SVG](https://readme-typing-svg.demolab.com?font=Fira+Code&size=20&pause=1000&color=00E5A0&center=true&vCenter=true&width=600&lines=Your+codebase+has+a+genome;Map+every+dependency+in+seconds;Predict+what+breaks+before+you+touch+it.)

[![Tests](https://img.shields.io/badge/tests-56_passing-00e5a0.svg)](#-verify-it-yourself)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Dependencies](https://img.shields.io/badge/dependencies-zero-00e5ff.svg)](pyproject.toml)
[![Version](https://img.shields.io/badge/version-0.2.0-b366ff.svg)](pyproject.toml)

🧬 **CODYNEX Engine** — codebase intelligence: an engine that reads your entire
project and builds a structured model of it — architecture, dependency graph,
design decisions, bug history. **Blast-radius prediction** — ask what breaks if
you touch `auth.py`, and get a ranked impact analysis. Apply a patch in an
isolated sandbox and see the test verdict before the change ever lands.

**Stdlib-only Python. Zero dependencies.**

</div>

## 🚀 Quickstart

```bash
git clone https://github.com/Thegreatprabh/codynex-engine.git
cd DNA
pip install -e .                 # stdlib only — nothing else to install

dna init ./my-project            # ingest → build the DNA
dna map                          # architecture: components + dependency stats
dna impact "auth.py"             # blast radius: what breaks if I change this?
dna plan "change the login system"  # predict a natural-language change
dna verify --patch fix.diff      # sandbox: apply patch, run tests, report
dna watch                        # keep the DNA updated as files change
```

The DNA is saved as JSON at `~/.dna/<project>/dna.json` (dir `0700`).
Run `dna watch` during development, or re-run `dna init` after big changes.

## 🧪 How it works — ingest → model → analyze → verify

```
 source code ──►  INGEST  ──►  MODEL  ──►  ANALYZE  ──►  VERIFY
  (.py files)     ast parse      ProjectDNA   blast radius    isolated
                  git log        dep graph    risk report     sandbox
                  mining         reverse      decisions       + pytest
                                 graph
```

1. **Ingest** — stdlib `ast` parses every Python file: imports (absolute
   `pkg.sub` and relative `.sib` resolved to real files), functions, classes,
   call edges. `git log` is mined for architectural decisions, bug history,
   and churn hotspots. An **intent extractor** records what each component
   is *for*: module docstring, README mentions, and the `test_*` names of
   tests importing it. No git? The graph still builds — history is skipped
   gracefully.
2. **Model** — a `ProjectDNA`: per-file components with one-line purpose
   summaries, a dependency graph **and its reverse graph**, decisions,
   hotspots, test coverage, and per-component intents. Persisted as JSON.
   `dna watch` keeps it live: it polls mtimes and re-parses only changed
   files, so the model never goes stale.
3. **Analyze** — `dna impact` runs reverse-BFS from your target over the
   dependency graph and scores every affected component. `dna plan` takes a
   natural-language change request, resolves it to components with a stated
   confidence, and returns the blast radius plus suggested tests. `dna risks`
   reports circular imports (Tarjan SCC), god-files, dead-code candidates,
   untested components. `dna decisions` lists design choices mined from
   commits.
4. **Verify** — `dna verify` copies the tree to a temp dir, applies your
   unified diff (context-verified — mismatched hunks are refused, new-file
   creation rejected), and runs the project's own test suite with a timeout.

## 💥 Blast-radius prediction

```console
$ dna impact "auth.py"

  target: auth.py  →  auth.py, session.py, api/routes.py
  affected components: 3

  RISK    SCORE DEPTH  COMPONENT
  ------------------------------------------
  high        5     1  session.py
            · no test coverage
            · churn hotspot
            · depth 1
  medium      3     2  api/routes.py
            · no test coverage
  low         1     1  auth.py
            · target itself

  ── 3 components · 1 high-risk ──
```

Risk scoring is explicit, not magic: no test coverage **+2**, circular
dependency **+2**, churn hotspot **+1**, depth > 3 **+1**. Labels: 0–1 low,
2–3 medium, 4+ high. Every score comes with its reasons printed.

```bash
dna impact checkout --limit 30    # fuzzy match — file, or even a function name
```

## 🧠 Change planning — predict before you change

```console
$ dna plan "change the login system"

  TARGET: auth.py  (confidence: high)
  request: change the login system
  affected components: 3

  RISK    SCORE DEPTH  COMPONENT
  ------------------------------------------
  high        5     1  session.py
            · no test coverage
            · churn hotspot
  medium      3     2  api/routes.py
            · no test coverage

  SUGGESTED TESTS:
    tests/test_session.py
    tests/test_routes.py

  RISK SUMMARY: high=1 medium=1 low=0
  HOTSPOTS IN BLAST:
    session.py (12 commits)
```

`dna plan` resolves your request to components (exact path/basename →
`high` confidence, fuzzy match → `medium`, keyword fallback → `low`),
reuses the blast-radius engine, and suggests the tests that cover the
affected code. Confidence is always shown — a `low` plan tells you the
match was a guess, not a fact.

## 🧫 Sandbox verification

```console
$ dna verify --patch fix.diff --path ./my-project

  verifying patch in sandbox (project: ./my-project) ...
  patched: auth.py
  tests: PASS — 42 passed, 0 failed in 1.8s
```

The patch is applied to a throwaway copy — your working tree is never
touched. Only verify projects you trust: the sandbox runs the project's
own test suite, so it inherits your trust in that code.

## 👁️ Live watcher — DNA that stays current

```console
$ dna watch --interval 2

  ingesting /home/you/my-project ...
  watching 38 files in /home/you/my-project (every 2s) — Ctrl+C to stop
  update #1: ~1 changed → DNA saved (38 files)
  update #2: ~1 changed, -1 deleted → DNA saved (37 files)
```

`dna watch` polls file mtimes (stdlib only — no watchdog dependency) and
re-parses **only the files that changed**, then rebuilds and re-saves the
DNA. New files, deleted files, and edits are all picked up; `Ctrl+C`
exits cleanly. The DNA stops being a snapshot and becomes a living model.

## 🤖 MCP — for AI agents

Four tools over stdio JSON-RPC. Malformed input returns `-32600`; the
server never crashes.

| Tool | Args | Returns |
|---|---|---|
| `dna_map` | — | Components, dependency stats |
| `dna_impact` | `{target}` | Ranked blast radius with reasons |
| `dna_plan` | `{request}` | Full change prediction + suggested tests |
| `dna_decisions` | `{limit}` | Decisions mined from git history |

```json
{ "project": { "command": "<FULL PYTHON PATH>", "args": ["-m", "dna", "mcp"] } }
```

> 📖 **Full per-agent setup guide:** [docs/SETUP_ALL_AGENTS.md](docs/SETUP_ALL_AGENTS.md) —
> Claude Code, Claude Desktop, Cursor, Codex, ChatGPT Desktop, Gemini CLI,
> Antigravity, Termux. (Golden rule: GUI apps need the **full** python path.)

## ⚠️ Risk report

```bash
dna risks
```

```
risk report: my-project (38 components, 112 edges)

circular imports: 1
  ↻ api/routes.py → db/session.py → api/routes.py

god-files (>500 lines): 2
  legacy/parser.py (812 lines)

dead-code candidates (no inbound, no tests): 3
  utils/old_helpers.py
```

## 🧱 Honest limits — v0.2.0

- **Python only.** Other languages are invisible to the parser.
- **Fuzzy target matching is heuristic.** Ambiguous names resolve to the
  first/best match; verify with `dna map` when unsure. `dna plan` always
  shows its confidence — treat `low` as a guess.
- **Call-graph resolution is best-effort.** Dynamic imports, `exec`,
  `getattr`-style dispatch, and method calls on unknown receivers are
  not tracked. The dependency graph is file-level (imports), which is
  robust; function-level edges are informational.
- **The sandbox runs the project's own test suite.** Only verify projects
  you trust — same trust level as running their tests locally.
- **Patch applier is minimal.** Unified diffs with new-file creation
  (`/dev/null` sources) are rejected; complex renames may fail — the
  tool refuses rather than mis-applying.
- **The watcher polls.** It checks mtimes on an interval (default 2s),
  so sub-second bursts of edits may batch into one update. It does not
  watch git history — commit, then re-mine decisions with `dna init`.
- **Intent is extracted, not understood.** Summaries come from docstrings,
  README mentions, and test names — useful signal, not deep comprehension.

## 🔍 Verify it yourself

```bash
python -m pytest tests/ -q    # 56 tests — should all pass
```

Tests are fully mocked — **zero network, zero real git**, under a second.
Every badge above is checkable in this repo.

## 🏗️ Architecture

```
                    ┌───────────────────────────┐
                    │        🧬 DNA CORE        │
                    │  ingest · model · analyze │
                    │        · verify           │
                    └──────────────┬────────────┘
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
     ┌────────────────┐  ┌─────────────────┐  ┌──────────────────┐
     │     INGEST     │  │      MODEL      │  │     ANALYZE      │
     │ ast parser     │  │ ProjectDNA      │  │ reverse-BFS      │
     │ import resolve │  │ dep + reverse   │  │ risk scoring     │
     │ git log miner  │  │ decisions       │  │ Tarjan cycles    │
     │ degrades w/o   │  │ hotspots        │  │ god-files        │
     │ git            │  │ JSON @ ~/.dna   │  │ dead code        │
     └────────────────┘  └─────────────────┘  └──────────────────┘
              └────────────────────┼────────────────────┘
                                   ▼
              ┌────────────────────────────────────────┐
              │              VERIFY + MCP              │
              │  temp-dir sandbox · context-verified   │
              │  patch applier · pytest · 3 MCP tools  │
              └────────────────────────────────────────┘
```

~2,000 lines of Python. No frameworks. No dependencies. The whole model
fits in one JSON file you can open and read.

## 🤝 Contributing

New analyzers are the best contribution:

1. Fork → branch → add your analyzer under `dna/analysis/`
2. Add a test in `tests/` (mocked — no network, no real git)
3. `pytest tests/ -q` must stay green
4. Open a PR explaining what it detects and why it matters

## 📄 License

MIT © 2026 Prabhjot Singh. Know your codebase's genome before you edit it. 🧬
