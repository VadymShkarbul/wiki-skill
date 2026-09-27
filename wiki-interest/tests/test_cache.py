from pathlib import Path

from wiki_interest.cache import Cache, default_cache_dir


class FakeClock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now


def test_roundtrip_within_ttl(tmp_path):
    cache = Cache(tmp_path, clock=FakeClock())
    cache.set("https://x/1", {"status": 200, "body": [1, "ł"]})
    assert cache.get("https://x/1", ttl=60) == {"status": 200, "body": [1, "ł"]}


def test_expired_entry_is_a_miss(tmp_path):
    clock = FakeClock()
    cache = Cache(tmp_path, clock=clock)
    cache.set("k", 1)
    clock.now += 61
    assert cache.get("k", ttl=60) is None


def test_missing_and_corrupt_entries_are_misses(tmp_path):
    cache = Cache(tmp_path)
    assert cache.get("absent", ttl=60) is None
    cache.set("k", 1)
    cache._path("k").write_text("{not json", encoding="utf-8")
    assert cache.get("k", ttl=60) is None


def test_entry_for_another_key_is_a_miss(tmp_path):
    cache = Cache(tmp_path)
    cache.set("a", 1)
    target = cache._path("b")
    target.parent.mkdir(parents=True, exist_ok=True)
    cache._path("a").rename(target)
    assert cache.get("b", ttl=60) is None


def test_unwritable_root_does_not_raise(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("", encoding="utf-8")
    cache = Cache(blocker / "sub")
    cache.set("k", 1)
    assert cache.get("k", ttl=60) is None


def test_default_dir_env_precedence(monkeypatch, tmp_path):
    monkeypatch.setenv("WIKI_INTEREST_CACHE_DIR", str(tmp_path / "own"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    assert default_cache_dir() == tmp_path / "own"
    monkeypatch.delenv("WIKI_INTEREST_CACHE_DIR")
    assert default_cache_dir() == tmp_path / "xdg" / "wiki-interest"
    monkeypatch.delenv("XDG_CACHE_HOME")
    assert default_cache_dir() == Path.home() / ".cache" / "wiki-interest"
