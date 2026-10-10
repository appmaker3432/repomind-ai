from typing import Literal

from pydantic import BaseModel, Field, SecretStr


class AnalysisRequest(BaseModel):
    repository_url: str = Field(min_length=1, max_length=500)
    ai_provider: Literal["none", "ollama", "openai", "gemini"] = "none"
    consent_to_send_source: bool = False
    api_key: SecretStr | None = Field(default=None, repr=False)
    ai_model: str | None = Field(default=None, min_length=1, max_length=200)


class RepositoryMetadata(BaseModel):
    full_name: str
    description: str | None
    default_branch: str
    stars: int
    forks: int
    open_issues: int
    license: str | None
    size_kb: int
    html_url: str
    languages: dict[str, int]
    readme: str
    files: list[str]
    files_truncated: bool
    github_rate_limit_remaining: int | None = None


class SecurityFinding(BaseModel):
    title: str
    severity: Literal["HIGH", "MEDIUM", "LOW", "INFO"]
    confidence: Literal["HIGH", "MEDIUM", "LOW", "UNKNOWN"]
    path: str
    line: int | None = None
    evidence: str
    remediation: str
    source: Literal["Bandit", "OSV"]


class DependencySummary(BaseModel):
    scanned: int
    unsupported: int
    vulnerabilities: int
    notes: list[str]


class AiSummary(BaseModel):
    provider: str
    model: str
    summary: str
    architecture: str
    caveat: str = "AI-generated hypotheses; verify against source. Not a security verdict."


class ReadmeQuality(BaseModel):
    score: int
    checks: list[dict[str, str | bool]]


class AnalysisResponse(BaseModel):
    repository: RepositoryMetadata
    findings: list[SecurityFinding]
    dependency_summary: DependencySummary
    readme_quality: ReadmeQuality
    ai_summary: AiSummary | None
    ai_status: str
    scanner_notes: list[str]
    analyzed_at: str
