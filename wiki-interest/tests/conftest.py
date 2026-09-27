"""Record/replay of API responses, so tests run offline and deterministically (decision S3).

Each test module gets `tests/fixtures/<module>.json` mapping URL -> response entry.
Re-record from the live APIs with: WIKI_INTEREST_RECORD=1 pytest tests/<module>.py
"""

import json
import os
from pathlib import Path

import pytest
from wiki_interest.http_client import HttpClient, NotFoundError

FIXTURES = Path(__file__).parent / "fixtures"
RECORDING = os.environ.get("WIKI_INTEREST_RECORD") == "1"


class ReplayClient:
    def __init__(self, entries):
        self.entries = entries

    def get_json(self, url, *, ttl):
        if url not in self.entries:
            pytest.fail(f"No recorded response for {url}. Re-record: WIKI_INTEREST_RECORD=1 pytest")
        entry = self.entries[url]
        if entry["status"] == 404:
            raise NotFoundError
        return entry["body"]


class RecordingClient:
    def __init__(self, entries):
        self.entries = entries
        self.live = HttpClient(None)

    def get_json(self, url, *, ttl):
        try:
            body = self.live.get_json(url, ttl=ttl)
        except NotFoundError:
            self.entries[url] = {"status": 404}
            raise
        self.entries[url] = {"status": 200, "body": body}
        return body


@pytest.fixture(scope="module")
def api(request):
    path = FIXTURES / f"{request.module.__name__.rsplit('.', 1)[-1]}.json"
    entries = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not RECORDING:
        yield ReplayClient(entries)
        return
    yield RecordingClient(entries)
    FIXTURES.mkdir(exist_ok=True)
    path.write_text(
        json.dumps(entries, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8"
    )
