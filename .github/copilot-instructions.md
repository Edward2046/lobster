# Copilot instructions for Lobster

## Build, test, and lint commands

### Python backend

- Install deps: `python -m pip install -r requirements.txt`
- Start the backend HTTP service plus the in-process scheduler: `python main.py`
- Start the backend on a custom port: `python main.py --port 8765`
- Run one scheduled job immediately:
  - `python main.py --now finance`
  - `python main.py --now food`
  - `python main.py --now earnings`
  - `python main.py --now all`
- Run the standalone CLI agent instead of the HTTP server: `python service/agent.py "东京现在几点？"`

### Frontend

- Install deps: `cd web && npm install`
- Start the Vite dev server: `cd web && npm run dev`
- Build the frontend: `cd web && npm run build`
- Preview the production build: `cd web && npm run preview`

### Tests and linting

- There are currently no automated test commands in the repository.
- There are currently no lint scripts or dedicated formatter commands in the repository.
- There is no repo-supported single-test command yet because no test suite is configured.

## High-level architecture

- `main.py` is the real application entrypoint. It loads `.env`, configures logging to stdout plus `lobster.log`, starts the scheduler on a background thread, and runs the HTTP API on the main thread.
- `service/server.py` exposes the backend API:
  - `POST /api/ask` accepts `{ "question": "..." }`
  - `GET /health` returns `{ "status": "ok" }`
- The backend agent is created lazily in `service/server.py:get_agent()` so importing the server does not initialize the model immediately.
- The HTTP agent and the CLI agent both use `smolagents.CodeAgent`, but they are configured in different files:
  - `service/server.py` is the web/API path
  - `service/agent.py` is the local CLI path
- `service/tools/` contains the tool surface the agent can call. These tools fetch external data and return formatted strings for the agent to use:
  - time and calculator utilities
  - weather lookup via Open-Meteo
  - financial news via Investing RSS
  - earnings calendar via Nasdaq API
  - food trend aggregation via RSS feeds
- `service/cron/` contains scheduled report builders and notification senders. The report builders reuse the same lower-level tool functions instead of reimplementing the data fetch logic.
- The frontend in `web/` is a small Vite + React chat client. It posts to `/api/ask`, and `web/vite.config.ts` proxies `/api` to `http://localhost:8765`, which matches the backend default port in `main.py`.

## Key conventions

- When adding or removing agent tools, keep the tool list aligned in three places:
  - the concrete tool module in `service/tools/`
  - the export list in `service/tools/__init__.py`
  - both `CodeAgent` registrations in `service/agent.py` and `service/server.py`
- Tool functions are designed to return user-readable strings on invalid input or upstream request failures instead of raising. Follow that pattern so the agent can recover from bad parameters and still produce an answer.
- Scheduled jobs are wired centrally in `main.py`. If you add a new scheduled report, update the task function, scheduler checks, and `_TASK_MAP` so both timed execution and `--now` execution stay consistent.
- User-facing product copy is primarily Chinese. Keep report titles, scheduler messages, frontend status text, and notification content in Chinese unless the surrounding file already uses English for a specific API-facing reason.
- The frontend message model is role-driven (`user | agent | error | loading`). Keep new chat UI behavior compatible with that role flow; the loading placeholder is removed by filtering out messages with the `loading` role when a response arrives.
- The frontend assumes backend responses are plain text answers inside `{ "answer": "..." }`, not structured tool output. Preserve that contract unless you update both the API handler and the React rendering path together.
- Backend startup is intentionally lightweight on import. Preserve lazy initialization in `service/server.py` rather than moving model creation to module import time.

## Required environment variables

- `DEEPSEEK_API_KEY`
- `WXPUSHER_APP_TOKEN`
- `WXPUSHER_UID`
- `FEISHU_WEBHOOK`
