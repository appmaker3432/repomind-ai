import type { AiProvider, AnalysisReport } from "./types";

export class AnalysisError extends Error {}

export function apiUrl(path: string): string {
  const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").trim().replace(/\/+$/, "");
  return `${baseUrl}${path}`;
}

export function isPublicGitHubRepositoryUrl(value: string): boolean {
  try {
    const url = new URL(value.trim());
    return (
      url.protocol === "https:" &&
      url.hostname === "github.com" &&
      url.port === "" &&
      url.username === "" &&
      url.password === "" &&
      url.search === "" &&
      url.hash === "" &&
      url.pathname.split("/").filter(Boolean).length === 2
    );
  } catch {
    return false;
  }
}

export async function analyzeRepository(
  repositoryUrl: string,
  aiProvider: AiProvider,
  consentToSendSource: boolean,
): Promise<AnalysisReport> {
  const response = await fetch(apiUrl("/api/analyze"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      repository_url: repositoryUrl,
      ai_provider: aiProvider,
      consent_to_send_source: consentToSendSource,
    }),
  });
  if (!response.ok) {
    let message = `Analysis failed with HTTP ${response.status}.`;
    const contentType = response.headers.get("content-type") ?? "";
    if (response.status === 404 && !contentType.includes("application/json")) {
      message =
        "The analysis API endpoint was not found. This deployment may be outdated or misconfigured; contact the site maintainer.";
    }
    try {
      const payload: unknown = await response.json();
      if (typeof payload === "object" && payload !== null && "detail" in payload) {
        const detail = payload.detail;
        if (typeof detail === "string") message = detail;
      }
    } catch {
      // Keep the HTTP status message when the API does not send JSON.
    }
    throw new AnalysisError(message);
  }
  return (await response.json()) as AnalysisReport;
}

export function buildMarkdownReport(report: AnalysisReport): string {
  const findings =
    report.findings.length === 0
      ? "No findings were reported by the scanners that ran. This is not a guarantee that the repository is secure."
      : report.findings
          .map(
            (finding) =>
              `### ${finding.severity}: ${finding.title}\n\n` +
              `- Source: ${finding.source} (confidence: ${finding.confidence})\n` +
              `- Location: \`${finding.path}${finding.line === null ? "" : `:${finding.line}`}\`\n` +
              `- Evidence: ${finding.evidence}\n- Remediation: ${finding.remediation}`,
          )
          .join("\n\n");
  const ai =
    report.ai_summary === null
      ? "AI analysis was not run."
      :       `Provider: ${report.ai_summary.provider} (${report.ai_summary.model})\n\n` +
      `### Project summary\n\n${report.ai_summary.summary}\n\n` +
      `### Architecture explanation\n\n${report.ai_summary.architecture}\n\n${report.ai_summary.caveat}`;
  return [
    `# RepoMind AI report: ${report.repository.full_name}`,
    "",
    `- Repository: ${report.repository.html_url}`,
    `- Analyzed: ${report.analyzed_at}`,
    `- AI status: ${report.ai_status}`,
    "",
    "## README quality",
    "",
    `Score: ${report.readme_quality.score}/100`,
    ...report.readme_quality.checks.map(
      (check) => `- [${check.passed ? "x" : " "}] ${check.name}: ${check.note}`,
    ),
    "",
    "## Security findings",
    "",
    findings,
    "",
    "## AI analysis",
    "",
    ai,
    "",
    "## Scanner notes",
    "",
    ...report.scanner_notes.map((note) => `- ${note}`),
    "",
  ].join("\n");
}

export function downloadReport(filename: string, content: string, mime: string): void {
  const url = URL.createObjectURL(new Blob([content], { type: mime }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}
