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

from wiki_interest import __version__
from wiki_interest.analysis import DEFAULT_MONTHS, SORT_KEYS, run_analysis
from wiki_interest.cache import Cache, default_cache_dir
from wiki_interest.editions import load_catalog
from wiki_interest.errors import SkillError
from wiki_interest.http_client import HttpClient
from wiki_interest.output import RUNS_DIR, save
from wiki_interest.resolve import MAX_CANDIDATES, find_candidates, format_candidates

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


def _not_implemented(args: argparse.Namespace) -> int:
    raise SkillError(
        f"`{args.command}` is not implemented in this build yet.",
        "Tell the user this command is not available yet.",
    )


def _resolve(args: argparse.Namespace) -> int:
    client = make_client()
    catalog = load_catalog(client)
    editions = catalog.parse(args.editions)
    concepts = find_candidates(
        client, catalog, args.topic, editions, search_lang=args.search_lang, limit=args.limit
    )
    print(format_candidates(args.topic, editions, concepts, command_prefix()))
    return EXIT_OK


def _analyze(args: argparse.Namespace) -> int:
    client = make_client()
    catalog = load_catalog(client)
    editions = catalog.parse(args.editions)
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


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog=PROG, description="Wikipedia pageview interest analysis.")
    parser.add_argument("--version", action="version", version=f"wiki-interest {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)

    resolve = sub.add_parser(
        "resolve",
        help="Find Wikidata concepts for a topic and their article in each edition.",
    )
    resolve.add_argument(
        "topic", help="Topic in words, a QID (Q333), lang:Title (pl:Astronomia), or an article URL."
    )
    resolve.add_argument("--editions", required=True, help="Edition codes, e.g. pl,cs.")
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
    analyze.add_argument("--editions", required=True, help="Edition codes, e.g. pl,cs.")
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
    report.set_defaults(handler=_not_implemented)
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
            f"internal error in wiki-interest ({type(error).__name__}: {error}). Details: {log}",
            "Tell the user the command failed and quote this error. "
            "Do not write your own code to work around it.",
        )
        return EXIT_INTERNAL
