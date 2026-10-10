# RepoMind AI

**Live app:** [repomind-ai-vert.vercel.app](https://repomind-ai-vert.vercel.app/)

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

The included `render.yaml` and `Dockerfile` deploy the Vite frontend and FastAPI backend as **one web service**. The backend serves the built frontend and the `/api` routes from the same origin, so production does not depend on a separately configured `VITE_API_BASE_URL`, a manually copied backend URL, or a production CORS allowlist. The Vite proxy remains available for local development.

1. Push the repository, including `render.yaml` and `Dockerfile`, to GitHub.
2. In Render, choose **New → Blueprint**, connect the repository, and apply the `repomind-ai` service described by `render.yaml`.
3. When prompted for environment variables, add an OpenAI API key and model if you want online OpenAI analysis, or a Gemini key and model for Gemini. These settings are optional; no-AI analysis works without provider credentials. Keep provider keys in Render's secret environment settings, never in source control. Ollama is optional and only works when its configured URL is reachable from the deployed service.
4. Wait for the deploy to finish, then verify `/api/health` returns `{"status":"ok"}` and analyze a public repository with **No AI — scanners only**. Online providers additionally require a valid provider key and model configured on the service.

Do not deploy the frontend as a separate Static Site with this configuration: the intended setup serves it from the API service. If using a separate frontend deployment instead, it must set `VITE_API_BASE_URL` to the backend origin and the backend must allow that exact frontend origin in `FRONTEND_ORIGINS`.

Render's free service may spin down while idle, so the first request can take longer while it starts. Review Render's current plan limits and service availability before deploying.

## Deploy to Vercel

The repository root includes a Vercel FastAPI entrypoint configuration and build script. This builds the Vite app, then deploys the frontend and FastAPI API routes together so the live site's relative `/api/analyze` request reaches the backend on the same origin.

1. In the Vercel project settings, set **Root Directory** to the repository root (not `frontend` or `backend`). Remove any custom Build Command or Output Directory overrides so Vercel can use `pyproject.toml`, and remove any `VITE_API_BASE_URL` environment variable so the frontend uses the same-origin API.
2. Redeploy from the repository. Vercel installs Python packages listed through the root `requirements.txt` and builds the frontend using the script in `pyproject.toml`.
3. Add provider environment variables in Vercel's project settings only if needed: `OPENAI_API_KEY` and `OPENAI_MODEL`, or `GEMINI_API_KEY` and `GEMINI_MODEL`. No-AI analysis works without these keys. Do not store API keys in the frontend or commit them.
4. Verify `https://repomind-ai-vert.vercel.app/api/health` returns `{"status":"ok"}`, then try an analysis in **No AI — scanners only** mode.

The Vercel project must deploy the repository root for its Python entrypoint and shared frontend build configuration to take effect. If the project remains rooted at `frontend`, Vercel will deploy only the static frontend and `/api/analyze` will continue to return 404.

### Configure AI providers

Copy `backend/.env.example` to `backend/.env`. The application and dashboard work without an API key and default to **No AI**.

For Ollama, install Ollama, use its model library to choose a chat model, and set `OLLAMA_MODEL` to the exact name reported by your local Ollama installation:

```powershell
ollama list
```

If the model is not already present, pull the exact model name shown in the Ollama model library, then set `OLLAMA_MODEL` to the name shown by `ollama list`, restart the backend, and select **Local Ollama model** in the dashboard. For the Hacktoberfest open-source AI category, choose an open-source/open-weight model and verify its license yourself; RepoMind does not validate model licenses. RepoMind sends the selected context to the configured Ollama endpoint; by default that endpoint is `http://127.0.0.1:11434`. It does not send prompts to a model unless you choose that provider.

For OpenAI analysis, choose **Online OpenAI API**, enter your key and model, and affirm the source-sharing consent checkbox. Keys are sent to the app backend only for that request, are not saved by RepoMind, and are cleared from the form when it finishes. Because the backend receives the key, only enter it on an app deployment you trust. Self-hosters may instead configure `OPENAI_API_KEY` and `OPENAI_MODEL` on their server.

For Gemini analysis, choose **Online Google Gemini API**, enter your key and model, and affirm the source-sharing consent checkbox. Gemini calls use Google's native HTTPS API and structured JSON output; the key is sent to Google only in the server-to-server `x-goog-api-key` header. Self-hosters may instead configure `GEMINI_API_KEY` and `GEMINI_MODEL` on their server. Rotate any key accidentally pasted into a chat, issue, or source file.

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
