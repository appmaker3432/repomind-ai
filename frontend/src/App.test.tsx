import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

describe("RepoMind dashboard", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("rejects malformed repository URLs before issuing a request", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    render(<App />);
    fireEvent.change(screen.getByLabelText("PUBLIC REPOSITORY URL"), {
      target: { value: "https://github.com.evil.example/owner/repo" },
    });
    fireEvent.click(screen.getByRole("button", { name: /analyze repository/i }));
    expect(screen.getByRole("alert")).toHaveTextContent("public GitHub URL");
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("runs scanner-only analysis without AI controls, keys, or model selection", async () => {
    const analysisReport = {
      repository: {
        full_name: "octocat/hello",
        description: "A public test repository",
        default_branch: "main",
        stars: 1,
        forks: 2,
        open_issues: 0,
        license: null,
        size_kb: 10,
        html_url: "https://github.com/octocat/hello",
        languages: { Python: 100 },
        readme: "# Hello\n\nRepository README content.",
        files: ["README.md"],
        files_truncated: false,
        github_rate_limit_remaining: 59,
      },
      findings: [],
      dependency_summary: { scanned: 0, unsupported: 0, vulnerabilities: 0, notes: [] },
      readme_quality: { score: 0, checks: [] },
      scanner_notes: ["Only supported dependency manifests are checked."],
      analyzed_at: "2026-01-01T00:00:00Z",
    };
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(analysisReport), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    render(<App />);
    fireEvent.change(screen.getByLabelText("PUBLIC REPOSITORY URL"), {
      target: { value: "https://github.com/owner/repo" },
    });
    fireEvent.click(screen.getByRole("button", { name: /analyze repository/i }));

    await waitFor(() => expect(fetchSpy).toHaveBeenCalledOnce());
    expect(JSON.parse(fetchSpy.mock.calls[0][1]?.body as string)).toEqual({
      repository_url: "https://github.com/owner/repo",
    });
    expect(screen.queryByLabelText(/AI ANALYSIS|API KEY|MODEL/)).not.toBeInTheDocument();
    expect(screen.getByText(/no AI or API key/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "octocat/hello" })).toBeInTheDocument();
    expect(screen.getByText(/Repository README content/)).toBeInTheDocument();
  });
});
