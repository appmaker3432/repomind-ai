import base64

import httpx
import pytest
from fastapi import HTTPException

from app.github_client import (
    MAX_API_RESPONSE_BYTES,
    GitHubClient,
    _decode_base64_content,
    parse_public_github_url,
)


@pytest.mark.parametrize(
    "url,owner,name",
    [
        ("https://github.com/octocat/hello-world", "octocat", "hello-world"),
        ("https://github.com/octocat/hello-world.git", "octocat", "hello-world"),
    ],
)
def test_parse_public_github_url(url: str, owner: str, name: str) -> None:
    repository = parse_public_github_url(url)
    assert (repository.owner, repository.name) == (owner, name)


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/octocat/repo",
        "https://github.com.evil.example/octocat/repo",
        "https://github.com/octocat/repo?redirect=example.com",
        "https://github.com/octocat/repo/issues",
        "https://attacker@github.com/octocat/repo",
        "https://127.0.0.1/octocat/repo",
        "https://github.com:444/octocat/repo",
        "https://github.com:invalid/octocat/repo",
    ],
)
def test_parse_rejects_non_repository_and_ssrf_urls(url: str) -> None:
    with pytest.raises(HTTPException):
        parse_public_github_url(url)


def test_github_base64_decoder_accepts_wrapped_lines() -> None:
    assert _decode_base64_content("IyBIZWxs\nbw==") == b"# Hello"


@pytest.mark.asyncio
async def test_repository_metadata_and_tree_are_read_from_fixed_github_origin() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path.endswith("/languages"):
            return httpx.Response(200, json={"Python": 12})
        if request.url.path.endswith("/readme"):
            return httpx.Response(
                200,
                json={
                    "path": "README.md",
                    "encoding": "base64",
                    "content": base64.b64encode(b"# Hello").decode() + "\n",
                },
            )
        if "/git/trees/" in request.url.path:
            return httpx.Response(200, json={"tree": [{"path": "main.py", "type": "blob"}], "truncated": False})
        return httpx.Response(
            200,
            headers={"x-ratelimit-remaining": "55"},
            json={"private": False, "size": 5, "default_branch": "main", "full_name": "user/repo"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = GitHubClient(http)
        repository, languages, readme, paths, _ = await client.inspect(parse_public_github_url("https://github.com/user/repo"))
    assert repository["full_name"] == "user/repo"
    assert languages == {"Python": 12}
    assert readme == "# Hello"
    assert paths == ["main.py"]
    assert client.rate_limit_remaining == 55
    assert all(call.url.host == "api.github.com" for call in calls)


@pytest.mark.asyncio
async def test_repository_without_a_readme_remains_analyzable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/languages"):
            return httpx.Response(200, json={})
        if request.url.path.endswith("/readme"):
            return httpx.Response(404, json={"message": "Not Found"})
        if "/git/trees/" in request.url.path:
            return httpx.Response(200, json={"tree": [], "truncated": False})
        return httpx.Response(
            200,
            json={"private": False, "size": 1, "default_branch": "main", "full_name": "user/repo"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = GitHubClient(http)
        _, _, readme, paths, _ = await client.inspect(parse_public_github_url("https://github.com/user/repo"))
    assert readme == ""
    assert paths == []


@pytest.mark.asyncio
async def test_oversized_github_api_response_is_rejected_before_json_parsing() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-length": str(MAX_API_RESPONSE_BYTES + 1)},
            content=b"{}",
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = GitHubClient(http)
        with pytest.raises(HTTPException, match="6 MB response limit"):
            await client._get_json("/repos/user/repo")
