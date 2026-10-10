import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from .config import get_settings, parse_frontend_origins
from .dependency_audit import audit_dependencies
from .github_client import (
    MAX_SOURCE_FILES,
    GitHubClient,
    parse_public_github_url,
)
from .models import AnalysisRequest, AnalysisResponse, AiSummary, DependencySummary, RepositoryMetadata
from .providers import GeminiProvider, OllamaProvider, OpenAIProvider
from .readme_analysis import analyze_readme
from .scanner import run_bandit
from .security import is_sensitive_path, redact_sensitive_lines

_RATE_WINDOW_SECONDS = 60
_MAX_REQUESTS_PER_WINDOW = 10
_MAX_RATE_BUCKETS = 10_000
_rate_buckets: dict[str, list[float]] = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_settings()
    yield


app = FastAPI(title="RepoMind AI", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_frontend_origins(get_settings().frontend_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def _enforce_rate_limit(request: Request) -> None:
    now = monotonic()
    client_address = request.client.host if request.client else "unknown"
    requests = [timestamp for timestamp in _rate_buckets.get(client_address, []) if now - timestamp < _RATE_WINDOW_SECONDS]
    if len(requests) >= _MAX_REQUESTS_PER_WINDOW:
        raise HTTPException(429, "Too many analyses from this address. Wait a minute and try again.")
    if client_address not in _rate_buckets and len(_rate_buckets) >= _MAX_RATE_BUCKETS:
        oldest_key = min(_rate_buckets, key=lambda key: _rate_buckets[key][-1], default=None)
        if oldest_key is not None:
            del _rate_buckets[oldest_key]
    requests.append(now)
    _rate_buckets[client_address] = requests


def _ai_context(readme: str, source_files: dict[str, str], files: list[str], description: str | None) -> str:
    parts = [
        f"Repository description: {redact_sensitive_lines(description or 'Not provided')}",
        f"README:\n{redact_sensitive_lines(readme)[:8_000]}",
    ]
    visible_paths = [path for path in files if not is_sensitive_path(path)]
    parts.append("Repository paths:\n" + "\n".join(visible_paths[:80]))
    remaining_chars = 24_000
    for path, content in source_files.items():
        if is_sensitive_path(path):
            continue
        redacted = redact_sensitive_lines(content)
        excerpt = redacted[: min(4_000, remaining_chars)]
        if excerpt:
            parts.append(f"File: {path}\n{excerpt}")
            remaining_chars -= len(excerpt)
        if remaining_chars <= 0:
            break
    return "\n\n".join(parts)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze(body: AnalysisRequest, request: Request) -> AnalysisResponse:
    _enforce_rate_limit(request)
    if body.ai_provider in {"openai", "gemini"} and not body.consent_to_send_source:
        raise HTTPException(400, "Explicit consent is required before repository context is sent to an online AI provider.")

    settings = get_settings()
    reference = parse_public_github_url(body.repository_url)
    timeout = httpx.Timeout(settings.request_timeout_seconds)
    api_client = httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=False,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "RepoMind-AI",
        },
    )
    service_client = httpx.AsyncClient(timeout=timeout, follow_redirects=False)
    try:
        async with asyncio.timeout(settings.max_analysis_seconds):
            github = GitHubClient(api_client)
            repository, languages, readme, paths, _ = await github.inspect(reference)
            candidate_paths = [
                path
                for path in paths
                if (
                    path.lower().endswith(".py")
                    or path.rsplit("/", 1)[-1].lower()
                    in {
                        "requirements.txt",
                        "requirements-dev.txt",
                        "requirements-prod.txt",
                        "package-lock.json",
                    }
                )
                and not is_sensitive_path(path)
            ][:MAX_SOURCE_FILES]
            source_files = await github.fetch_source_files(reference, candidate_paths)
            bandit_findings, scanner_notes = run_bandit(source_files)
            dependency_findings, scanned_count, unsupported_count, dependency_notes = await audit_dependencies(
                source_files, service_client
            )
            scanner_notes.extend(dependency_notes)

            ai_summary = None
            ai_status = "AI analysis was not run."
            if body.ai_provider != "none":
                context = _ai_context(readme, source_files, paths, repository.get("description"))
                if body.ai_provider == "ollama":
                    provider = OllamaProvider(httpx.AsyncClient(timeout=25.0, follow_redirects=False), settings.ollama_base_url, settings.ollama_model)
                    try:
                        summary, architecture, model = await provider.analyze(reference, context)
                    finally:
                        await provider.client.aclose()
                elif body.ai_provider == "gemini":
                    provider = GeminiProvider(
                        httpx.AsyncClient(timeout=25.0, follow_redirects=False),
                        settings.gemini_api_key,
                        settings.gemini_model,
                    )
                    try:
                        summary, architecture, model = await provider.analyze(reference, context)
                    finally:
                        await provider.client.aclose()
                else:
                    provider = OpenAIProvider(settings.openai_api_key, settings.openai_model)
                    summary, architecture, model = await provider.analyze(reference, context)
                ai_summary = AiSummary(
                    provider=provider.name,
                    model=model,
                    summary=summary,
                    architecture=architecture,
                )
                ai_status = f"AI analysis ran with {provider.name}; validate its hypotheses against the source."

            metadata = RepositoryMetadata(
                full_name=str(repository["full_name"]),
                description=repository.get("description"),
                default_branch=str(repository["default_branch"]),
                stars=int(repository.get("stargazers_count", 0)),
                forks=int(repository.get("forks_count", 0)),
                open_issues=int(repository.get("open_issues_count", 0)),
                license=(repository.get("license") or {}).get("spdx_id"),
                size_kb=int(repository["size"]),
                html_url=str(repository["html_url"]),
                languages=languages,
                readme=readme,
                files=paths[:500],
                files_truncated=len(paths) > 500,
                github_rate_limit_remaining=github.rate_limit_remaining,
            )
            notes = scanner_notes + [
                f"Repository source fetches are bounded to at most {MAX_SOURCE_FILES} files and 4 MB total; the README and visible file tree are separately capped.",
                "Bandit findings apply only to the fetched Python files; other languages are not statically scanned in this release.",
                "Repository code is never executed. Scanners inspect downloaded source as data.",
                "No findings does not guarantee that a repository is secure.",
            ]
            return AnalysisResponse(
                repository=metadata,
                findings=bandit_findings + dependency_findings,
                dependency_summary=DependencySummary(
                    scanned=scanned_count,
                    unsupported=unsupported_count,
                    vulnerabilities=len(dependency_findings),
                    notes=dependency_notes,
                ),
                readme_quality=analyze_readme(readme),
                ai_summary=ai_summary,
                ai_status=ai_status,
                scanner_notes=notes,
                analyzed_at=datetime.now(UTC).isoformat(),
            )
    except TimeoutError as exc:
        raise HTTPException(504, "Repository analysis exceeded its 60-second time limit.") from exc
    finally:
        await api_client.aclose()
        await service_client.aclose()


@app.post("/api/report/markdown")
async def markdown_report(report: AnalysisResponse) -> Response:
    from .report import to_markdown

    return PlainTextResponse(to_markdown(report), media_type="text/markdown; charset=utf-8")


@app.post("/api/report/json")
async def json_report(report: AnalysisResponse) -> Response:
    from .report import to_json

    return Response(content=to_json(report), media_type="application/json")


frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
