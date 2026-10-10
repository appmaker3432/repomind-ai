import { useState, type FormEvent, type ReactNode } from "react";

import { analyzeRepository, buildMarkdownReport, downloadReport, isPublicGitHubRepositoryUrl } from "./api";
import type { AiProvider, AnalysisReport, SecurityFinding } from "./types";

function Icon({ children }: { children: ReactNode }) {
  return <span className="icon" aria-hidden="true">{children}</span>;
}

function App() {
  const [repositoryUrl, setRepositoryUrl] = useState("");
  const [provider, setProvider] = useState<AiProvider>("none");
  const [onlineConsent, setOnlineConsent] = useState(false);
  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleAnalyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setReport(null);
    if (!isPublicGitHubRepositoryUrl(repositoryUrl)) {
      setError("Enter a public GitHub URL in the form https://github.com/owner/repository.");
      return;
    }
    if ((provider === "openai" || provider === "gemini") && !onlineConsent) {
      setError("Give explicit consent before sending repository context to the online AI provider.");
      return;
    }
    setLoading(true);
    try {
      setReport(await analyzeRepository(repositoryUrl, provider, onlineConsent));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Analysis could not be completed.");
    } finally {
      setLoading(false);
    }
  }

  function downloadJson() {
    if (report) downloadReport("repomind-report.json", JSON.stringify(report, null, 2), "application/json");
  }

  function downloadMarkdown() {
    if (report) downloadReport("repomind-report.md", buildMarkdownReport(report), "text/markdown");
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#" aria-label="RepoMind AI home">
          <span className="brand-mark"><Icon>R</Icon></span>
          <span>repo<span className="brand-light">mind</span><small>AI</small></span>
        </a>
        <div className="topbar-note"><span className="status-dot" /> PUBLIC REPOS ONLY</div>
      </header>

      <main>
        <section className="hero">
          <div className="eyebrow"><span className="eyebrow-line" /> A CLEARER VIEW OF OPEN SOURCE</div>
          <h1>Know what’s inside<br />before you <em>trust it.</em></h1>
          <p className="hero-copy">
            Understand a public repository, check the signals, and choose whether AI should see any source.
            No GitHub account or token required.
          </p>

          <form className="analyze-card" onSubmit={handleAnalyze}>
            <label className="field-label" htmlFor="repo-url">PUBLIC REPOSITORY URL</label>
            <div className="url-field">
              <Icon>⌘</Icon>
              <input
                id="repo-url"
                type="url"
                placeholder="https://github.com/owner/repository"
                value={repositoryUrl}
                onChange={(event) => setRepositoryUrl(event.target.value)}
                autoComplete="url"
                required
              />
              <button className="analyze-button" type="submit" disabled={loading}>
                {loading ? <><span className="spinner" /> Inspecting</> : <>Analyze repository <span aria-hidden="true">↗</span></>}
              </button>
            </div>
            <div className="form-options">
              <label className="field-label" htmlFor="provider">AI ANALYSIS</label>
              <select
                id="provider"
                value={provider}
                onChange={(event) => {
                  setProvider(event.target.value as AiProvider);
                  setOnlineConsent(false);
                }}
              >
                <option value="none">No AI — scanners only</option>
                <option value="ollama">Local Ollama model</option>
                <option value="openai">Online OpenAI API</option>
                <option value="gemini">Online Google Gemini API</option>
              </select>
              <span className="privacy-pill"><Icon>◈</Icon> Private by default</span>
            </div>
            {provider === "ollama" && (
              <p className="provider-hint">Uses the Ollama model configured on the backend. For an open-source AI showcase, select an open-weight model; RepoMind does not verify model licenses. Source is sent to your local Ollama service.</p>
            )}
            {(provider === "openai" || provider === "gemini") && (
              <label className="consent">
                <input
                  type="checkbox"
                  checked={onlineConsent}
                  onChange={(event) => setOnlineConsent(event.target.checked)}
                />
                <span>
                  I consent to sending the selected public repository context to the configured{" "}
                  {provider === "gemini" ? "Google Gemini" : "OpenAI"} API for this analysis.
                </span>
              </label>
            )}
            <div className="trust-row">
              <span><Icon>✓</Icon> Read-only public API</span>
              <span><Icon>✓</Icon> No repository code execution</span>
              <span><Icon>✓</Icon> No AI unless selected</span>
            </div>
          </form>

          {error && <div className="error-banner" role="alert"><Icon>!</Icon>{error}</div>}
          {loading && <p className="loading-note" role="status">Reading repository metadata and supported files. This can take up to 60 seconds.</p>}
        </section>

        {report && <Results report={report} onDownloadJson={downloadJson} onDownloadMarkdown={downloadMarkdown} />}

        <section className="principles">
          <div className="principle">
            <span className="principle-icon">01</span>
            <h3>Clarity over certainty</h3>
            <p>Scanner evidence and AI hypotheses stay visibly separate. No green check means “guaranteed safe.”</p>
          </div>
          <div className="principle">
            <span className="principle-icon">02</span>
            <h3>Privacy is a choice</h3>
            <p>Start with no AI. Local models stay local to your configured Ollama service; online AI needs consent.</p>
          </div>
          <div className="principle">
            <span className="principle-icon">03</span>
            <h3>Built to be inspectable</h3>
            <p>Repository data comes from GitHub’s public API. Sensitive-looking files are excluded from AI context.</p>
          </div>
        </section>
      </main>

      <footer>
        <a className="brand footer-brand" href="#"><span className="brand-mark">R</span><span>repo<span className="brand-light">mind</span><small>AI</small></span></a>
        <span>Open source, inspectable by design.</span>
        <span>Analysis is a signal, not a security guarantee.</span>
      </footer>
    </div>
  );
}

