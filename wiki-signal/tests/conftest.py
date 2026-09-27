"""Record/replay of API responses, so tests run offline and deterministically (decision S3).

Each test module gets `tests/fixtures/<module>.json.gz` mapping URL -> response entry
(gzip: daily pageview histories are large but compress about tenfold).
Re-record from the live APIs with: WIKI_SIGNAL_RECORD=1 pytest tests/<module>.py
"""

import gzip
import json
import os
from pathlib import Path

import pytest
from wiki_signal.http_client import HttpClient, NotFoundError

FIXTURES = Path(__file__).parent / "fixtures"
RECORDING = os.environ.get("WIKI_SIGNAL_RECORD") == "1"


class ReplayClient:
    def __init__(self, entries):
        self.entries = entries

    def get_json(self, url, *, ttl):
        if url not in self.entries:
            pytest.fail(f"No recorded response for {url}. Re-record: WIKI_SIGNAL_RECORD=1 pytest")
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
    path = FIXTURES / f"{request.module.__name__.rsplit('.', 1)[-1]}.json.gz"
    entries = json.loads(gzip.decompress(path.read_bytes())) if path.exists() else {}
    if not RECORDING:
        yield ReplayClient(entries)
        return
    yield RecordingClient(entries)
    FIXTURES.mkdir(exist_ok=True)
    body = json.dumps(entries, ensure_ascii=False, sort_keys=True).encode()
    path.write_bytes(gzip.compress(body, mtime=0))  # mtime=0: same data, same bytes
