import { describe, expect, it, vi } from "vitest";

import { analyzeRepository, apiUrl, buildMarkdownReport, isPublicGitHubRepositoryUrl } from "./api";
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

describe("production API URL configuration", () => {
  it("uses the relative same-origin path locally when no base URL is set", () => {
    expect(apiUrl("/api/analyze")).toBe("/api/analyze");
  });

  it("uses the configured backend origin and removes trailing slashes", () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://repomind-api.example.onrender.com/");
    try {
      expect(apiUrl("/api/analyze")).toBe("https://repomind-api.example.onrender.com/api/analyze");
    } finally {
      vi.unstubAllEnvs();
    }
  });
});

describe("analysis API errors", () => {
  it("explains how to restore the API connection when fetch cannot reach the backend", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(
      analyzeRepository("https://github.com/octocat/hello-world"),
    ).rejects.toThrow("start the FastAPI backend on http://127.0.0.1:8000");
  });

  it("explains when a deployed frontend is not connected to its API", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("<!doctype html><title>Not found</title>", {
          status: 404,
          headers: { "Content-Type": "text/html" },
        }),
      ),
    );
    await expect(
      analyzeRepository("https://github.com/octocat/hello-world"),
    ).rejects.toThrow("analysis API endpoint was not found");
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
      scanner_notes: ["Only supported dependency manifests are checked."],
      analyzed_at: "2026-01-01T00:00:00Z",
    } satisfies AnalysisReport;
    const markdown = buildMarkdownReport(report);
    expect(markdown).toContain("not a guarantee");
    expect(markdown).toContain("Only supported dependency manifests");
  });
});
