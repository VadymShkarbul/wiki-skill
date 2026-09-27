"""Thin helper for MediaWiki Action APIs (Wikipedia editions, Wikidata, Meta)."""

import urllib.parse
from typing import Any, Protocol

from wiki_interest.errors import SkillError

WEEK = 7 * 24 * 3600
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
META_API = "https://meta.wikimedia.org/w/api.php"
BATCH = 50  # MediaWiki's limit for ids/titles per request


class JsonGetter(Protocol):
    def get_json(self, url: str, *, ttl: float) -> Any: ...


def action_api(client: JsonGetter, base: str, params: dict[str, str], ttl: float = WEEK) -> Any:
    """GET an Action API request. Parameters are sorted so equal requests share a cache entry."""
    query = {**params, "format": "json", "formatversion": "2"}
    url = f"{base}?{urllib.parse.urlencode(sorted(query.items()))}"
    data = client.get_json(url, ttl=ttl)
    if isinstance(data, dict) and "error" in data:
        error = data["error"]
        host = urllib.parse.urlsplit(base).netloc
        raise SkillError(
            f"{host} API error {error.get('code')}: {error.get('info')}",
            "This is a bug in the skill, not in your command. Tell the user the exact error. "
            "Do not write your own code to fetch the data.",
        )
    return data


def batches(items: list[str], size: int = BATCH) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]
