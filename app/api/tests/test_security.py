import base64

import pytest
from fastapi.testclient import TestClient

from main import app
from security import check_bindings, is_loopback


@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.0.2", "::1", "localhost"])
def test_loopback_bindings(host, monkeypatch):
    assert is_loopback(host)
    monkeypatch.setenv("API_HOST", host)
    monkeypatch.setenv("WEB_HOST", host)
    check_bindings()


@pytest.mark.parametrize("variable", ["API_HOST", "WEB_HOST"])
@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.0.2.1", "example.com"])
def test_public_bind_refused_without_token_or_explicit_opt_out(variable, host, monkeypatch):
    monkeypatch.setenv(variable, host)
    monkeypatch.setenv("EVENTLENS_ALLOW_UNAUTHENTICATED", "true")
    with pytest.raises(ValueError, match=variable):
        with TestClient(app):
            pass
    monkeypatch.setenv("EVENTLENS_API_TOKEN", "shared-test-token")
    check_bindings()
    monkeypatch.delenv("EVENTLENS_API_TOKEN")
    monkeypatch.setenv("EVENTLENS_ALLOW_UNAUTHENTICATED", "1")
    check_bindings()


def test_local_defaults_and_remote_or_rebound_host_denied(client):
    assert client.get("/runs").status_code == 200
    assert client.get("/runs", headers={"host": "attacker.example"}).status_code == 403
    with TestClient(app, base_url="http://localhost", client=("192.0.2.1", 1234)) as remote:
        assert remote.get("/runs").status_code == 403
        assert remote.get("/runs", headers={"x-forwarded-for": "127.0.0.1"}).status_code == 403


@pytest.mark.parametrize("origin,status", [("http://localhost:3000", 200), ("https://attacker.example", 400)])
def test_token_mode_preflight_reaches_cors_but_actual_requests_still_require_auth(client, monkeypatch, origin, status):
    monkeypatch.setenv("EVENTLENS_API_TOKEN", "shared-test-token")
    response = client.options("/runs", headers={"origin": origin,
        "access-control-request-method": "GET", "access-control-request-headers": "authorization"})
    assert response.status_code == status
    if status == 200:
        assert response.headers["access-control-allow-origin"] == origin
        assert "authorization" in response.headers["access-control-allow-headers"].lower()
        authenticated = client.get("/runs", headers={"origin": origin, "authorization": "Bearer shared-test-token"})
        assert authenticated.status_code == 200
        assert authenticated.headers["access-control-allow-origin"] == origin
    assert client.get("/runs", headers={"origin": origin}).status_code == 401


@pytest.mark.parametrize("headers", [{}, {"origin": "http://localhost:3000"},
                                    {"access-control-request-method": "GET"}])
def test_non_preflight_options_still_require_token(client, monkeypatch, headers):
    monkeypatch.setenv("EVENTLENS_API_TOKEN", "shared-test-token")
    assert client.options("/runs", headers=headers).status_code == 401


@pytest.mark.parametrize("host,peer", [("localhost", "192.0.2.1"), ("attacker.example", "127.0.0.1")])
def test_no_token_preflight_preserves_remote_and_host_guard(host, peer):
    with TestClient(app, base_url=f"http://{host}", client=(peer, 1234)) as remote:
        response = remote.options("/runs", headers={"origin": "http://localhost:3000",
                                                  "access-control-request-method": "GET"})
        assert response.status_code == 403


@pytest.mark.parametrize("method,path", [
    ("GET", "/runs"), ("GET", "/runs/private"), ("POST", "/analyses"),
    ("PATCH", "/analyses/private"), ("DELETE", "/analyses/private"),
    ("GET", "/events"), ("GET", "/forecast"), ("POST", "/assistant/query"),
    ("GET", "/assistant/sources/forward_probabilities.csv"),
    ("GET", "/docs"), ("GET", "/openapi.json"),
])
def test_token_protects_every_api_surface_before_handlers(client, monkeypatch, method, path):
    monkeypatch.setenv("EVENTLENS_API_TOKEN", "shared-test-token")
    response = client.request(method, path)
    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Basic ")
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("authorization", ["", "Bearer wrong", "Basic !!!", "Basic /w==",
    "Basic " + base64.b64encode(b"wrong-user:shared-test-token").decode(), "Digest shared-test-token"])
def test_invalid_credentials_and_query_tokens_are_denied(client, monkeypatch, authorization):
    monkeypatch.setenv("EVENTLENS_API_TOKEN", "shared-test-token")
    response = client.get("/runs?token=shared-test-token", headers={"authorization": authorization})
    assert response.status_code == 401


@pytest.mark.parametrize("authorization", ["Bearer shared-test-token", "bearer shared-test-token",
    "Basic " + base64.b64encode(b"eventlens:shared-test-token").decode()])
def test_valid_bearer_and_browser_basic_auth_allow_remote_access(monkeypatch, authorization, tmp_path):
    monkeypatch.setenv("EVENTLENS_DB", str(tmp_path / "runs.sqlite3"))
    monkeypatch.setenv("EVENTLENS_API_TOKEN", "shared-test-token")
    with TestClient(app, base_url="http://research.example", client=("192.0.2.1", 1234)) as remote:
        response = remote.get("/runs", headers={"authorization": authorization})
        assert response.status_code == 200
        assert response.json() == []
        assert response.headers["cache-control"] == "no-store"


def test_preview_opt_out_allows_remote_but_never_overrides_a_configured_token(monkeypatch, tmp_path):
    monkeypatch.setenv("EVENTLENS_DB", str(tmp_path / "runs.sqlite3"))
    monkeypatch.setenv("EVENTLENS_ALLOW_UNAUTHENTICATED", "1")
    monkeypatch.setenv("WEB_HOST", "0.0.0.0")
    with TestClient(app, base_url="http://preview.example", client=("192.0.2.1", 1234)) as preview:
        assert preview.get("/runs").status_code == 200
        monkeypatch.setenv("EVENTLENS_API_TOKEN", "shared-test-token")
        assert preview.get("/runs").status_code == 401


def test_whitespace_token_is_not_an_authentication_configuration(monkeypatch):
    monkeypatch.setenv("EVENTLENS_API_TOKEN", "  ")
    with pytest.raises(ValueError, match="whitespace"):
        check_bindings()
