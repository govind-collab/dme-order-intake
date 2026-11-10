# AGENTS.md

REST API that turns faxed DME order PDFs into orders. A FastAPI service extracts patient and provider fields with the Claude API, checks them, and stores orders per user. The design and build plan are in [docs/design.md](docs/design.md).

## Commands

Python 3.13. From the repo root:

```bash
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload     # http://127.0.0.1:8000/docs
pytest
ruff check .
ruff format --check .             # `ruff format .` fixes it
alembic revision --autogenerate -m "Describe the change"   # after changing app/models.py
```

Migrations run when the app starts. A database made before migrations existed is stamped at `0001` instead of being created again.

Settings come from environment variables. For local runs, copy `.env.example` to `.env` and fill it in by hand. `JWT_SECRET` needs 32+ characters: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

Frontend (React, TypeScript, Vite, Node 24), from `frontend/`: `npm ci`, `npm run dev` (talks to the API at `VITE_API_URL`, default `http://127.0.0.1:8000`; set the API's `FRONTEND_ORIGIN=http://localhost:5173` for CORS), `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`.

## Code rules

- Small functions that do one thing. Names say what the thing is.
- The simplest code that works: no extra layers, no helper used only once, no dead code, no loop inside a loop when a dict or set lookup does it.
- Type hints everywhere.
- Every module and function has a docstring; ruff enforces it (`D`, numpy convention). A module docstring says in one line what the module is for, then what it owns. A function docstring opens with one line saying what it does or returns, starting with a verb such as Return or Parse. Add a short paragraph only for what the signature can't show: what it raises, what it returns on failure, why it works that way. Add a Parameters section only when a parameter's meaning isn't clear from its name and type. Never restate types.
- Route docstrings are the endpoint descriptions in /docs, so write them for someone calling the API.
- Inline comments only for the why. No comment that repeats the line, no big comment blocks.
- Routes stay thin and logic lives in services. The Claude API call lives in one file so tests can fake it.
- Column types stay portable: SQLite locally and in tests, Postgres on Render, both through `DATABASE_URL`.
- Change only what the current step needs. Ask before adding anything the plan doesn't have.
- Every step ends with ruff and pytest passing, then a commit with a plain one-line message and no trailers, then a push.
- Frontend: the same ideas apply. No UI library, plain CSS, no `any`. All API calls go through the typed client in `src/api.ts`; components stay small. A TSDoc comment above every exported component, hook and function says what it does, and props are documented on the props type where the name isn't enough. Vitest covers the parts with logic, not the markup. Lint, typecheck, tests and build pass before a commit.

## Security and data rules

- PDFs are never committed, logged or stored. `*.pdf` is gitignored. Uploads are read in memory, never written to disk, and dropped after extraction.
- Logs carry ids, statuses and timings only. Never field values, filenames, document text or model output.
- Error responses never echo input. Strip `input` from validation errors.
- Every string field has a max length and list endpoints cap the page size. Bad input gets a 4xx, never a 500.
- Every order query filters by owner. Another user's order returns 404.
- A value that fails a check is never stored on the order. The value as read and the reason go in the field report.
- The model's reply is validated by a strict pydantic model. A mismatch is a model error (502), never a half-filled order.
- Secrets live only in env vars: `.env` locally, the Render dashboard in production. Never read `.env`. Never put a secret in code, commits, logs or chat.
- Passwords are hashed with argon2. JWTs expire after 60 minutes.
- This deployment takes synthetic data only. There is no BAA with Render or Anthropic.
- The frontend keeps the token in memory only. Nothing with patient data goes in localStorage, sessionStorage or the console (ESLint forbids `console`). The API allows only `FRONTEND_ORIGIN` through CORS.
