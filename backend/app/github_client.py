import base64
import binascii
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import quote, urlsplit

import httpx
from fastapi import HTTPException

GITHUB_API = "https://api.github.com"
MAX_REPOSITORY_KB = 200_000
MAX_TREE_ENTRIES = 5_000
MAX_FILE_BYTES = 200_000
MAX_TOTAL_SOURCE_BYTES = 4_000_000
MAX_SOURCE_FILES = 25
MAX_README_BYTES = 128_000
MAX_API_RESPONSE_BYTES = 6_000_000
_REPOSITORY_PART = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


def _decode_base64_content(content: str) -> bytes:
    normalized = "".join(content.split())
    try:
        return base64.b64decode(normalized, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(502, "GitHub returned invalid base64 file content.") from exc


@dataclass(frozen=True)
class RepositoryReference:
    owner: str
    name: str


def parse_public_github_url(value: str) -> RepositoryReference:
    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
    except ValueError as exc:
        raise HTTPException(400, "Enter a valid public GitHub repository URL.") from exc

    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise HTTPException(400, "Only public repositories at https://github.com/owner/repo are supported.")

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        raise HTTPException(400, "Use a repository URL containing exactly an owner and repository name.")

    owner, name = parts
    if name.endswith(".git"):
        name = name[:-4]
    if not _REPOSITORY_PART.fullmatch(owner) or not _REPOSITORY_PART.fullmatch(name):
        raise HTTPException(400, "The repository URL contains invalid owner or repository characters.")
    return RepositoryReference(owner=owner, name=name)


class GitHubClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client
        self.rate_limit_remaining: int | None = None

    def _record_rate_limit(self, response: httpx.Response) -> None:
        remaining = response.headers.get("x-ratelimit-remaining")
        if remaining is not None and remaining.isdigit():
            self.rate_limit_remaining = int(remaining)

    async def _read_bounded(self, response: httpx.Response) -> bytes:
        content_length = response.headers.get("content-length")
        if content_length and content_length.isdigit() and int(content_length) > MAX_API_RESPONSE_BYTES:
            raise HTTPException(413, "GitHub returned a response larger than RepoMind's 6 MB response limit.")
        chunks = bytearray()
        async for chunk in response.aiter_bytes():
            if len(chunks) + len(chunk) > MAX_API_RESPONSE_BYTES:
                raise HTTPException(413, "GitHub returned a response larger than RepoMind's 6 MB response limit.")
            chunks.extend(chunk)
        return bytes(chunks)

    def _check_response(self, response: httpx.Response, *, allow_not_found: bool = False) -> bool:
        self._record_rate_limit(response)
        if response.status_code == 404:
            if allow_not_found:
                return False
            raise HTTPException(404, "The public GitHub repository or requested resource was not found.")
        if response.status_code == 403 and self.rate_limit_remaining == 0:
            reset = response.headers.get("x-ratelimit-reset")
            if reset and reset.isdigit():
                reset_time = datetime.fromtimestamp(int(reset), tz=UTC).isoformat()
                raise HTTPException(429, f"GitHub's anonymous API rate limit is exhausted. It resets at {reset_time}.")
            raise HTTPException(429, "GitHub's anonymous API rate limit is exhausted. Try again after its reset window.")
        if response.status_code == 403:
            raise HTTPException(403, "GitHub refused the public API request.")
        if response.status_code >= 400:
            raise HTTPException(502, f"GitHub returned an unexpected HTTP {response.status_code} response.")
        return True

    async def _get_json(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
        allow_not_found: bool = False,
    ) -> dict:
        try:
            async with self.client.stream("GET", f"{GITHUB_API}{path}", params=params) as response:
                if not self._check_response(response, allow_not_found=allow_not_found):
                    return {}
                content = await self._read_bounded(response)
        except httpx.TimeoutException as exc:
            raise HTTPException(504, "GitHub's public API timed out.") from exc
        except httpx.RequestError as exc:
            raise HTTPException(502, "Could not reach GitHub's public API.") from exc
        try:
            payload = json.loads(content)
        except (ValueError, UnicodeDecodeError) as exc:
            raise HTTPException(502, "GitHub returned an invalid JSON response.") from exc
        if not isinstance(payload, dict):
            raise HTTPException(502, "GitHub returned an unexpected response shape.")
        return payload

    async def _get_content(self, path: str) -> bytes:
        try:
            async with self.client.stream("GET", f"{GITHUB_API}{path}") as response:
                if not self._check_response(response, allow_not_found=True):
                    return b""
                payload_bytes = await self._read_bounded(response)
        except httpx.TimeoutException as exc:
            raise HTTPException(504, "GitHub's public API timed out while reading a repository file.") from exc
        except httpx.RequestError as exc:
            raise HTTPException(502, "Could not reach GitHub's public API.") from exc
        try:
            payload = json.loads(payload_bytes)
            if payload.get("encoding") != "base64" or not isinstance(payload.get("content"), str):
                return b""
            encoded_content = "".join(payload["content"].split())
            if len(encoded_content) > ((MAX_FILE_BYTES + 2) // 3) * 4 + 4:
                return b""
            return _decode_base64_content(encoded_content)
        except (ValueError, binascii.Error, AttributeError) as exc:
            raise HTTPException(502, "GitHub returned invalid base64 file content.") from exc

    async def inspect(self, reference: RepositoryReference) -> tuple[dict, dict[str, int], str, list[str], bool]:
        repo_path = f"/repos/{quote(reference.owner, safe='')}/{quote(reference.name, safe='')}"
        repository = await self._get_json(repo_path)
        if repository.get("private") is True:
            raise HTTPException(400, "Only public GitHub repositories can be analyzed.")
        if not isinstance(repository.get("size"), int) or repository["size"] > MAX_REPOSITORY_KB:
            raise HTTPException(413, "This repository exceeds the 200 MB analysis limit.")

        default_branch = repository.get("default_branch")
        if not isinstance(default_branch, str) or not default_branch:
            raise HTTPException(502, "GitHub did not provide a default branch for this repository.")
        if any(part in {".", ".."} for part in default_branch.split("/")):
            raise HTTPException(502, "GitHub returned an invalid default branch name.")

        languages_payload = await self._get_json(f"{repo_path}/languages")
        languages = {
            name: value
            for name, value in languages_payload.items()
            if isinstance(name, str) and isinstance(value, int)
        }
        readme_payload = await self._get_json(f"{repo_path}/readme", allow_not_found=True)
        readme = ""
        if isinstance(readme_payload.get("path"), str):
            encoded = readme_payload.get("content")
            if isinstance(encoded, str) and readme_payload.get("encoding") == "base64":
                try:
                    encoded = "".join(encoded.split())
                    if len(encoded) > ((MAX_README_BYTES + 2) // 3) * 4 + 4:
                        encoded = encoded[: ((MAX_README_BYTES + 2) // 3) * 4]
                    decoded = _decode_base64_content(encoded)[:MAX_README_BYTES]
                    readme = decoded.decode("utf-8", errors="replace")
                except HTTPException as exc:
                    raise HTTPException(502, "GitHub returned an invalid README encoding.") from exc

        tree = await self._get_json(
            f"{repo_path}/git/trees/{quote(default_branch, safe='')}",
            params={"recursive": "1"},
        )
        entries = tree.get("tree")
        if not isinstance(entries, list):
            raise HTTPException(502, "GitHub returned an unexpected repository tree.")
        if tree.get("truncated") is True:
            raise HTTPException(413, "GitHub truncated this repository tree; this repository is too large to analyze safely.")
        if len(entries) > MAX_TREE_ENTRIES:
            raise HTTPException(413, f"This repository exceeds the {MAX_TREE_ENTRIES:,}-entry analysis limit.")

        files = [
            entry["path"]
            for entry in entries
            if isinstance(entry, dict)
            and entry.get("type") == "blob"
            and isinstance(entry.get("path"), str)
        ]
        return repository, languages, readme, files, len(files) > 500

    async def fetch_source_files(self, reference: RepositoryReference, paths: list[str]) -> dict[str, str]:
        repo_path = f"/repos/{quote(reference.owner, safe='')}/{quote(reference.name, safe='')}/contents"
        selected: dict[str, str] = {}
        total_bytes = 0
        for path in paths:
            if len(selected) >= MAX_SOURCE_FILES or total_bytes >= MAX_TOTAL_SOURCE_BYTES:
                break
            path_parts = path.split("/")
            if any(part in {"", ".", ".."} for part in path_parts):
                continue
            encoded_path = "/".join(quote(part, safe="") for part in path_parts)
            content = await self._get_content(f"{repo_path}/{encoded_path}")
            if len(content) > MAX_FILE_BYTES:
                continue
            if total_bytes + len(content) > MAX_TOTAL_SOURCE_BYTES or b"\x00" in content:
                continue
            total_bytes += len(content)
            selected[path] = content.decode("utf-8", errors="replace")
        return selected
