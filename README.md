# RepoMind AI

## Project overview

RepoMind AI helps people understand and inspect public GitHub repositories before they trust, ship, or send repository context to an AI model. It combines transparent, bounded repository inspection with optional local or consent-gated AI analysis.

## Status

The first release implements:

- Public repository URL validation and anonymous GitHub REST API inspection.
- Repository metadata, language byte counts, README text, and a bounded file tree.
- Python static checks through Bandit, without executing repository code.
- Vulnerability lookups for exact-pinned `requirements*.txt` entries and `package-lock.json` package versions using the OSV batch API.
- A lightweight README section-presence checklist.
- No-AI mode by default, a local Ollama chat provider, and opt-in OpenAI and Google Gemini API providers.
- Evidence-labelled scanner findings and clearly caveated AI-generated summaries.
- JSON and Markdown report downloads.
- Optional AI-generated project summaries and architecture explanations returned as structured JSON; architecture statements are hypotheses to check against source, not verified diagrams.
- Responsive dashboard, API tests, and frontend URL/export tests.

This release does **not** statically scan JavaScript, TypeScript, or other non-Python source. It does not inspect every Python package manifest or every lockfile format. The README check looks for section keywords, not correctness or writing quality. The project tree and source file lists are capped. Unsupported or unpinned dependencies are reported as skipped. Features outside this list are not implemented.

## Architecture

```text
React + TypeScript (Vite)
          |
          | same-origin /api calls
          v
FastAPI backend
  | GitHub public REST API: repository, languages, README, tree, bounded files
  | Bandit: selected Python files, static-only
  | OSV batch API: exact-pinned supported dependencies
  | Provider interface
      | none (default)
      | Ollama (configured local model)
      | OpenAI API (explicit user consent)
      | Google Gemini API (explicit user consent)
```

Repository URLs are parsed as `https://github.com/{owner}/{repo}`. The backend constructs requests only to the fixed `api.github.com` origin; it does not follow redirects, clone repositories, accept arbitrary URLs, or execute downloaded content. GitHub read requests are anonymous and subject to GitHub's rate limits. OSV receives dependency names and versions, not repository source. Online AI is never selected by default; when selected, the UI requires explicit consent before sending the bounded repository context to OpenAI or Google Gemini.

## Requirements

- Python 3.11 or newer.
- Node.js 20 or newer and npm.
- Network access to GitHub's public REST API. Dependency checks also need access to `api.osv.dev`.
- Optional: Ollama installed on the same machine as the backend, with a model already pulled.
- Optional: an OpenAI API account and server-side API key. The online provider is not needed for no-AI or Ollama analysis.

## Local setup

From the repository root, open two terminals.

### Backend

```powershell
cd backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

If PowerShell blocks environment activation, use the virtual environment's interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite (normally `http://127.0.0.1:5173`). The Vite development server proxies `/api` requests to the local FastAPI backend.

## Deploy to Render

This repository uses two Render services: a **Python Web Service** for FastAPI and a **Static Site** for the Vite frontend. The API URL and browser CORS allowlist are configured separately so the production frontend calls only the backend you specify.

### 1. Push the deployment configuration

The frontend reads `VITE_API_BASE_URL` at build time. The backend reads `FRONTEND_ORIGINS` at startup. Commit and push these changes to `main` before creating deployments; Render builds from the GitHub repository, not from unpushed local files.

### 2. Create the FastAPI Web Service

In Render, choose **New → Web Service**, connect `appmaker3432/repomind-ai`, and configure:

| Setting | Value |
| --- | --- |
| Root Directory | `backend` |
| Runtime | Python |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/api/health` |

Add environment variables in the service settings:

| Key | Value |
| --- | --- |
| `FRONTEND_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` initially |
| `OLLAMA_BASE_URL` | Leave unset unless your deployment has an Ollama endpoint reachable by the backend |
| `OLLAMA_MODEL` | Leave unset until you have selected and tested a model |

Leave `OPENAI_API_KEY`, `GEMINI_API_KEY`, and their model settings unset unless you intend to use those providers. If enabled, add keys as secrets in Render's dashboard, never in GitHub. Render assigns the backend its own `onrender.com` URL after creation. Record that URL. The `/api/health` endpoint should return `{"status":"ok"}`.

### 3. Create the Vite Static Site

Choose **New → Static Site**, connect the same GitHub repository, and set:

| Setting | Value |
| --- | --- |
| Root Directory | `frontend` |
| Build Command | `npm ci && npm run build` |
| Publish Directory | `dist` |
| `VITE_API_BASE_URL` environment variable | The backend service origin from step 2, with no `/api` suffix, e.g. `https://your-api.onrender.com` |

After the first deploy, copy the Static Site's exact `https://...onrender.com` origin (scheme plus hostname, without a path). Add that exact origin to the backend's `FRONTEND_ORIGINS` value, keeping the two localhost origins if you also want local development, then redeploy the backend. Do not use a wildcard CORS origin.

### 4. Verify production behavior

Open the Static Site URL and analyze a public repository in **No AI — scanners only** mode. Confirm the browser can reach the API, results and exports load, invalid input shows an error, and the backend logs contain no secrets. If a browser CORS error appears, check that `FRONTEND_ORIGINS` exactly matches the Static Site origin and that `VITE_API_BASE_URL` points to the backend Web Service, then redeploy the changed service.

