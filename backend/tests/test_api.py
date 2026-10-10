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


def test_analysis_runs_without_ai_or_provider_credentials(monkeypatch) -> None:
    class FakeGitHubClient:
        rate_limit_remaining = 59

        def __init__(self, client) -> None:
            pass

        async def inspect(self, reference):
            repository = {
                "full_name": "octocat/hello",
                "description": "A test repository",
                "default_branch": "main",
                "stargazers_count": 1,
                "forks_count": 2,
                "open_issues_count": 0,
                "license": None,
                "size": 10,
                "html_url": "https://github.com/octocat/hello",
            }
            return repository, {"Python": 100}, "# Hello", ["app.py"], False

        async def fetch_source_files(self, reference, paths):
            return {"app.py": "print('hello')"}

    async def fake_audit_dependencies(source_files, client):
        return [], 0, 0, []

    monkeypatch.setattr("app.main.GitHubClient", FakeGitHubClient)
    monkeypatch.setattr("app.main.run_bandit", lambda source_files: ([], []))
    monkeypatch.setattr("app.main.audit_dependencies", fake_audit_dependencies)

    with TestClient(app) as client:
        response = client.post(
            "/api/analyze",
            json={"repository_url": "https://github.com/octocat/hello"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["repository"]["full_name"] == "octocat/hello"
    assert payload["findings"] == []
    assert "ai_summary" not in payload
    assert "ai_status" not in payload


def test_invalid_repository_url_is_rejected_before_network_access() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/analyze",
            json={"repository_url": "http://127.0.0.1/private"},
        )
    assert response.status_code == 400


def test_analysis_rejects_removed_ai_request_fields() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/analyze",
            json={
                "repository_url": "https://github.com/octocat/hello",
                "ai_provider": "openai",
                "api_key": "unused-test-key",
            },
        )
    assert response.status_code == 422


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
