"""Topic -> Wikidata concept -> article in each edition (decisions D1-D5).

The code proposes candidates and the model picks one (D1). An edition without an article is
reported as not covered, with proxies the user may approve (D3). Proxies are the edition's
articles on the concept's broader concepts in Wikidata: subclass of, then instance of (D3a).
"""

import re
import shlex
import urllib.parse
from dataclasses import dataclass, field
from typing import Any

from wiki_interest.editions import Catalog, Edition
from wiki_interest.errors import SkillError
from wiki_interest.mediawiki import WIKIDATA_API, JsonGetter, action_api, batches

MAX_CANDIDATES = 5
PROXIES_PER_EDITION = 3
BROADER_PROPERTIES = ("P279", "P31")  # subclass of, instance of
QID_RE = re.compile(r"[Qq]([1-9]\d*)")
WIKI_URL_RE = re.compile(r"https?://([a-z0-9-]+)(?:\.m)?\.wikipedia\.org/", re.IGNORECASE)


@dataclass(frozen=True)
class Proxy:
    title: str
    via: str


@dataclass
class Concept:
    qid: str
    label: str
    description: str
    wiki_count: int
    titles: dict[str, str]
    proxies: dict[str, list[Proxy]] = field(default_factory=dict)

    def missing(self, editions: list[Edition]) -> list[Edition]:
        return [e for e in editions if e.code not in self.titles]


@dataclass(frozen=True)
class TitleRef:
    edition: Edition
    title: str


def parse_ref(text: str, catalog: Catalog) -> str | TitleRef | None:
    """Return a QID, a TitleRef (``pl:Title`` or a Wikipedia URL), or None for free text."""
    text = text.strip()
    if match := QID_RE.fullmatch(text):
        return f"Q{match.group(1)}"
    if match := WIKI_URL_RE.match(text):
        code = match.group(1).lower()
        parsed = urllib.parse.urlsplit(text)
        title = ""
        if parsed.path.startswith("/wiki/"):
            title = parsed.path.removeprefix("/wiki/")
        else:
            title = urllib.parse.parse_qs(parsed.query).get("title", [""])[0]
        title = urllib.parse.unquote(title).replace("_", " ").strip()
        if code in catalog.by_code and title:
            return TitleRef(catalog.by_code[code], title)
        raise SkillError(
            f"Could not read an article title from the URL {text!r}.",
            "Pass the article as lang:Title, e.g. pl:Astronomia.",
        )
    prefix, sep, title = text.partition(":")
    if sep and prefix.lower() in catalog.by_code and title.strip():
        return TitleRef(catalog.by_code[prefix.lower()], title.strip())
    return None


def resolve_title(client: JsonGetter, ref: TitleRef) -> str:
    """Follow normalization and redirects, then return the article's Wikidata item."""
    data = action_api(
        client,
        ref.edition.api,
        {
            "action": "query",
            "titles": ref.title,
            "redirects": "1",
            "prop": "pageprops",
            "ppprop": "wikibase_item",
        },
    )
    page = data["query"]["pages"][0]
    if page.get("missing") or page.get("invalid"):
        raise SkillError(
            f"No article {ref.title!r} in {ref.edition.label()} Wikipedia.",
            'Check the title, or search by topic instead: resolve "<topic in words>".',
        )
    qid = page.get("pageprops", {}).get("wikibase_item")
    if not qid:
        raise SkillError(
            f"{ref.edition.code}:{page['title']} is not linked to a Wikidata item, so it cannot "
            "be matched across editions.",
            "Tell the user; pick another article or search by topic.",
        )
    return qid


def search_qids(client: JsonGetter, topic: str, lang: str, limit: int) -> list[tuple[str, bool]]:
    """Return (qid, exact) pairs. Search is by label prefix; exact means the whole label or an
    alias equals the topic, e.g. "Go" matches the game exactly but "Google" only by prefix."""
    data = action_api(
        client,
        WIKIDATA_API,
        {
            "action": "wbsearchentities",
            "search": topic,
            "language": lang,
            "uselang": lang,
            "type": "item",
            "limit": str(min(limit * 4, 50)),
        },
    )
    wanted = topic.strip().casefold()
    return [
        (hit["id"], hit.get("match", {}).get("text", "").casefold() == wanted)
        for hit in data.get("search", [])
    ]


def fetch_entities(
    client: JsonGetter, qids: list[str], props: str, languages: list[str], sitefilter: str = ""
) -> dict[str, Any]:
    entities: dict[str, Any] = {}
    for batch in batches(qids):
        params = {
            "action": "wbgetentities",
            "ids": "|".join(batch),
            "props": props,
            "languages": "|".join(dict.fromkeys(languages)),
        }
        if sitefilter:
            params["sitefilter"] = sitefilter
        entities.update(action_api(client, WIKIDATA_API, params)["entities"])
    return entities


def _pick(values: dict[str, Any], languages: list[str]) -> str:
    for lang in languages:
        if lang in values:
            return values[lang]["value"]
    return ""


def make_concept(
    entity: dict[str, Any], catalog: Catalog, editions: list[Edition], languages: list[str]
) -> Concept | None:
    """Build a Concept, or None for items that are not topics (no Wikipedia article at all,
    or Wikimedia pages such as disambiguation pages and lists)."""
    if entity.get("missing") is not None:
        return None
    sitelinks = entity.get("sitelinks", {})
    wiki_count = sum(1 for dbname in sitelinks if dbname in catalog.by_dbname)
    english = entity.get("descriptions", {}).get("en", {}).get("value", "")
    if wiki_count == 0 or english.startswith("Wikimedia "):
        return None
    titles = {e.code: sitelinks[e.dbname]["title"] for e in editions if e.dbname in sitelinks}
    return Concept(
        qid=entity["id"],
        label=_pick(entity.get("labels", {}), languages) or entity["id"],
        description=_pick(entity.get("descriptions", {}), languages),
        wiki_count=wiki_count,
        titles=titles,
    )


