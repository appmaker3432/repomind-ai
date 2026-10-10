from fastapi.testclient import TestClient

from app.config import parse_frontend_origins
from app.main import _rate_buckets, app


def setup_function() -> None:
    _rate_buckets.clear()


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_online_ai_requires_explicit_consent_before_network_access() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/analyze",
            json={
                "repository_url": "https://github.com/octocat/hello",
                "ai_provider": "openai",
                "consent_to_send_source": False,
            },
        )
    assert response.status_code == 400
    assert "Explicit consent" in response.json()["detail"]


def test_invalid_repository_url_is_rejected_before_network_access() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/analyze",
            json={"repository_url": "http://127.0.0.1/private", "ai_provider": "none"},
        )
    assert response.status_code == 400


def test_frontend_origins_parse_as_exact_origins() -> None:
    assert parse_frontend_origins(
        "http://localhost:5173, http://127.0.0.1:5173, https://repomind-ai.onrender.com/"
    ) == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://repomind-ai.onrender.com",
    ]


def test_frontend_origins_reject_wildcards_paths_and_credentials() -> None:
    for value in ("*", "https://example.com/app", "https://user:pass@example.com", ""):
        try:
            parse_frontend_origins(value)
        except ValueError:
            continue
        raise AssertionError(f"Unsafe CORS origin configuration was accepted: {value!r}")
