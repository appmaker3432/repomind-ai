from fastapi.testclient import TestClient

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
