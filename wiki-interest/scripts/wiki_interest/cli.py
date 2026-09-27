"""Command-line interface: resolve -> analyze -> report (decision I1).

Every failure ends with ``Error:`` and ``Next:`` lines, never a traceback (decision E0).
"""

import argparse
import sys
import traceback
from collections.abc import Sequence
from typing import NoReturn

from wiki_interest import __version__
from wiki_interest.cache import default_cache_dir
from wiki_interest.errors import SkillError

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_USAGE = 2
EXIT_INTERRUPTED = 130
PROG = "wiki.py"


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


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog=PROG, description="Wikipedia pageview interest analysis.")
    parser.add_argument("--version", action="version", version=f"wiki-interest {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)

    resolve = sub.add_parser("resolve", help="Find Wikidata concepts for a topic.")
    resolve.set_defaults(handler=_not_implemented)

    analyze = sub.add_parser("analyze", help="Fetch pageviews and compute verdicts and charts.")
    analyze.set_defaults(handler=_not_implemented)

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
