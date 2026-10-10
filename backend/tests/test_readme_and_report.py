from app.models import (
    AnalysisResponse,
    DependencySummary,
    RepositoryMetadata,
)
from app.readme_analysis import analyze_readme
from app.report import to_json, to_markdown


def test_readme_quality_rewards_documented_sections() -> None:
    report = analyze_readme(
        "# Repo\n## Overview\n## Installation\n## Usage\n## License\n## Contributing\n"
    )
    assert report.score == 100


def test_report_exports_disclose_no_findings_is_not_a_security_guarantee() -> None:
    report = AnalysisResponse(
        repository=RepositoryMetadata(
            full_name="owner/repo",
            description=None,
            default_branch="main",
            stars=0,
            forks=0,
            open_issues=0,
            license=None,
            size_kb=1,
            html_url="https://github.com/owner/repo",
            languages={},
            readme="",
            files=[],
            files_truncated=False,
        ),
        findings=[],
        dependency_summary=DependencySummary(scanned=0, unsupported=0, vulnerabilities=0, notes=[]),
        readme_quality=analyze_readme(""),
        ai_summary=None,
        ai_status="AI analysis was not run.",
        scanner_notes=[],
        analyzed_at="2026-01-01T00:00:00+00:00",
    )
    assert "not a guarantee" in to_markdown(report)
    assert '"findings": []' in to_json(report)
