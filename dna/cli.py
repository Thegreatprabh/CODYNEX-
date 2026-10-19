"""DNA CLI: init / map / impact / risks / verify / decisions / watch / plan / mcp."""

import argparse
import os
import sys

from . import __version__
from .config import resolve_project
from .ingest import python_parser, git_miner
from .model import dna as dna_mod
from .model import store as store_mod
from .analysis import blast as blast_mod
from .analysis import risks as risks_mod
from .verify import sandbox as sandbox_mod


def _die(msg, code=1):
    print(f"dna: error: {msg}", file=sys.stderr)
    sys.exit(code)


def _load_or_die(project=None):
    slug, err = resolve_project(project)
    if err:
        _die(err)
    dna = store_mod.load(slug)
    if dna is None:
        _die(f"no saved DNA for project {slug!r} — run `dna init` first")
    return dna


# ---------- init ----------

def cmd_init(args):
    path = os.path.abspath(args.path or ".")
    if not os.path.isdir(path):
        _die(f"not a directory: {path}")
    slug = store_mod.slugify(args.name or os.path.basename(path))
    print(f"ingesting {path} ...")
    nodes = python_parser.parse_project(path)
    print(f"  parsed {len(nodes)} python files")
    facts = git_miner.mine(path)
    if facts.is_repo:
        print(f"  git: {facts.commit_count} commits, "
              f"{len(facts.decisions)} decisions, "
              f"{len(facts.bug_history)} bug-fixes")
    else:
        print("  git: not a repo — decisions/bug history unavailable")
    dna = dna_mod.build(slug, path, nodes, facts)
    saved = store_mod.save(dna)
    store_mod.mark_project(path, slug)
    n_err = len(dna.errors)
    print(f"DNA saved → {saved}")
    print(f"  components: {len(dna.components)}, "
          f"edges: {sum(len(v) for v in dna.dep_graph.values())}"
          + (f", parse errors: {n_err}" if n_err else ""))
    return 0


# ---------- map ----------

def cmd_map(args):
    dna = _load_or_die(args.project)
    print(f"project: {dna.project}  ({dna.root})")
    print(f"components: {len(dna.components)}   "
          f"edges: {sum(len(v) for v in dna.dep_graph.values())}   "
          f"commits: {dna.commit_count}")
    print()
    print(f"{'COMPONENT':<30} {'LINES':>6} {'IN':>4} {'OUT':>4} "
          f"{'TESTS':>6}  {'INTENT':<40}  PURPOSE")
    print("-" * 140)
    for p in sorted(dna.components):
        c = dna.components[p]
        tests = "yes" if c.has_tests else "no"
        intent = dna.intents.get(p, {}).get("summary", "")[:40]
        print(f"{p:<30} {c.lines:>6} {c.inbound:>4} {c.outbound:>4} "
              f"{tests:>6}  {intent:<40}  {c.purpose[:40]}")
    if dna.errors:
        print(f"\nparse errors: {len(dna.errors)} "
              f"(e.g. {dna.errors[0]['path']}: {dna.errors[0]['error'][:60]})")
    return 0


# ---------- impact ----------

def cmd_impact(args):
    dna = _load_or_die(args.project)
    try:
        resolved, affected = blast_mod.impact(dna, args.target)
    except ValueError as e:
        _die(str(e))
    print(f"target: {args.target}  →  {', '.join(resolved)}")
    print(f"affected components: {len(affected)}")
    print()
    if not affected:
        print("no dependents — safe to change in isolation.")
        return 0
    print(f"{'RISK':<7} {'SCORE':>5} {'DEPTH':>5}  COMPONENT")
    print("-" * 70)
    for n in affected[: args.limit]:
        print(f"{n.label:<7} {n.score:>5} {n.depth:>5}  {n.path}")
        for r in n.reasons:
            print(f"          · {r}")
    if len(affected) > args.limit:
        print(f"... and {len(affected) - args.limit} more")
    return 0


# ---------- risks ----------

def cmd_risks(args):
    dna = _load_or_die(args.project)
    rep = risks_mod.report(dna)
    print(f"risk report: {dna.project} "
          f"({rep['component_count']} components, {rep['edge_count']} edges)")
    print()
    print(f"circular imports: {len(rep['cycles'])}")
    for cyc in rep["cycles"][:5]:
        print(f"  ↻ {' → '.join(cyc)}")
    print(f"\ngod-files (>{risks_mod.GOD_FILE_LINES} lines): {len(rep['god_files'])}")
    for p, lines in rep["god_files"][:5]:
        print(f"  {p} ({lines} lines)")
    print(f"\ndead-code candidates (no inbound, no tests): "
          f"{len(rep['dead_code_candidates'])}")
    for p in rep["dead_code_candidates"][:8]:
        print(f"  {p}")
    print(f"\nuntested components: {len(rep['untested'])}")
    for p in rep["untested"][:8]:
        print(f"  {p}")
    print(f"\ntop churn hotspots:")
    for p, n in rep["hotspots"]:
        print(f"  {p} ({n} commits)")
    if not rep["hotspots"]:
        print("  (no git history)")
    return 0


# ---------- verify ----------

