# RepoMind

**Live app:** [repomind-ai-vert.vercel.app](https://repomind-ai-vert.vercel.app/)

## Project overview

RepoMind helps people understand and inspect public GitHub repositories before they trust or ship them. It uses deterministic, bounded repository inspection and static checks only. It does not use AI models or send source to AI providers.

## Status

The first release implements:

- Public repository URL validation and anonymous GitHub REST API inspection.
- Repository metadata, language byte counts, README text, and a bounded file tree.
- Python static checks through Bandit, without executing repository code.
- Vulnerability lookups for exact-pinned `requirements*.txt` entries and `package-lock.json` package versions using the OSV batch API.
- A lightweight README section-presence checklist.
- Evidence-labelled scanner findings and a source README preview.
- JSON and Markdown report downloads.
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
```

Repository URLs are parsed as `https://github.com/{owner}/{repo}`. The backend constructs requests only to the fixed `api.github.com` origin; it does not follow redirects, clone repositories, accept arbitrary URLs, or execute downloaded content. GitHub read requests are anonymous and subject to GitHub's rate limits. OSV receives supported dependency names and versions, not repository source. Analysis runs locally on the backend plus public GitHub and OSV APIs; there are no AI models, AI provider SDKs, or AI requests.

## Requirements

- Python 3.11 or newer.
- Node.js 20 or newer and npm.
- Network access to GitHub's public REST API. Dependency checks also need access to `api.osv.dev`.

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
3. No model or provider credentials are needed. Configure only application settings if your deployment requires them.
4. Wait for the deploy to finish, then verify `/api/health` returns `{"status":"ok"}` and analyze a public repository.

Do not deploy the frontend as a separate Static Site with this configuration: the intended setup serves it from the API service. If using a separate frontend deployment instead, it must set `VITE_API_BASE_URL` to the backend origin and the backend must allow that exact frontend origin in `FRONTEND_ORIGINS`.

Render's free service may spin down while idle, so the first request can take longer while it starts. Review Render's current plan limits and service availability before deploying.

## Deploy to Vercel

The root `pyproject.toml` configures Vercel's FastAPI entrypoint and frontend build command. The build creates `frontend/dist`; FastAPI serves those files and its `/api` endpoints from the same deployment.

1. In the Vercel project settings, set **Root Directory** to the repository root (not `frontend` or `backend`). Remove custom Build Command and Output Directory overrides so Vercel detects the FastAPI app, and remove any `VITE_API_BASE_URL` environment variable so the frontend uses the same-origin API.
2. Redeploy from the repository. Vercel installs Python packages listed through the root `requirements.txt` and builds the frontend using the script in `pyproject.toml`.
3. No model, provider API key, or AI-related environment variables are needed.
4. Verify `https://repomind-ai-vert.vercel.app/api/health` returns `{"status":"ok"}`, then analyze a public repository.

The Vercel project must deploy the repository root for its Python entrypoint and frontend build configuration to take effect. If the project remains rooted at `frontend`, Vercel will deploy only the static frontend and `/api/analyze` will continue to return 404.

## Usage

1. Start the backend and frontend using the setup steps above.
2. Paste a public GitHub repository URL such as `https://github.com/owner/repository`.
3. Run the scan; no model selection, API key, or source-sharing consent is needed.
4. Review each scanner finding, file location, evidence, remediation, README checklist, and the documented coverage limits.
5. Download a JSON or Markdown report from the results panel.

Private repositories, GitHub enterprise hosts, GitLab/Bitbucket projects, cloning, code execution, and unsupported scanners are not part of this release.

## Contributing

Contributions are welcome. Please open an issue describing the change, include tests for new analysis or security behavior, and update this README when feature coverage or privacy behavior changes. Never include credentials, private repository contents, or real API keys in issues, screenshots, fixtures, or pull requests.

## Privacy and security

- Normal public repository analysis requires no login, GitHub account connection, or GitHub personal access token.
- Only canonical HTTPS GitHub repository URLs are accepted. API requests use a fixed GitHub API host, disallow redirects, and never make arbitrary requests to a user-provided URL.
- The backend does not clone or execute repository contents. Bandit receives temporary source files as data, has a time limit, and runs only over fetched Python files.
- The analysis has a 60-second overall deadline, a 200 MB advertised-repository-size limit, a 5,000-entry tree limit, a 6 MB response-body limit for each GitHub API response, at most 25 fetched source files, at most 200 KB per source file, and a 4 MB total source-download cap.
- `.env`, credential/secret-named paths, common private-key files, and common local credential directories are excluded from source fetches. These heuristics are imperfect: inspect a repository and its report before sharing source.
- RepoMind has no AI model integration and never sends repository source to an AI provider.
- Dependency checks send supported package names and versions to OSV's public vulnerability service; source files are not sent to OSV.
- The local API has a small in-memory per-client rate limit. It is not a substitute for authentication, a durable distributed limiter, or a production deployment security review. The development server binds to loopback by default; do not expose it publicly without adding deployment-grade controls.
- Application secrets belong in the backend environment only. Keep `.env` files, API keys, and private repository content out of issues, reports, screenshots, and commits.

Static and dependency scanner findings are deterministic but limited: a scanner match still needs human review, and an empty result never guarantees that a repository is secure. GitHub's anonymous API can be rate-limited; RepoMind reports when that happens instead of asking for a token.

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
