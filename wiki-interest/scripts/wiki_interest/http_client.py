"""HTTP client for Wikimedia APIs.

Follows the Wikimedia API etiquette (see docs/research-data-sources.md):
- a descriptive User-Agent with contact information;
- one request at a time, spaced by ``min_interval`` to stay under 200 requests/min;
- on 429 or 5xx, wait for ``Retry-After`` or back off exponentially from 5 s.
"""

import http.client
import json
import os
import sys
import time
import urllib.parse
from collections.abc import Callable
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from wiki_interest import __version__
from wiki_interest.cache import Cache
from wiki_interest.errors import SkillError

DEFAULT_CONTACT = "https://github.com/VadymShkarbul"
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
MAX_RETRY_WAIT = 60.0


def user_agent() -> str:
    contact = os.environ.get("WIKI_INTEREST_CONTACT", DEFAULT_CONTACT)
    python = f"{sys.version_info.major}.{sys.version_info.minor}"
    return f"wiki-interest/{__version__} ({contact}) python-urllib/{python}"


class NotFoundError(Exception):
    """HTTP 404. The pageviews API returns it both for unknown titles and for missing data."""


def _retry_wait(retry_after: str | None, attempt: int) -> float:
    if retry_after:
        try:
            return min(float(retry_after), MAX_RETRY_WAIT)
        except ValueError:
            pass
        try:
            delay = parsedate_to_datetime(retry_after).timestamp() - time.time()
            return min(max(delay, 0.0), MAX_RETRY_WAIT)
        except (TypeError, ValueError):
            pass
    return min(5.0 * 2**attempt, MAX_RETRY_WAIT)


def _error_detail(error: HTTPError) -> str:
    try:
        body = error.read().decode("utf-8", "replace")
    except OSError:
        return error.reason or ""
    try:
        parsed = json.loads(body)
    except ValueError:
        return body[:200]
    if isinstance(parsed, dict):
        return str(parsed.get("detail") or parsed.get("title") or parsed)[:200]
    return body[:200]


class HttpClient:
    """GET JSON with caching, spacing, and retries. Only this class touches the network."""

    def __init__(  # noqa: PLR0913 - every argument is an injectable seam for tests
        self,
        cache: Cache | None,
        *,
        min_interval: float = 0.3,
        max_retries: int = 3,
        timeout: float = 30.0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.cache = cache
        self.min_interval = min_interval
        self.max_retries = max_retries
        self.timeout = timeout
        self._sleep = sleep
        self._clock = clock
        self._last_request: float | None = None

    def get_json(self, url: str, *, ttl: float) -> Any:
        """Return the parsed JSON body. Raises NotFoundError on 404 and SkillError on failure."""
        if self.cache is not None:
            cached = self.cache.get(url, ttl)
            if cached is not None:
                return self._unwrap(cached)
        entry = self._fetch(url)
        if self.cache is not None:
            self.cache.set(url, entry)
        return self._unwrap(entry)

    @staticmethod
    def _unwrap(entry: dict[str, Any]) -> Any:
        if entry.get("status") == 404:  # noqa: PLR2004
            raise NotFoundError
        return entry.get("body")

    def _throttle(self) -> None:
        if self._last_request is not None:
            wait = self.min_interval - (self._clock() - self._last_request)
            if wait > 0:
                self._sleep(wait)
        self._last_request = self._clock()

    def _fetch(self, url: str) -> dict[str, Any]:
        host = urllib.parse.urlsplit(url).netloc
        request = Request(  # noqa: S310 - callers build https URLs to Wikimedia hosts only
            url, headers={"User-Agent": user_agent(), "Accept": "application/json"}
        )
        for attempt in range(self.max_retries + 1):
            self._throttle()
            try:
                with urlopen(request, timeout=self.timeout) as response:  # noqa: S310
                    return {"status": 200, "body": json.load(response)}
            except HTTPError as error:
                if error.code == 404:  # noqa: PLR2004
                    return {"status": 404}
                if error.code in RETRYABLE_STATUS and attempt < self.max_retries:
                    self._sleep(_retry_wait(error.headers.get("Retry-After"), attempt))
                    continue
                raise self._http_failure(error, host) from error
            except ValueError as error:  # the body is not JSON: retrying won't help
                raise self._network_failure(error, host) from error
            # URLError wraps failures while sending; OSError (e.g. RemoteDisconnected) and
            # HTTPException (e.g. IncompleteRead) escape unwrapped from the response phase.
            except (OSError, http.client.HTTPException) as error:
                if attempt >= self.max_retries:
                    raise self._network_failure(error, host) from error
                self._sleep(_retry_wait(None, attempt))
        msg = "unreachable: the retry loop always returns or raises"
        raise AssertionError(msg)

    @staticmethod
    def _http_failure(error: HTTPError, host: str) -> SkillError:
        detail = _error_detail(error)
        if error.code == 429:  # noqa: PLR2004
            return SkillError(
                f"{host} is rate-limiting requests (HTTP 429) after several retries.",
                "Wait one minute, then re-run the same command.",
            )
        if error.code >= 500:  # noqa: PLR2004
            return SkillError(
                f"{host} is failing (HTTP {error.code}): {detail}",
                "Retry the same command in a few minutes. If it keeps failing, tell the user "
                "Wikimedia is having problems.",
            )
        return SkillError(
            f"{host} rejected the request (HTTP {error.code}): {detail}",
            "This is a bug in the skill, not in your command. Tell the user the exact error. "
            "Do not write your own code to fetch the data.",
        )

    @staticmethod
    def _network_failure(error: Exception, host: str) -> SkillError:
        reason = getattr(error, "reason", error)
        return SkillError(
            f"Could not read a response from {host}: {reason}",
            "Check the internet connection and re-run the same command. If it keeps failing, "
            "tell the user Wikimedia is unreachable from this machine.",
        )
