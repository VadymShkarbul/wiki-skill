"""The no-uv fallback (requirements.txt) must match the script lockfile (decision S2)."""

import shutil
import subprocess
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv is not installed")
def test_requirements_match_lock():
    exported = subprocess.run(
        ["uv", "export", "--script", "scripts/wiki.py", "--quiet"],  # noqa: S607
        cwd=SKILL_DIR,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    committed = (SKILL_DIR / "requirements.txt").read_text(encoding="utf-8")
    assert committed == exported, (
        "requirements.txt is stale: run `uv export --script scripts/wiki.py --quiet "
        "> requirements.txt` in the skill dir"
    )
