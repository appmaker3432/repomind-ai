from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

from app.github_client import RepositoryReference
from app.providers.base import parse_ai_analysis
from app.providers.gemini_provider import GeminiProvider
from app.providers.ollama_provider import OllamaProvider
from app.providers.openai_provider import OpenAIProvider


@pytest.mark.asyncio
async def test_ollama_provider_uses_documented_chat_endpoint() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": '{"summary":"A small example project.","architecture":"A documented module layout."}',
                }
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OllamaProvider(client, "http://127.0.0.1:11434", "installed-model")
        summary, architecture, model = await provider.analyze(RepositoryReference("owner", "repo"), "README excerpt")
    assert summary == "A small example project."
    assert architecture == "A documented module layout."
    assert model == "installed-model"
    assert requests[0].url == "http://127.0.0.1:11434/api/chat"
    assert "untrusted data" in requests[0].read().decode()


def test_ollama_requires_an_explicitly_configured_model() -> None:
    with pytest.raises(HTTPException, match="OLLAMA_MODEL"):
        OllamaProvider(httpx.AsyncClient(), "http://127.0.0.1:11434", "")


@pytest.mark.asyncio
async def test_openai_adapter_uses_the_configured_model_and_closes_client(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []
    client_closed = False

    class FakeOpenAIClient:
        def __init__(self, **kwargs: str) -> None:
            assert kwargs["api_key"] == "test-only-key"
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        async def create(self, **kwargs: object) -> SimpleNamespace:
            calls.append(kwargs)
            message = SimpleNamespace(
                content='{"summary":"A repository summary.","architecture":"A documented module layout."}'
            )
            choice = SimpleNamespace(message=message)
            return SimpleNamespace(choices=[choice])

        async def close(self) -> None:
            nonlocal client_closed
            client_closed = True

    monkeypatch.setattr("app.providers.openai_provider.AsyncOpenAI", FakeOpenAIClient)
    provider = OpenAIProvider("test-only-key", "configured-model")
    summary, architecture, model = await provider.analyze(RepositoryReference("owner", "repo"), "context")
    assert summary == "A repository summary."
    assert architecture == "A documented module layout."
    assert model == "configured-model"
    assert calls[0]["model"] == "configured-model"
    assert "untrusted data" in calls[0]["messages"][0]["content"]
    assert calls[0]["response_format"] == {"type": "json_object"}
    assert client_closed


@pytest.mark.asyncio
async def test_gemini_adapter_uses_native_structured_output_and_closes_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(
            {
                "url": str(request.url),
                "headers": request.headers,
                "body": request.read().decode(),
            }
        )
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": (
                                        '{"summary":"A repository summary.",'
                                        '"architecture":"A documented module layout."}'
                                    )
                                }
                            ]
                        }
                    }
                ]
            },
        )

    with pytest.raises(HTTPException, match="GEMINI_MODEL"):
        GeminiProvider(httpx.AsyncClient(), "test-only-key", "")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = GeminiProvider(client, "test-only-key", "configured-gemini-model")
        summary, architecture, model = await provider.analyze(
            RepositoryReference("owner", "repo"), "context"
        )

    assert summary == "A repository summary."
    assert architecture == "A documented module layout."
    assert model == "configured-gemini-model"
    assert calls[0]["url"].endswith("/models/configured-gemini-model:generateContent")
    assert calls[0]["headers"]["x-goog-api-key"] == "test-only-key"
    assert "test-only-key" not in calls[0]["url"]
    assert '"responseMimeType":"application/json"' in calls[0]["body"]
    assert '"summary"' in calls[0]["body"]
    assert "untrusted data" in calls[0]["body"]


@pytest.mark.asyncio
async def test_gemini_translates_rate_limit_and_unavailable_responses() -> None:
    for status, expected_status in ((429, 429), (503, 503)):
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(status))
        ) as client:
            provider = GeminiProvider(client, "test-only-key", "configured-model")
            with pytest.raises(HTTPException) as error:
                await provider.analyze(RepositoryReference("owner", "repo"), "context")
        assert error.value.status_code == expected_status


def test_gemini_requires_an_explicitly_configured_model() -> None:
    with pytest.raises(HTTPException, match="GEMINI_MODEL"):
        GeminiProvider(httpx.AsyncClient(), "test-only-key", "")


def test_ai_response_requires_summary_and_architecture() -> None:
    with pytest.raises(ValueError, match="architecture"):
        parse_ai_analysis('{"summary":"Only a summary."}')
