#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Eval runner (decisions E1-E4): runs the skill on a cheap model and grades the transcripts.

Each run copies only the skill into a fresh temp workspace and drives Claude Code headless:
    claude -p --model <model> --setting-sources project --strict-mcp-config
so no user-level skills, plugins or MCP servers leak in. Multi-turn cases use --resume.
Grading is deterministic (see cases.json "about"). Results go to evals/runs/<stamp>-<model>/.

    uv run evals/run.py --model haiku --runs 1
    uv run evals/run.py --case 'q1-*' --runs 3
"""

import argparse
import fnmatch
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

EVALS = Path(__file__).resolve().parent
SKILL = EVALS.parent
sys.path.insert(0, str(SKILL / "scripts"))
from wiki_interest.narrative import unknown_numbers  # noqa: E402 - needs the path above

SKIP = ("tests", "docs", "evals", "__pycache__", ".ruff_cache", ".pytest_cache")
ALLOWED_TOOLS = ["Skill", "Read", "Write", "Edit", "Bash(uv run:*)"]
WIKI_CMD = re.compile(r"^\s*uv run\s.*?wiki\.py['\"]?\s+(\w+)")  # allows `uv run --quiet ...`
CHAINED = re.compile(r"&&|;|\|")
ADHOC = re.compile(r"\b(python3?|curl|wget|pip|node|requests|urllib)\b", re.IGNORECASE)
PATH = re.compile(r"\S*/\S+")
CYRILLIC, LATIN = re.compile(r"[Ѐ-ӿ]"), re.compile(r"[A-Za-z]")
TURN_TIMEOUT = 600


@dataclass(frozen=True)
class Config:
    model: str
    max_turns: int
    out_root: Path


# --- transcripts ----------------------------------------------------------------------


@dataclass
class Turn:
    prompt: str
    session_id: str = ""
    skill_invoked: bool = False
    commands: list[dict] = field(default_factory=list)  # wiki.py: cmd, sub, output, error
    violations: list[str] = field(default_factory=list)  # ad-hoc code attempts
    other_tools: list[str] = field(default_factory=list)
    answer: str = ""
    cost: float = 0.0
    turns: int = 0
    seconds: float = 0.0
    error: str = ""
    pending: dict[str, dict] = field(default_factory=dict, repr=False)

    def on_tool_use(self, block: dict) -> None:
        name, args = block["name"], block.get("input", {})
        if name == "Skill":
            self.skill_invoked |= args.get("skill") == "wiki-interest"
        elif name == "Bash":
            self._on_bash(block["id"], args.get("command", ""))
        elif name in {"Write", "Edit"}:
            path = args.get("file_path", "")
            if not path.endswith("narrative.md"):
                self.violations.append(f"{name}: {path}")
        else:
            self.other_tools.append(name)

    def _on_bash(self, tool_id: str, cmd: str) -> None:
        match = WIKI_CMD.match(cmd)
        if match and not CHAINED.search(cmd):
            entry = {"cmd": cmd, "sub": match.group(1), "output": "", "error": False}
            self.commands.append(entry)
            self.pending[tool_id] = entry
        elif ADHOC.search(cmd):
            self.violations.append(f"Bash: {cmd[:160]}")
        else:
            self.other_tools.append(f"Bash: {cmd[:120]}")

    def on_tool_result(self, block: dict) -> None:
        entry = self.pending.get(block.get("tool_use_id", ""))
        if entry is not None:
            entry["output"] = _text(block.get("content"))
            entry["error"] = bool(block.get("is_error"))


def _text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
    return ""


def _events(lines: list[str]) -> list[dict]:
    events = []
    for line in lines:
        try:
            events.append(json.loads(line))
        except ValueError:
            continue
    return events


def parse(lines: list[str], prompt: str) -> Turn:
    """Read a Claude Code stream-json transcript into a Turn."""
    turn = Turn(prompt)
    for event in _events(lines):
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            turn.session_id = event.get("session_id", "")
        elif kind == "assistant":
            for block in event["message"]["content"]:
                if block.get("type") == "tool_use":
                    turn.on_tool_use(block)
        elif kind == "user":
            for block in event["message"]["content"]:
                if isinstance(block, dict):
                    turn.on_tool_result(block)
        elif kind == "result":
            turn.answer = event.get("result", "") or ""
            turn.cost = event.get("total_cost_usd") or 0.0
            turn.turns = event.get("num_turns") or 0
            turn.session_id = event.get("session_id", turn.session_id)
    return turn


# --- running --------------------------------------------------------------------------


def workspace() -> Path:
    ws = Path(tempfile.mkdtemp(prefix="wiki-eval-"))
    target = ws / ".claude" / "skills" / "wiki-interest"
    shutil.copytree(SKILL, target, ignore=shutil.ignore_patterns(*SKIP))
    subprocess.run(["git", "init", "-q"], cwd=ws, check=True)
    return ws


def run_turn(ws: Path, prompt: str, session: str, log: Path, config: Config) -> Turn:
    cmd = ["claude", "-p", prompt, "--model", config.model, "--max-turns", str(config.max_turns)]
    cmd += ["--setting-sources", "project", "--strict-mcp-config"]
    cmd += ["--allowedTools", *ALLOWED_TOOLS, "--output-format", "stream-json", "--verbose"]
    if session:
        cmd += ["--resume", session]
    start = time.monotonic()
    try:
        done = subprocess.run(
            cmd, cwd=ws, capture_output=True, text=True, stdin=subprocess.DEVNULL,
            timeout=TURN_TIMEOUT, check=False,
        )  # fmt: skip
        output, error = done.stdout, done.stderr[-2000:] if done.returncode else ""
    except subprocess.TimeoutExpired as exc:
        raw = exc.stdout or ""
        output = raw if isinstance(raw, str) else raw.decode()
        error = f"timeout after {TURN_TIMEOUT}s"
    log.write_text(output, encoding="utf-8")
    turn = parse(output.splitlines(), prompt)
    turn.seconds = round(time.monotonic() - start, 1)
    turn.error = error
    return turn


def keep_artifacts(ws: Path, out: Path) -> list[str]:
    kept = []
    for run in sorted((ws / "wiki-interest-runs").glob("*")):
        for name in ("analysis.json", "summary.txt", "narrative.md", "report.pdf"):
            if (run / name).exists():
                target = out / "artifacts" / run.name / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(run / name, target)
                kept.append(str(target.relative_to(out)))
    return kept


# --- grading --------------------------------------------------------------------------


class Grades(list):
    def add(self, name: str, *, passed: bool, evidence: str) -> None:
        self.append({"check": name, "passed": bool(passed), "evidence": evidence})


def _script(text: str) -> str:
    cyrillic, latin = len(CYRILLIC.findall(text)), len(LATIN.findall(text))
    return "uk" if cyrillic > latin else "en"


def _grade_commands(grades: Grades, turn: Turn, checks: dict) -> None:
    subs = [c["sub"] for c in turn.commands]
    cmds = [c["cmd"] for c in turn.commands]
    if "skill" in checks:
        used = turn.skill_invoked or bool(turn.commands)
        grades.add(
            f"skill {'used' if checks['skill'] else 'not used'}",
            passed=used == checks["skill"],
            evidence=f"Skill tool: {turn.skill_invoked}; wiki.py commands: {subs}",
        )
    if "commands" in checks:
        remaining = iter(subs)
        in_order = all(any(s == want for s in remaining) for want in checks["commands"])
        grades.add(
            f"runs {' -> '.join(checks['commands'])}", passed=in_order, evidence=f"ran: {subs}"
        )
    for pattern in checks.get("command_regex", []):
        hit = next((c for c in cmds if re.search(pattern, c)), None)
        grades.add(
            f"a command matches /{pattern}/", passed=hit is not None, evidence=hit or str(cmds)
        )
    for pattern in checks.get("no_command_regex", []):
        hit = next((c for c in cmds if re.search(pattern, c)), None)
        grades.add(f"no command matches /{pattern}/", passed=hit is None, evidence=hit or "none")
    if checks.get("report"):
        saved = [
            c for c in turn.commands if c["sub"] == "report" and "Report saved:" in c["output"]
        ]
        grades.add(
            "PDF report produced",
            passed=bool(saved),
            evidence=saved[-1]["output"][:160] if saved else "no successful report",
        )


def _grade_answer(grades: Grades, turn: Turn, checks: dict, history: list[Turn]) -> None:
    for pattern in checks.get("answer_regex", []):
        found = re.search(pattern, turn.answer, re.IGNORECASE)
        evidence = found.group() if found else turn.answer[:200]
        grades.add(f"answer matches /{pattern}/", passed=found is not None, evidence=evidence)
    if "language" in checks:
        script = _script(turn.answer)
        grades.add(
            f"answer in {checks['language']}",
            passed=script == checks["language"],
            evidence=f"script looks like {script}",
        )
    if any(t.commands for t in history):
        # Failed commands don't count: report's rejection quotes the very numbers it rejected.
        shown = "\n".join(c["output"] for t in history for c in t.commands if not c["error"])
        shown += "\n" + "\n".join(t.prompt for t in history)
        unknown = unknown_numbers(PATH.sub(" ", turn.answer), shown)  # paths carry run ids
        grades.add(
            "answer numbers were printed by the tools",
            passed=not unknown,
            evidence="; ".join(unknown[:5]) or "all grounded",
        )


def _grade_paths(grades: Grades, turn: Turn, paths: list[dict], history: list[Turn]) -> None:
    """Pass if any one acceptable path passes all its checks (e.g. two correct ways to answer)."""
    outcomes = []
    for path in paths:
        sub = Grades()
        _grade_commands(sub, turn, path)
        _grade_answer(sub, turn, path, history)
        outcomes.append((path.get("name", "path"), [g for g in sub if not g["passed"]]))
    ok = next((name for name, failed in outcomes if not failed), None)
    evidence = ok or " | ".join(
        f"{name}: " + "; ".join(g["check"] for g in failed) for name, failed in outcomes
    )
    grades.add(f"one of {len(paths)} acceptable paths", passed=ok is not None, evidence=evidence)


def grade(turn: Turn, checks: dict, history: list[Turn]) -> list[dict]:
    """One {"check", "passed", "evidence"} per check; the fixed checks always run."""
    grades = Grades()
    if turn.error:
        grades.add("turn completed", passed=False, evidence=turn.error[:300])
    _grade_commands(grades, turn, checks)
    _grade_answer(grades, turn, checks, history)
    if "any_of" in checks:
        _grade_paths(grades, turn, checks["any_of"], history)
    grades.add(
        "no ad-hoc code", passed=not turn.violations, evidence="; ".join(turn.violations) or "none"
    )
    return list(grades)


# --- orchestration --------------------------------------------------------------------


def run_case(case: dict, index: int, config: Config) -> dict:
    out = config.out_root / case["id"] / f"run-{index}"
    out.mkdir(parents=True, exist_ok=True)
    ws = workspace()
    history: list[Turn] = []
    graded = []
    session = ""
    for k, spec in enumerate(case["turns"], 1):
        turn = run_turn(ws, spec["prompt"], session, out / f"turn-{k}.jsonl", config)
        session = turn.session_id or session
        history.append(turn)
        graded.append({"turn": k, "checks": grade(turn, spec.get("checks", {}), history)})
    artifacts = keep_artifacts(ws, out)
    shutil.rmtree(ws, ignore_errors=True)
    record = {
        "case": case["id"],
        "run": index,
        "passed": all(c["passed"] for g in graded for c in g["checks"]),
        "cost": round(sum(t.cost for t in history), 4),
        "turns": sum(t.turns for t in history),
        "seconds": round(sum(t.seconds for t in history), 1),
        "graded": graded,
        "artifacts": artifacts,
        "transcript": [{k: v for k, v in asdict(t).items() if k != "pending"} for t in history],
    }
    text = json.dumps(record, ensure_ascii=False, indent=2)
    (out / "result.json").write_text(text, encoding="utf-8")
    return record


def safe_run(case: dict, index: int, config: Config) -> dict:
    """A crash in one case becomes a failed record instead of aborting the whole eval."""
    try:
        return run_case(case, index, config)
    except Exception as error:  # noqa: BLE001 - report it with the other results
        check = {
            "check": "case ran",
            "passed": False,
            "evidence": f"{type(error).__name__}: {error}",
        }
        return {
            "case": case["id"],
            "run": index,
            "passed": False,
            "cost": 0.0,
            "turns": 0,
            "seconds": 0.0,
            "graded": [{"turn": 0, "checks": [check]}],
            "artifacts": [],
        }


def summarize(records: list[dict], model: str) -> str:
    lines = [f"# Eval results: {model}", ""]
    lines += ["| Case | Run | Pass | Failed checks | Cost | Turns | Time |"]
    lines += ["|---|---|---|---|---|---|---|"]
    for r in sorted(records, key=lambda r: (r["case"], r["run"])):
        failed = [
            f"t{g['turn']}: {c['check']} ({c['evidence'][:80]})"
            for g in r["graded"]
            for c in g["checks"]
            if not c["passed"]
        ]
        lines.append(
            f"| {r['case']} | {r['run']} | {'yes' if r['passed'] else 'NO'} | "
            f"{'<br>'.join(failed) or '-'} | ${r['cost']:.3f} | {r['turns']} | {r['seconds']}s |"
        )
    cases = sorted({r["case"] for r in records})
    per_case = ", ".join(
        f"{c} {sum(r['passed'] for r in records if r['case'] == c)}"
        f"/{sum(1 for r in records if r['case'] == c)}"
        for c in cases
    )
    total = sum(r["passed"] for r in records)
    cost = sum(r["cost"] for r in records)
    lines += ["", f"Passed {total}/{len(records)} runs ({per_case}); total cost ${cost:.2f}."]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default="haiku")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--case", default="*", help="glob on case ids")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--max-turns", type=int, default=15)
    args = parser.parse_args()
    if not shutil.which("claude"):
        print("Error: the claude CLI is not on PATH.", file=sys.stderr)
        return 2
    all_cases = json.loads((EVALS / "cases.json").read_text(encoding="utf-8"))["cases"]
    cases = [c for c in all_cases if fnmatch.fnmatch(c["id"], args.case)]
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    config = Config(args.model, args.max_turns, EVALS / "runs" / f"{stamp}-{args.model}")
    jobs = [(c, i) for c in cases for i in range(1, args.runs + 1)]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        records = list(pool.map(lambda job: safe_run(*job, config), jobs))
    report = summarize(records, args.model)
    (config.out_root / "summary.md").write_text(report + "\n", encoding="utf-8")
    print(report)
    print(f"\nSaved: {config.out_root}")
    return 0 if all(r["passed"] for r in records) else 1


if __name__ == "__main__":
    sys.exit(main())
