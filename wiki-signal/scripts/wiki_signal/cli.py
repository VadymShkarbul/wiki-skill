"""Command-line interface: resolve -> analyze -> report (decision I1).

Every failure ends with ``Error:`` and ``Next:`` lines, never a traceback (decision E0).
"""

import argparse
import shlex
import sys
import traceback
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

from wiki_signal import __version__
from wiki_signal.analysis import DEFAULT_MONTHS, SORT_KEYS, run_analysis
from wiki_signal.cache import Cache, default_cache_dir
from wiki_signal.editions import Catalog, load_catalog
from wiki_signal.errors import SkillError
from wiki_signal.http_client import HttpClient
from wiki_signal.i18n import languages
from wiki_signal.output import RUNS_DIR, save
from wiki_signal.report import render
from wiki_signal.resolve import MAX_CANDIDATES, find_candidates, format_candidates

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_USAGE = 2
EXIT_INTERRUPTED = 130
PROG = "wiki.py"
SCRIPT = Path(__file__).resolve().parents[1] / "wiki.py"


def command_prefix() -> str:
    """The exact command the agent should copy into Next lines: absolute path, no cd."""
    return f"uv run {shlex.quote(str(SCRIPT))}"


def make_client() -> HttpClient:
    return HttpClient(Cache(default_cache_dir()))


def _print_error(message: str, next_step: str) -> None:
    print(f"Error: {message}\nNext: {next_step}", file=sys.stderr)


class _Parser(argparse.ArgumentParser):
    """Reports bad arguments in the same Error/Next shape as every other failure."""

    def error(self, message: str) -> NoReturn:
        _print_error(message, f"Run `{self.prog} --help` and fix the command.")
        sys.exit(EXIT_USAGE)


def _recover_topic(args: argparse.Namespace, catalog: Catalog) -> None:
    """`resolve --editions pl,cs astronomy`: --editions takes several words, so it swallowed
    the topic. Take back the trailing words that are not editions."""
    if args.topic:
        return
    words = args.editions
    while words and not catalog.is_edition(words[-1]):
        args.topic = f"{words.pop()} {args.topic or ''}".strip()
    if not args.topic:
        raise SkillError(
            "No topic given.",
            'Run: resolve "<topic>" --editions <codes>, e.g. resolve "astronomy" --editions uk',
        )


def _resolve(args: argparse.Namespace) -> int:
    client = make_client()
    catalog = load_catalog(client)
    _recover_topic(args, catalog)
    editions = catalog.parse(",".join(args.editions))
    concepts = find_candidates(
        client, catalog, args.topic, editions, search_lang=args.search_lang, limit=args.limit
    )
    print(format_candidates(args.topic, editions, concepts, command_prefix()))
    return EXIT_OK


def _analyze(args: argparse.Namespace) -> int:
    client = make_client()
    catalog = load_catalog(client)
    editions = catalog.parse(",".join(args.editions))
    analysis = run_analysis(
        client,
        catalog,
        args.concepts,
        editions,
        months=args.months,
        proxies=args.proxy,
        sort=args.sort,
    )
    _, summary = save(analysis, Path(args.out), command_prefix())
    print(summary)
    return EXIT_OK


def _numbers(text: str) -> list[float]:
    try:
        return [float(t.replace("%", "")) for t in text.split(",") if t.strip()]
    except ValueError as error:
        msg = f"--user-numbers must be comma-separated numbers, got {text!r}"
        raise argparse.ArgumentTypeError(msg) from error


def _report(args: argparse.Namespace) -> int:
    run_dir = Path(args.run).resolve()
    pdf = render(run_dir, args.lang, args.user_numbers)
    print(
        f"Report saved: {pdf} (1 page, labels in {args.lang})\n"
        "Checks passed: every number in narrative.md was shown by analyze; the text fits one "
        "page.\n"
        "Next: give the user the PDF path. To change the wording, edit "
        f"{run_dir / 'narrative.md'} and re-run: {command_prefix()} report --run "
        f"{shlex.quote(str(run_dir))} --lang {args.lang}"
    )
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog=PROG, description="Wikipedia pageview interest analysis.")
    parser.add_argument("--version", action="version", version=f"wiki-signal {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)

    resolve = sub.add_parser(
        "resolve",
        help="Find Wikidata concepts for a topic and their article in each edition.",
    )
    resolve.add_argument(
        "topic",
        nargs="?",
        help="Topic in words, a QID (Q333), lang:Title (pl:Astronomia), or an article URL.",
    )
    resolve.add_argument("--editions", required=True, nargs="+", help="Edition codes, e.g. pl,cs.")
    resolve.add_argument(
        "--search-lang", default="en", help="Language the topic is written in (default: en)."
    )
    resolve.add_argument(
        "--limit",
        type=int,
        default=3,
        choices=range(1, MAX_CANDIDATES + 1),
        metavar=f"1-{MAX_CANDIDATES}",
        help="How many candidates to show (default: 3).",
    )
    resolve.set_defaults(handler=_resolve)

    analyze = sub.add_parser("analyze", help="Fetch pageviews and compute verdicts and charts.")
    analyze.add_argument(
        "--concepts",
        nargs="+",
        required=True,
        help="Wikidata IDs from resolve (Q1666254), or lang:Title. Several = one broad topic.",
    )
    analyze.add_argument("--editions", required=True, nargs="+", help="Edition codes, e.g. pl,cs.")
    analyze.add_argument(
        "--months", type=int, default=DEFAULT_MONTHS, help="Trend window in months (default 24)."
    )
    analyze.add_argument(
        "--proxy",
        action="append",
        default=[],
        help="pl:Title (or Q123=pl:Title) for an edition without an article. Only if the user "
        "agreed. Repeatable.",
    )
    analyze.add_argument("--sort", choices=SORT_KEYS, default="growth", help="Order of editions.")
    analyze.add_argument(
        "--out", default=RUNS_DIR, help=f"Folder for run outputs (default ./{RUNS_DIR})."
    )
    analyze.set_defaults(handler=_analyze)

    report = sub.add_parser("report", help="Render the one-page PDF report for a run.")
    report.add_argument("--run", required=True, help="The run folder from analyze's Saved: line.")
    report.add_argument(
        "--lang",
        default="en",
        choices=languages(),
        help="Language of the report's fixed labels (the narrative can be in any language).",
    )
    report.add_argument(
        "--user-numbers",
        type=_numbers,
        default=[],
        help="Numbers the user gave you (e.g. a growth threshold of 15 or a goal of 5000), "
        "comma-separated, so the narrative may quote them. Never analysis numbers.",
    )
    report.set_defaults(handler=_report)
    return parser


def _write_crash_log() -> str:
    path = default_cache_dir() / "logs" / "last-error.txt"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(traceback.format_exc(), encoding="utf-8")
    except OSError:
        return "(could not write the log)"
    return str(path)


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except SkillError as error:
        _print_error(error.message, error.next_step)
        return EXIT_USAGE
    except KeyboardInterrupt:
        return EXIT_INTERRUPTED
    except Exception as error:  # noqa: BLE001 - last-resort guard, see module docstring
        log = _write_crash_log()
        _print_error(
            f"internal error in wiki-signal ({type(error).__name__}: {error}). Details: {log}",
            "Tell the user the command failed and quote this error. "
            "Do not write your own code to work around it.",
        )
        return EXIT_INTERNAL
