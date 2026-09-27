"""File cache for API responses (decision I4).

Entries live in the user cache dir, not in the skill dir, which may be read-only. The cache
is an optimization: read or write failures never fail a command.
"""

import hashlib
import json
import os
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any


def _writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write-test"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
    except OSError:
        return False
    return True


def default_cache_dir() -> Path:
    """Return the cache root.

    Precedence: ``$WIKI_SIGNAL_CACHE_DIR``, then ``$XDG_CACHE_HOME/wiki-signal``,
    then ``~/.cache/wiki-signal``. If that isn't writable (e.g. Codex's sandbox allows only
    the workspace and /tmp), fall back to the system temp dir so caching still works.
    """
    if override := os.environ.get("WIKI_SIGNAL_CACHE_DIR"):
        chosen = Path(override)
    else:
        base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
        chosen = Path(base) / "wiki-signal"
    if _writable(chosen):
        return chosen
    return Path(tempfile.gettempdir()) / "wiki-signal-cache"


class Cache:
    """JSON values keyed by string (usually a URL), each with its own TTL at read time."""

    def __init__(self, root: Path, clock: Callable[[], float] = time.time) -> None:
        self.root = root
        self._clock = clock

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode()).hexdigest()
        return self.root / "http" / digest[:2] / f"{digest}.json"

    def get(self, key: str, ttl: float) -> Any | None:
        """Return the stored value if it is younger than ``ttl`` seconds, else None."""
        try:
            entry = json.loads(self._path(key).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(entry, dict) or entry.get("key") != key:
            return None
        if self._clock() - entry.get("stored_at", 0) > ttl:
            return None
        return entry.get("value")

    def set(self, key: str, value: Any) -> None:
        """Store ``value`` atomically, so a crash never leaves a half-written entry."""
        path = self._path(key)
        entry = {"key": key, "stored_at": self._clock(), "value": value}
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(entry, f, ensure_ascii=False)
            Path(tmp).replace(path)
        except OSError:
            return