def cmd_verify(args):
    path = os.path.abspath(args.path or ".")
    try:
        with open(args.patch, "r", encoding="utf-8") as f:
            diff = f.read()
    except OSError as e:
        _die(f"cannot read patch: {e}")
    print(f"verifying patch in sandbox (project: {path}) ...")
    res = sandbox_mod.verify_patch(path, diff, timeout=args.timeout)
    if res.patch_error:
        _die(f"patch failed: {res.patch_error}")
    print(f"patched: {', '.join(res.files_patched)}")
    if not res.tests_ran:
        print(f"tests: could not run — {res.summary}")
        return 2
    status = "PASS" if res.passed else "FAIL"
    print(f"tests: {status} — {res.summary}")
    if res.timed_out:
        print("(timed out)")
    if not res.passed and res.output_tail:
        print("--- tail ---")
        print(res.output_tail)
    return 0 if res.passed else 1


# ---------- decisions ----------

def cmd_decisions(args):
    dna = _load_or_die(args.project)
    items = dna.decisions[: args.limit]
    print(f"decisions: {len(items)} shown / {len(dna.decisions)} mined")
    for d in items:
        files = f" [{len(d['files'])} files]" if d["files"] else ""
        print(f"  {d['date']} {d['sha']}  {d['message'][:72]}{files}")
    if not items:
        print("  (none — needs git history with feat/refactor-style messages)")
    return 0


# ---------- watch ----------

def cmd_watch(args):
    from . import watch as watch_mod
    if args.project:
        slug = store_mod.slugify(args.project)
    else:
        slug = store_mod.find_slug()
        if not slug:
            slug = store_mod.slugify(os.path.basename(os.getcwd()))
    dna = store_mod.load(slug)
    root = dna.root if dna else os.getcwd()
    watch_mod.watch_project(root, slug, interval=args.interval)
    return 0


# ---------- plan ----------

def cmd_plan(args):
    from .analysis import plan as plan_mod
    dna = _load_or_die(args.project)
    try:
        plan = plan_mod.plan_change(dna, args.request)
    except ValueError as e:
        _die(str(e))
    print(f"TARGET: {', '.join(plan.resolved)}  "
          f"(confidence: {plan.confidence})")
    print(f"request: {plan.target}")
    print(f"affected components: {len(plan.affected)}")
    print()
    if plan.affected:
        print(f"{'RISK':<7} {'SCORE':>5} {'DEPTH':>5}  COMPONENT")
        print("-" * 70)
        for n in plan.affected[:args.limit]:
            print(f"{n.label:<7} {n.score:>5} {n.depth:>5}  {n.path}")
            for r in n.reasons:
                print(f"          · {r}")
        if len(plan.affected) > args.limit:
            print(f"... and {len(plan.affected) - args.limit} more")
        print()
    print("SUGGESTED TESTS:")
    for t in plan.suggested_tests:
        print(f"  {t}")
    if not plan.suggested_tests:
        print("  (none found)")
    print()
    s = plan.risk_summary
    print(f"RISK SUMMARY: high={s.get('high', 0)} "
          f"medium={s.get('medium', 0)} low={s.get('low', 0)}")
    if plan.hotspots_in_blast:
        print("HOTSPOTS IN BLAST:")
        for p, n in plan.hotspots_in_blast:
            print(f"  {p} ({n} commits)")
    return 0


# ---------- mcp ----------

def cmd_mcp(args):
    from .mcp_server import serve
    serve()
    return 0

def build_parser():
    p = argparse.ArgumentParser(
        prog="dna",
        description=f"DNA v{__version__} — AI that understands the entire project.",
    )
    p.add_argument("--version", action="version", version=f"dna {__version__}")
    sub = p.add_subparsers(dest="cmd")

    pi = sub.add_parser("init", help="ingest a repo and build its DNA")
    pi.add_argument("path", nargs="?", default=".",
                    help="project root (default: cwd)")
    pi.add_argument("--name", help="project slug (default: dir name)")
    pi.set_defaults(fn=cmd_init)

    pm = sub.add_parser("map", help="show architecture")
    pm.add_argument("--project", help="project slug")
    pm.set_defaults(fn=cmd_map)

    pi2 = sub.add_parser("impact", help="predict blast radius of a change")
    pi2.add_argument("target", help="component name/path/export to change")
    pi2.add_argument("--project", help="project slug")
    pi2.add_argument("--limit", type=int, default=20)
    pi2.set_defaults(fn=cmd_impact)

    pr = sub.add_parser("risks", help="global structural risk report")
    pr.add_argument("--project", help="project slug")
    pr.set_defaults(fn=cmd_risks)

    pv = sub.add_parser("verify", help="apply a patch in sandbox and run tests")
    pv.add_argument("--patch", required=True, help="unified diff file")
    pv.add_argument("--path", default=".", help="project root (default: cwd)")
    pv.add_argument("--timeout", type=int, default=300)
    pv.set_defaults(fn=cmd_verify)

    pd = sub.add_parser("decisions", help="decisions mined from git history")
    pd.add_argument("--limit", type=int, default=10)
    pd.add_argument("--project", help="project slug")
    pd.set_defaults(fn=cmd_decisions)

    pw = sub.add_parser("watch", help="keep DNA updated as files change")
    pw.add_argument("--interval", type=float, default=2.0,
                    help="poll interval in seconds (default: 2)")
    pw.add_argument("--project", help="project slug")
    pw.set_defaults(fn=cmd_watch)

    pp = sub.add_parser("plan", help="predict a natural-language change")
    pp.add_argument("request", help="e.g. \"change the login system\"")
    pp.add_argument("--project", help="project slug")
    pp.add_argument("--limit", type=int, default=20)
    pp.set_defaults(fn=cmd_plan)

    pmcp = sub.add_parser("mcp", help="serve MCP over stdio")
    pmcp.set_defaults(fn=cmd_mcp)
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "cmd", None):
        parser.print_help()
        return 0
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
