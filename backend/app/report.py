import json

from .models import AnalysisResponse


def to_markdown(report: AnalysisResponse) -> str:
    repository = report.repository
    lines = [
        f"# RepoMind report: {repository.full_name}",
        "",
        f"- Repository: [{repository.html_url}]({repository.html_url})",
        f"- Analyzed: {report.analyzed_at}",
        "",
        "## Repository",
        "",
        repository.description or "No repository description provided.",
        "",
        "## Languages",
        "",
    ]
    lines.extend(f"- {language}: {bytes_count:,} bytes" for language, bytes_count in repository.languages.items())
    lines.extend(["", "## README quality", "", f"Score: {report.readme_quality.score}/100", ""])
    lines.extend(f"- [{'x' if item['passed'] else ' '}] {item['name']}: {item['note']}" for item in report.readme_quality.checks)
    lines.extend(["", "## Security findings", ""])
    if not report.findings:
        lines.append("No findings were reported by the scanners that ran. This is not a guarantee that the repository is secure.")
    for finding in report.findings:
        location = f"{finding.path}:{finding.line}" if finding.line is not None else finding.path
        lines.extend(
            [
                f"### {finding.severity}: {finding.title}",
                "",
                f"- Source: {finding.source} (confidence: {finding.confidence})",
                f"- Location: `{location}`",
                f"- Evidence: {finding.evidence}",
                f"- Remediation: {finding.remediation}",
                "",
            ]
        )
    lines.extend(["## Scanner notes", ""])
    lines.extend(f"- {note}" for note in report.scanner_notes)
    return "\n".join(lines) + "\n"


def to_json(report: AnalysisResponse) -> str:
    return json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2)
