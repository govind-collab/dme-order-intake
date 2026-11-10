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
```

Settings come from environment variables. For local runs, copy `.env.example` to `.env` and fill it in by hand. `JWT_SECRET` needs 32+ characters: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

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
