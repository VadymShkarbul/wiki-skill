import http.client
import io
import json
from email.message import Message
from urllib.error import HTTPError, URLError

import pytest
from wiki_interest import http_client
from wiki_interest.cache import Cache
from wiki_interest.errors import SkillError
from wiki_interest.http_client import HttpClient, NotFoundError

URL = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/x"


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def http_error(code, body=b"", headers=None):
    msg = Message()
    for key, value in (headers or {}).items():
        msg[key] = value
    return HTTPError(URL, code, "reason", msg, io.BytesIO(body))


class FakeNetwork:
    """Replays scripted outcomes: a dict (JSON body) or an exception to raise."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append(request)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return FakeResponse(json.dumps(outcome).encode())


@pytest.fixture
def sleeps():
    return []


def make_client(monkeypatch, network, sleeps, cache=None):
    monkeypatch.setattr(http_client, "urlopen", network)
    return HttpClient(cache, sleep=sleeps.append, min_interval=0)


def test_success_is_cached(monkeypatch, sleeps, tmp_path):
    network = FakeNetwork({"items": [1]})
    client = make_client(monkeypatch, network, sleeps, Cache(tmp_path))
    assert client.get_json(URL, ttl=60) == {"items": [1]}
    assert client.get_json(URL, ttl=60) == {"items": [1]}
    assert len(network.requests) == 1


def test_user_agent_has_name_version_and_contact(monkeypatch, sleeps):
    monkeypatch.setenv("WIKI_INTEREST_CONTACT", "me@example.org")
    network = FakeNetwork({})
    make_client(monkeypatch, network, sleeps).get_json(URL, ttl=60)
    agent = network.requests[0].get_header("User-agent")
    assert agent.startswith("wiki-interest/")
    assert "(me@example.org)" in agent


def test_404_raises_not_found_and_is_cached(monkeypatch, sleeps, tmp_path):
    network = FakeNetwork(http_error(404))
    client = make_client(monkeypatch, network, sleeps, Cache(tmp_path))
    for _ in range(2):
        with pytest.raises(NotFoundError):
            client.get_json(URL, ttl=60)
    assert len(network.requests) == 1


def test_429_waits_for_retry_after(monkeypatch, sleeps):
    network = FakeNetwork(http_error(429, headers={"Retry-After": "2"}), {"ok": True})
    assert make_client(monkeypatch, network, sleeps).get_json(URL, ttl=60) == {"ok": True}
    assert sleeps == [2.0]


def test_5xx_backs_off_then_reports_next_step(monkeypatch, sleeps):
    network = FakeNetwork(*[http_error(503, b'{"detail": "down"}')] * 4)
    with pytest.raises(SkillError) as info:
        make_client(monkeypatch, network, sleeps).get_json(URL, ttl=60)
    assert sleeps == [5.0, 10.0, 20.0]
    assert "HTTP 503" in info.value.message
    assert "down" in info.value.message
    assert "Retry" in info.value.next_step


def test_400_is_not_retried_and_forbids_workarounds(monkeypatch, sleeps):
    body = b'{"detail": "end timestamp is invalid"}'
    network = FakeNetwork(http_error(400, body))
    with pytest.raises(SkillError) as info:
        make_client(monkeypatch, network, sleeps).get_json(URL, ttl=60)
    assert sleeps == []
    assert "end timestamp is invalid" in info.value.message
    assert "Do not write your own code" in info.value.next_step


def test_network_error_is_retried_then_reported(monkeypatch, sleeps):
    network = FakeNetwork(*[URLError("no route")] * 4)
    with pytest.raises(SkillError) as info:
        make_client(monkeypatch, network, sleeps).get_json(URL, ttl=60)
    assert len(network.requests) == 4
    assert "no route" in info.value.message


@pytest.mark.parametrize(
    "drop",
    [http.client.RemoteDisconnected("closed"), http.client.IncompleteRead(b""), TimeoutError()],
)
def test_mid_response_drops_are_retried(monkeypatch, sleeps, drop):
    network = FakeNetwork(drop, {"ok": True})
    assert make_client(monkeypatch, network, sleeps).get_json(URL, ttl=60) == {"ok": True}
    assert sleeps == [5.0]


def test_non_json_body_is_reported_without_retry(monkeypatch, sleeps):
    monkeypatch.setattr(http_client, "urlopen", lambda request, timeout: FakeResponse(b"<html>"))
    with pytest.raises(SkillError):
        HttpClient(None, sleep=sleeps.append, min_interval=0).get_json(URL, ttl=60)
    assert sleeps == []


def test_requests_are_spaced(monkeypatch, sleeps):
    now = [100.0]
    monkeypatch.setattr(http_client, "urlopen", FakeNetwork({}, {}))
    client = HttpClient(None, sleep=sleeps.append, clock=lambda: now[0], min_interval=0.3)
    client.get_json(URL, ttl=60)
    now[0] += 0.1
    client.get_json(URL + "2", ttl=60)
    assert sleeps == [pytest.approx(0.2)]


@pytest.mark.live
def test_live_known_value(tmp_path):
    """Cross-check against a value read by hand from the API on 2026-09-26."""
    client = HttpClient(Cache(tmp_path))
    data = client.get_json(
        "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/"
        "all-access/user/Astronomy/monthly/2024010100/2024013100",
        ttl=60,
    )
    assert data["items"][0]["views"] == 43527