The Vite `/api` proxy is development-only. The production `VITE_API_BASE_URL` setting is required when the frontend and API are separate services. Deployment credit balances, eligible service types, and service pricing depend on the Render account; review Render's dashboard before selecting a paid instance or enabling autoscaling. Do not assume local Ollama is available inside a hosted backend: the configured Ollama endpoint must be reachable from Render, or leave AI disabled.

### Configure AI providers

Copy `backend/.env.example` to `backend/.env`. The application and dashboard work without an API key and default to **No AI**.

For Ollama, install Ollama, use its model library to choose a chat model, and set `OLLAMA_MODEL` to the exact name reported by your local Ollama installation:

```powershell
ollama list
```

If the model is not already present, pull the exact model name shown in the Ollama model library, then set `OLLAMA_MODEL` to the name shown by `ollama list`, restart the backend, and select **Local Ollama model** in the dashboard. For the Hacktoberfest open-source AI category, choose an open-source/open-weight model and verify its license yourself; RepoMind does not validate model licenses. RepoMind sends the selected context to the configured Ollama endpoint; by default that endpoint is `http://127.0.0.1:11434`. It does not send prompts to a model unless you choose that provider.

For OpenAI analysis, set `OPENAI_API_KEY` and `OPENAI_MODEL` in the backend environment, choose **Online OpenAI API**, and affirm the source-sharing consent checkbox for that analysis.

For Gemini analysis, set `GEMINI_API_KEY` and `GEMINI_MODEL` in the backend environment, choose **Online Google Gemini API**, and affirm the source-sharing consent checkbox for that analysis. Gemini calls use Google's native HTTPS API and structured JSON output; the API key is sent only in the server-to-server `x-goog-api-key` header and is never sent to the browser. Gemini is not accessed through an OpenAI-compatible endpoint. Rotate any API key that has been pasted into a chat, issue, or source file, then store its replacement only in the backend environment.

The provider interface is in `backend/app/providers/base.py`. This release implements Ollama's `/api/chat`, the OpenAI Python SDK's chat-completions call, and Google's native Gemini `generateContent` API. Each provider returns a summary and architecture explanation validated as structured JSON. Other online providers are **not implemented**; adding a provider requires a real adapter, tests, and documentation rather than assuming compatibility.

## Usage

1. Start the backend and frontend using the setup steps above.
2. Paste a public GitHub repository URL such as `https://github.com/owner/repository`.
3. Leave **No AI — scanners only** selected for metadata and supported scanner checks without any AI calls.
4. Optionally choose a configured Ollama model for local summaries, or choose a configured OpenAI/Gemini provider and give explicit consent before online source sharing.
5. Review each scanner finding, file location, evidence, remediation, README checklist, and the documented coverage limits.
6. Download a JSON or Markdown report from the results panel.

Private repositories, GitHub enterprise hosts, GitLab/Bitbucket projects, cloning, code execution, and unsupported scanners are not part of this release.

## Contributing

Contributions are welcome. Please open an issue describing the change, include tests for new analysis or security behavior, and update this README when feature coverage or privacy behavior changes. Never include credentials, private repository contents, or real API keys in issues, screenshots, fixtures, or pull requests.

## Privacy and security

- Normal public repository analysis requires no login, GitHub account connection, or GitHub personal access token.
- Only canonical HTTPS GitHub repository URLs are accepted. API requests use a fixed GitHub API host, disallow redirects, and never make arbitrary requests to a user-provided URL.
- The backend does not clone or execute repository contents. Bandit receives temporary source files as data, has a time limit, and runs only over fetched Python files.
- The analysis has a 60-second overall deadline, a 200 MB advertised-repository-size limit, a 5,000-entry tree limit, a 6 MB response-body limit for each GitHub API response, at most 25 fetched source files, at most 200 KB per source file, and a 4 MB total source-download cap.
- `.env`, credential/secret-named paths, common private-key files, and common local credential directories are excluded from source fetches. AI context also excludes likely secret assignment lines. These heuristics are imperfect: inspect a repository and its report before sharing source.
- AI mode defaults to off. Ollama context stays with the backend's configured Ollama service. OpenAI and Gemini analysis require explicit per-analysis consent and send bounded repository context to the selected online provider. Do not use online analysis for repositories or content you do not have permission to share.
- Dependency checks send supported package names and versions to OSV's public vulnerability service. The service is separate from AI providers.
- The local API has a small in-memory per-client rate limit. It is not a substitute for authentication, a durable distributed limiter, or a production deployment security review. The development server binds to loopback by default; do not expose it publicly without adding deployment-grade controls.
- Application secrets belong in the backend environment only. Keep `.env` files, API keys, and private repository content out of issues, reports, screenshots, and commits.

Static and dependency scanner findings are distinct from AI-generated hypotheses. A scanner match still needs human review, and an empty result never guarantees that a repository is secure. GitHub's anonymous API can be rate-limited; RepoMind reports when that happens instead of asking for a token.

## Tests

Backend, from `backend/`:

```powershell
python -m pytest
```

Frontend, from `frontend/`:

```powershell
npm test
npm run build
```

## License

MIT. See [LICENSE](LICENSE).
