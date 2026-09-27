"""Report labels per language (decision R4): one JSON file per language in assets/i18n.

Adding a language means adding one file with the same keys as en.json; no code changes.
"""

import json
from functools import cache
from pathlib import Path
from typing import Any

from wiki_signal.errors import SkillError

I18N_DIR = Path(__file__).resolve().parents[2] / "assets" / "i18n"


def languages() -> list[str]:
    return sorted(p.stem for p in I18N_DIR.glob("*.json"))


@cache
def words(lang: str) -> dict[str, Any]:
    path = I18N_DIR / f"{lang}.json"
    if not path.exists():
        raise SkillError(
            f"No report labels for language {lang!r}.",
            f"Use one of: {', '.join(languages())}. Write the narrative in the user's language "
            "either way; only the fixed labels come from --lang.",
        )
    labels = json.loads(path.read_text(encoding="utf-8"))
    missing = set(json.loads((I18N_DIR / "en.json").read_text(encoding="utf-8"))) - set(labels)
    if missing:
        raise SkillError(
            f"assets/i18n/{lang}.json is missing labels: {', '.join(sorted(missing))}.",
            "This is a bug in the skill. Tell the user; use --lang en meanwhile.",
        )
    return labels
