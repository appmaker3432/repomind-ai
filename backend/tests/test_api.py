from fastapi.testclient import TestClient
import pytest

from app.config import parse_frontend_origins
from app.main import _rate_buckets, app
from app.models import AnalysisRequest


def setup_function() -> None:
    _rate_buckets.clear()


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("provider", ["openai", "gemini"])
def test_online_ai_requires_explicit_consent_before_network_access(provider: str) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/analyze",
            json={
                "repository_url": "https://github.com/octocat/hello",
                "ai_provider": provider,
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


def test_analysis_request_masks_and_normalizes_user_api_key() -> None:
    request = AnalysisRequest(
        repository_url="https://github.com/octocat/hello",
        ai_provider="openai",
        api_key="  user-secret-key  ",
    )
    assert request.api_key is not None
    assert request.api_key.get_secret_value() == "  user-secret-key  "
    assert "user-secret-key" not in repr(request)


@pytest.mark.parametrize("api_key", ["", "   ", "x" * 501])
def test_analysis_endpoint_rejects_blank_or_oversized_user_api_keys_without_echoing_them(api_key: str) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/analyze",
            json={
                "repository_url": "https://github.com/octocat/hello",
                "ai_provider": "openai",
                "consent_to_send_source": True,
                "api_key": api_key,
            },
        )
    assert response.status_code == 400
    assert response.json()["detail"] == "API key must contain between 1 and 500 characters."
    if api_key:
        assert api_key not in response.text


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