def _broader(entity: dict[str, Any]) -> list[str]:
    parents = []
    for prop in BROADER_PROPERTIES:
        for statement in entity.get("claims", {}).get(prop, []):
            value = statement.get("mainsnak", {}).get("datavalue", {}).get("value", {})
            if isinstance(value, dict) and value.get("id") and value["id"] not in parents:
                parents.append(value["id"])
    return parents[:6]


def add_proxies(client: JsonGetter, concepts: list[Concept], editions: list[Edition]) -> None:
    """Proxies are the edition's articles on the concept's broader concepts. Text search was
    tried and dropped: it returned unrelated, sometimes offensive, articles (decision D3a)."""
    needy = [c for c in concepts if c.missing(editions)]
    if not needy:
        return
    claims = fetch_entities(client, [c.qid for c in needy], "claims", ["en"])
    parents = {c.qid: _broader(claims.get(c.qid, {})) for c in needy}
    all_parents = list(dict.fromkeys(q for qs in parents.values() for q in qs))
    missing_dbnames = "|".join(dict.fromkeys(e.dbname for c in needy for e in c.missing(editions)))
    parent_entities = (
        fetch_entities(client, all_parents, "labels|sitelinks", ["en"], missing_dbnames)
        if all_parents
        else {}
    )
    for concept in needy:
        for edition in concept.missing(editions):
            found: list[Proxy] = []
            for pid in parents[concept.qid]:
                parent = parent_entities.get(pid, {})
                link = parent.get("sitelinks", {}).get(edition.dbname)
                if link and len(found) < PROXIES_PER_EDITION:
                    name = _pick(parent.get("labels", {}), ["en"]) or pid
                    found.append(Proxy(link["title"], f"broader concept: {name}, {pid}"))
            concept.proxies[edition.code] = found


def find_candidates(  # noqa: PLR0913 - mirrors the CLI flags one to one
    client: JsonGetter,
    catalog: Catalog,
    topic: str,
    editions: list[Edition],
    *,
    search_lang: str = "en",
    limit: int = 3,
) -> list[Concept]:
    limit = max(1, min(limit, MAX_CANDIDATES))
    languages = ["en", search_lang, *(e.lang for e in editions)]
    ref = parse_ref(topic, catalog)
    if isinstance(ref, str):
        hits = [(ref, True)]
    elif isinstance(ref, TitleRef):
        hits = [(resolve_title(client, ref), True)]
    else:
        hits = search_qids(client, topic, search_lang, limit)
        for lang in dict.fromkeys(e.lang for e in editions):
            if hits:
                break
            hits = search_qids(client, topic, lang, limit)
    qids = [qid for qid, _ in hits]
    exact = {qid for qid, is_exact in hits if is_exact}
    entities = fetch_entities(client, qids, "labels|descriptions|sitelinks", languages)
    built = (make_concept(entities.get(q, {}), catalog, editions, languages) for q in qids)
    # Exact matches first, then a notability prior: widely covered meanings before rare ones
    # ("Mercury": planet before a car brand; "Go": the game and the language before Google).
    concepts = sorted((c for c in built if c), key=lambda c: (c.qid not in exact, -c.wiki_count))[
        :limit
    ]
    if not concepts:
        if ref is not None:
            raise SkillError(
                f"{qids[0]} is not a topic with Wikipedia articles.",
                'Search by topic instead: resolve "<topic in words>".',
            )
        raise SkillError(
            f"No Wikidata concept with Wikipedia articles matches {topic!r}.",
            "Retry with the topic's usual English name, or with --search-lang set to the "
            "language the topic is written in, or pass an article URL.",
        )
    add_proxies(client, concepts, editions)
    return concepts


def format_candidates(
    topic: str, editions: list[Edition], concepts: list[Concept], command: str
) -> str:
    names = ", ".join(e.label() for e in editions)
    lines = [f"Candidates for {topic!r} · editions: {names}"]
    for n, c in enumerate(concepts, 1):
        about = f": {c.description}" if c.description else ""
        count = f"{c.wiki_count} Wikipedia{'s' if c.wiki_count != 1 else ''}"
        lines.append(f"{n}. {c.qid} {c.label}{about} · {count}")
        for e in editions:
            if e.code in c.titles:
                lines.append(f"   {e.code}: {c.titles[e.code]}")
                continue
            lines.append(f"   {e.code}: NOT COVERED (no article on this concept)")
            proxies = c.proxies.get(e.code, [])
            if proxies:
                shown = "; ".join(f'"{p.title}" ({p.via})' for p in proxies)
                lines.append(f"       possible proxies, only if the user agrees: {shown}")
            else:
                lines.append("       no proxy found in this edition")
    codes = ",".join(e.code for e in editions)
    first = concepts[0]
    lines += [
        "",
        (
            "Next: pick the candidate that matches what the user means. If more than one fits, "
            "ask the user. If none fits, re-run resolve with the concept's encyclopedic "
            'name, e.g. "English language" instead of "learning English".'
        ),
        f"Then run: {command} analyze --concepts {first.qid} --editions {codes}",
    ]
    proxy_example = next(
        (
            (e, first.proxies[e.code][0])
            for e in first.missing(editions)
            if first.proxies.get(e.code)
        ),
        None,
    )
    if proxy_example:
        edition, proxy = proxy_example
        ref = shlex.quote(f"{edition.code}:{proxy.title}")
        lines.append(f"To use a proxy (only after the user agrees), add: --proxy {ref}")
    return "\n".join(lines)
