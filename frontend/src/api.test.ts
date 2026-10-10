import { describe, expect, it } from "vitest";

import { buildMarkdownReport, isPublicGitHubRepositoryUrl } from "./api";
import type { AnalysisReport } from "./types";

describe("public repository URL validation", () => {
  it("accepts only the canonical public GitHub repository origin and path", () => {
    expect(isPublicGitHubRepositoryUrl("https://github.com/octocat/hello-world")).toBe(true);
    expect(isPublicGitHubRepositoryUrl("https://github.com.evil.example/octocat/repo")).toBe(false);
    expect(isPublicGitHubRepositoryUrl("http://github.com/octocat/repo")).toBe(false);
    expect(isPublicGitHubRepositoryUrl("https://github.com/octocat/repo/issues")).toBe(false);
    expect(isPublicGitHubRepositoryUrl("https://user@github.com/octocat/repo")).toBe(false);
  });
});

describe("Markdown report export", () => {
  it("includes scanner scope and the non-guarantee caveat", () => {
    const report = {
      repository: {
        full_name: "octocat/hello",
        description: null,
        default_branch: "main",
        stars: 0,
        forks: 0,
        open_issues: 0,
        license: null,
        size_kb: 10,
        html_url: "https://github.com/octocat/hello",
        languages: {},
        readme: "",
        files: [],
        files_truncated: false,
        github_rate_limit_remaining: 59,
      },
      findings: [],
      dependency_summary: { scanned: 0, unsupported: 0, vulnerabilities: 0, notes: [] },
      readme_quality: { score: 0, checks: [] },
      ai_summary: null,
      ai_status: "AI analysis was not run.",
      scanner_notes: ["Only supported dependency manifests are checked."],
      analyzed_at: "2026-01-01T00:00:00Z",
    } satisfies AnalysisReport;
    const markdown = buildMarkdownReport(report);
    expect(markdown).toContain("not a guarantee");
    expect(markdown).toContain("Only supported dependency manifests");
  });
});