function Results({
  report,
  onDownloadJson,
  onDownloadMarkdown,
}: {
  report: AnalysisReport;
  onDownloadJson: () => void;
  onDownloadMarkdown: () => void;
}) {
  const repository = report.repository;
  return (
    <section className="results" aria-label="Repository analysis results">
      <div className="result-heading">
        <div>
          <div className="eyebrow"><span className="eyebrow-line" /> ANALYSIS COMPLETE</div>
          <h2>{repository.full_name}</h2>
          <p>{repository.description ?? "No repository description provided."}</p>
        </div>
        <div className="export-buttons">
          <button onClick={onDownloadMarkdown} className="secondary-button">Export Markdown</button>
          <button onClick={onDownloadJson} className="secondary-button">Export JSON</button>
        </div>
      </div>
      <p className="status-callout"><Icon>i</Icon>{report.ai_status}</p>
      <div className="stat-grid">
        <Stat label="Stars" value={repository.stars.toLocaleString()} icon="☆" />
        <Stat label="Forks" value={repository.forks.toLocaleString()} icon="⑂" />
        <Stat label="Open issues" value={repository.open_issues.toLocaleString()} icon="○" />
        <Stat label="Default branch" value={repository.default_branch} icon="⌘" />
      </div>
      <div className="result-grid">
        <article className="panel">
          <div className="panel-title"><div><span className="panel-kicker">01 / STATIC CHECKS</span><h3>Security findings</h3></div><span className="count-badge">{report.findings.length}</span></div>
          {report.findings.length === 0 ? (
            <p className="empty-state">No findings from the scanners that ran. This is not a guarantee that the repository is secure.</p>
          ) : (
            <div className="finding-list">{report.findings.map((finding, index) => <Finding key={`${finding.source}-${finding.path}-${finding.line}-${index}`} finding={finding} />)}</div>
          )}
          <div className="panel-footnote">Bandit scans Python source. OSV checks exact-pinned Python requirements and supported npm lockfiles.</div>
        </article>
        <article className="panel">
          <div className="panel-title"><div><span className="panel-kicker">02 / DOCUMENTATION</span><h3>README quality</h3></div><span className="score">{report.readme_quality.score}<small>/100</small></span></div>
          <div className="check-list">
            {report.readme_quality.checks.map((check) => (
              <div className="check-item" key={check.name}>
                <span className={check.passed ? "check-icon passed" : "check-icon"}>{check.passed ? "✓" : "–"}</span>
                <span>{check.name}</span><span className="check-note">{check.passed ? "Found" : "Missing"}</span>
              </div>
            ))}
          </div>
          <div className="panel-footnote">A lightweight presence check only; it does not assess documentation accuracy.</div>
        </article>
        <article className="panel">
          <div className="panel-title"><div><span className="panel-kicker">03 / TECHNOLOGY</span><h3>Language mix</h3></div></div>
          {Object.keys(repository.languages).length === 0 ? <p className="empty-state">No language data returned.</p> : (
            <div className="language-list">{Object.entries(repository.languages).sort((a, b) => b[1] - a[1]).map(([name, bytes]) => {
              const total = Object.values(repository.languages).reduce((sum, value) => sum + value, 0) || 1;
              return <div className="language-row" key={name}><div><span>{name}</span><span>{Math.round(bytes / total * 100)}%</span></div><div className="language-track"><span style={{ width: `${Math.max(2, bytes / total * 100)}%` }} /></div></div>;
            })}</div>
          )}
          <div className="panel-footnote">{report.dependency_summary.scanned} pinned dependencies checked; {report.dependency_summary.vulnerabilities} OSV matches.</div>
        </article>
        <article className="panel">
          <div className="panel-title"><div><span className="panel-kicker">04 / REPOSITORY MAP</span><h3>Directory structure</h3></div><span className="count-badge">{repository.files.length}</span></div>
          <div className="file-list">{repository.files.slice(0, 24).map((path) => <div className="file-row" key={path}><span className="file-glyph">{path.includes(".") ? "·" : "/"}</span><code>{path}</code></div>)}</div>
          {repository.files_truncated && <div className="panel-footnote">Showing an abbreviated tree.</div>}
        </article>
        <article className="panel wide-panel">
          <div className="panel-title"><div><span className="panel-kicker">05 / AI ASSISTED</span><h3>Project understanding</h3></div><span className="ai-badge">{report.ai_summary?.provider ?? "Not run"}</span></div>
          {report.ai_summary ? (
            <>
              <h4 className="ai-section-heading">Project summary</h4>
              <p className="ai-copy">{report.ai_summary.summary}</p>
              <h4 className="ai-section-heading">Architecture explanation</h4>
              <p className="ai-copy">{report.ai_summary.architecture}</p>
              <p className="panel-footnote">{report.ai_summary.caveat} Model: {report.ai_summary.model}.</p>
            </>
          ) : <p className="empty-state">No AI analysis was run. Choose a provider above to request a summary.</p>}
        </article>
      </div>
      <div className="disclaimer"><Icon>!</Icon><div><strong>Read this before acting on a finding.</strong><span>Automated checks can miss issues or flag patterns that are safe in context. Review the evidence and remediation; no report guarantees security.</span></div></div>
      <div className="scanner-notes">
        <h3>Coverage &amp; limits</h3>
        <ul>{report.scanner_notes.map((note) => <li key={note}>{note}</li>)}</ul>
        {repository.github_rate_limit_remaining !== null && <p>Anonymous GitHub API requests remaining: {repository.github_rate_limit_remaining}.</p>}
        {repository.files_truncated && <p>The displayed path list is abbreviated to 500 entries.</p>}
      </div>
    </section>
  );
}

function Stat({ label, value, icon }: { label: string; value: string; icon: string }) {
  return <div className="stat-card"><span className="stat-icon">{icon}</span><span className="stat-value">{value}</span><span className="stat-label">{label}</span></div>;
}

function Finding({ finding }: { finding: SecurityFinding }) {
  return (
    <div className="finding">
      <div className="finding-top"><span className={`severity severity-${finding.severity.toLowerCase()}`}>{finding.severity}</span><span className="source-badge">{finding.source}</span><span className="confidence">{finding.confidence} confidence</span></div>
      <h4>{finding.title}</h4>
      <code className="finding-location">{finding.path}{finding.line === null ? "" : `:${finding.line}`}</code>
      <p>{finding.evidence}</p>
      <p className="remediation"><strong>Next step:</strong> {finding.remediation}</p>
    </div>
  );
}

export default App;
