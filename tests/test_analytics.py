import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from core.analytics import AnalyticsMiddleware, _endpoint, _headers_from_env, identify  # noqa: E402


def test_client_param_wins_over_origin():
    assert identify("client=My Portfolio!", {"origin": "https://example.com"}) == (
        "client:my-portfolio",
        "my-portfolio",
        "Named clients",
    )


def test_origin_then_referer():
    assert identify("", {"origin": "https://www.example.com"})[0] == "site:example.com"
    assert identify("", {"referer": "https://foo.github.io/page?x=1"})[0] == "site:foo.github.io"


def test_own_and_local_sites_are_grouped():
    assert identify("", {"origin": "https://codetrace.xyz"})[2] == "Own sites"
    assert identify("", {"origin": "https://leetcode-stats.tashif.codes"})[2] == "Own sites"
    assert identify("", {"referer": "http://localhost:3000/"})[0] == "local"


def test_anonymous_callers_grouped_by_agent():
    assert identify("", {"user-agent": "python-requests/2.32.3"})[0] == "anon:python-requests"
    assert identify("", {"user-agent": "curl/8.7.1"})[0] == "anon:curl"
    assert identify("", {"user-agent": "github-camo (abc123)"})[0] == "anon:github-readme"
    assert identify("", {})[0] == "anon:unknown"


def test_empty_or_junk_client_param_falls_through():
    assert identify("client=%20%21%21", {"origin": "https://example.com"})[0] == "site:example.com"


def test_endpoint_drops_username():
    assert _endpoint("/") == "root"
    assert _endpoint("/someuser") == "profile"
    assert _endpoint("/someuser/heatmap") == "heatmap"
    assert _endpoint("/openapi.json") == "openapi.json"
    assert _endpoint("/docs") == "docs"


def test_otlp_headers_env_parsing():
    assert _headers_from_env("x-honeycomb-team=abc,x-other=a%20b") == {"x-honeycomb-team": "abc", "x-other": "a b"}
    assert _headers_from_env("") == {}


def _app(monkeypatch, endpoint="https://otlp.example", fail=False):
    for var in ("OTEL_EXPORTER_OTLP_ENDPOINT", "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"):
        monkeypatch.delenv(var, raising=False)
    if endpoint:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", endpoint)
    sent = []

    async def fake_send(self, payload):
        await asyncio.sleep(0)
        if fail:
            raise RuntimeError("backend down")
        sent.append((self.url, payload))

    monkeypatch.setattr(AnalyticsMiddleware, "_send", fake_send)
    app = FastAPI()
    app.add_middleware(AnalyticsMiddleware, api="leetcode")

    @app.get("/{user}/heatmap")
    def heatmap(user: str):
        return {"ok": True}

    return app, sent


def _span(payload):
    rs = payload["resourceSpans"][0]
    resource = {a["key"]: list(a["value"].values())[0] for a in rs["resource"]["attributes"]}
    span = rs["scopeSpans"][0]["spans"][0]
    attrs = {a["key"]: list(a["value"].values())[0] for a in span["attributes"]}
    return resource, span, attrs


def test_one_span_per_request(monkeypatch):
    app, sent = _app(monkeypatch)
    with TestClient(app) as client:
        r = client.get("/alice/heatmap?client=demo", headers={"origin": "https://example.com"})
        assert r.status_code == 200
    assert len(sent) == 1
    url, payload = sent[0]
    assert url == "https://otlp.example/v1/traces"
    resource, span, attrs = _span(payload)
    assert resource["service.name"] == "leetcode-stats-api"
    assert span["name"] == "GET heatmap"
    assert span["kind"] == 2
    assert len(span["traceId"]) == 32 and len(span["spanId"]) == 16
    assert int(span["endTimeUnixNano"]) >= int(span["startTimeUnixNano"])
    assert attrs["consumer"] == "client:demo"
    assert attrs["consumer.group"] == "Named clients"
    assert attrs["endpoint"] == "heatmap"
    assert attrs["http.response.status_code"] == "200"
    assert attrs["origin_host"] == "example.com"


def test_failed_requests_are_recorded(monkeypatch):
    app, sent = _app(monkeypatch)
    with TestClient(app) as client:
        assert client.get("/nope").status_code == 404
    _, span, attrs = _span(sent[0][1])
    assert attrs["http.response.status_code"] == "404"
    assert span["status"]["code"] == 0  # 4xx is the caller's fault, not a server error


def test_no_endpoint_sends_nothing(monkeypatch):
    app, sent = _app(monkeypatch, endpoint="")
    with TestClient(app) as client:
        assert client.get("/alice/heatmap").status_code == 200
    assert sent == []


def test_backend_failure_never_breaks_requests(monkeypatch):
    app, _ = _app(monkeypatch, fail=True)
    with TestClient(app) as client:
        assert client.get("/alice/heatmap").status_code == 200


def test_wait_mode_sends_before_returning(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://otlp.example")
    sent = []

    async def fake_send_now(self, payload):
        sent.append(payload)

    monkeypatch.setattr(AnalyticsMiddleware, "_send_now", fake_send_now)
    app = FastAPI()
    app.add_middleware(AnalyticsMiddleware, api="leetcode", wait=True)

    @app.get("/{user}/heatmap")
    def heatmap(user: str):
        return {"ok": True}

    with TestClient(app) as client:
        assert client.get("/alice/heatmap").status_code == 200
        assert len(sent) == 1  # already sent, not left to a background task


def test_wait_mode_backend_failure_never_breaks_requests(monkeypatch):
    import httpx

    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://otlp.example")

    async def boom(self, *args, **kwargs):
        raise httpx.TimeoutException("backend down")

    monkeypatch.setattr(httpx.AsyncClient, "post", boom)
    app = FastAPI()
    app.add_middleware(AnalyticsMiddleware, api="leetcode", wait=True)

    @app.get("/{user}/heatmap")
    def heatmap(user: str):
        return {"ok": True}

    with TestClient(app) as client:
        assert client.get("/alice/heatmap").status_code == 200
