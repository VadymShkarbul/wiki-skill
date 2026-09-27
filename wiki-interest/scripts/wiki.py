#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fpdf2>=2.8",
#     "matplotlib>=3.9",
#     "numpy>=2.0",
# ]
# ///
"""Entry point of the wiki-interest skill.

Run from any directory: uv run <skill-dir>/scripts/wiki.py --help
"""

import sys

from wiki_interest.cli import main

if __name__ == "__main__":
    sys.exit(main())
