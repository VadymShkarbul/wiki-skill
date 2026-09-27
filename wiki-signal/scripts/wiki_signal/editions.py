"""Wikipedia language editions, validated against Wikimedia's site matrix.

An edition is identified by its subdomain (``pl``, ``zh-yue``), which is also what the
pageviews API expects. Its Wikidata language code (``yue``) and database name
(``zh_yuewiki``) can differ from it.
"""

import difflib
from dataclasses import dataclass

from wiki_signal.errors import SkillError
from wiki_signal.mediawiki import META_API, WEEK, JsonGetter, action_api

MAX_EDITIONS = 15

# Country codes that people often use for languages. Applied only when the code is not
# itself an open Wikipedia edition (for example `se` is Northern Sami, not Swedish).
COUNTRY_CODE_HINTS = {
    "cz": "cs",
    "ua": "uk",
    "jp": "ja",
    "gr": "el",
    "dk": "da",
    "kr": "ko",
    "cn": "zh",
    "rs": "sr",
    "by": "be",
    "il": "he",
    "iw": "he",
    "ge": "ka",
    "br": "pt",
    "us": "en",
    "gb": "en",
    "uk-ua": "uk",
}


@dataclass(frozen=True)
class Edition:
    code: str
    dbname: str
    lang: str
    name: str

    @property
    def project(self) -> str:
        return f"{self.code}.wikipedia"

    @property
    def api(self) -> str:
        return f"https://{self.code}.wikipedia.org/w/api.php"

    def label(self) -> str:
        return f"{self.code} ({self.name})"


class Catalog:
    """Open Wikipedia editions, by code, with English names for matching and display."""

    def __init__(self, editions: list[Edition]) -> None:
        self.by_code = {e.code: e for e in editions}
        self.by_dbname = {e.dbname: e for e in editions}
        self._by_name = {e.name.casefold(): e for e in editions}

    def is_edition(self, token: str) -> bool:
        """True if every comma-separated part of ``token`` names an edition."""
        parts = [p for p in token.replace(";", ",").split(",") if p.strip()]
        try:
            return bool(parts) and all(self._lookup(p.strip()) for p in parts)
        except SkillError:
            return False

    def parse(self, text: str) -> list[Edition]:
        """Parse ``pl,cs`` (codes, dbnames like ``plwiki``, or English names like ``Polish``)."""
        tokens = [t.strip() for t in text.replace(";", ",").split(",") if t.strip()]
        if not tokens:
            raise SkillError(
                "No Wikipedia editions given.", "Pass editions as codes, e.g. --editions pl,cs."
            )
        result: list[Edition] = []
        for token in tokens:
            edition = self._lookup(token)
            if edition not in result:
                result.append(edition)
        if len(result) > MAX_EDITIONS:
            raise SkillError(
                f"{len(result)} editions requested; the limit is {MAX_EDITIONS}.",
                "Ask the user which editions matter most and re-run with fewer.",
            )
        return result

    def _lookup(self, token: str) -> Edition:
        key = token.casefold().removesuffix(".wikipedia.org").removesuffix(".wikipedia")
        if key in self.by_code:
            return self.by_code[key]
        if key in self.by_dbname:
            return self.by_dbname[key]
        if key in self._by_name:
            return self._by_name[key]
        raise SkillError(f"Unknown Wikipedia edition {token!r}.", self._suggest(key))

    def _suggest(self, key: str) -> str:
        hinted = COUNTRY_CODE_HINTS.get(key)
        if hinted in self.by_code:
            e = self.by_code[hinted]
            return f"{key!r} is a country code. Did you mean {e.label()}? Re-run with {e.code}."
        close = difflib.get_close_matches(key, list(self.by_code) + list(self._by_name), n=3)
        if close:
            labels = ", ".join(self._lookup(c).label() for c in close)
            return f"Did you mean one of: {labels}? Re-run with the right code."
        return "Use a Wikipedia subdomain code, e.g. pl for pl.wikipedia.org."


def load_catalog(client: JsonGetter) -> Catalog:
    data = action_api(
        client,
        META_API,
        {
            "action": "sitematrix",
            "smtype": "language",
            "smlangprop": "code|name|localname|site",
            "smsiteprop": "url|dbname|code",
        },
        ttl=WEEK,
    )
    editions = []
    for key, language in data["sitematrix"].items():
        if key == "count":
            continue
        for site in language.get("site", []):
            if site.get("code") != "wiki" or site.get("closed"):
                continue
            subdomain = site["url"].removeprefix("https://").split(".")[0]
            name = language.get("localname") or language.get("name") or subdomain
            editions.append(Edition(subdomain, site["dbname"], language["code"], name))
    return Catalog(editions)
