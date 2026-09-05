# latexapp

A personal LaTeX editor: sign in, keep your own homework/exercise documents,
get an instant math preview while typing, and compile to a real PDF on
demand.

## Stack

- **Backend**: FastAPI, SQLAlchemy (async) + asyncpg against Railway Postgres, own email/password auth (bcrypt + JWT in an httpOnly cookie).
- **Frontend**: plain HTML/CSS/JS for login/signup/dashboard, one Vite+React bundle for the editor (CodeMirror 6 for LaTeX source, KaTeX for the live math preview).
- **Compile**: [tectonic](https://tectonic-typesetting.github.io/), a self-contained LaTeX engine, run per-request in an isolated temp dir.

## Local development

Prerequisites:

```bash
brew install tectonic postgresql@16
```

Backend:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in DATABASE_URL and JWT_SECRET
```

Frontend (builds straight into `static/editor.bundle.{js,css}`):

```bash
cd frontend/latexeditor
npm install
npm run build   # or `npm run dev` won't work standalone — this app has no dev server split, always `build`
cd ../..
```

Run:

```bash
uvicorn app.main:app --reload --port 8080
```

Then visit `http://localhost:8080` (redirects to `/login`).

## Deploying to Railway

1. Create a Railway project, attach a **Postgres** plugin — it injects `DATABASE_URL` automatically.
2. Set `JWT_SECRET` (generate with `python -c "import secrets; print(secrets.token_hex(32))"`).
3. Deploy from this repo — `Dockerfile` builds the frontend bundle and installs tectonic in a multi-stage build; `Procfile`/`railway.json` start the app.
4. `ALLOWED_ORIGINS` can stay unset — the app is served same-origin (static pages + API on one FastAPI process), so there's no cross-origin frontend to allow.

## Notes / known limitations (v1, personal-scale tradeoffs)

- No Alembic — schema is created via `Base.metadata.create_all` on startup. If columns change later, migrate by hand or introduce Alembic then.
- Signup is open (no invite codes, no email verification) — anyone who finds the URL can create an account.
- The live preview is a lightweight KaTeX-based approximation (math renders live, plain text/commands don't) — it is not a full LaTeX engine. Use "Compile to PDF" for the real, complete render.
- tectonic's package cache lives at `/var/cache/latexapp` inside the container and does **not** persist across redeploys (no volume attached). To avoid paying tectonic's ~55s bootstrap-bundle download on every fresh container, the Dockerfile pre-warms the cache at *build time* with a small document using common packages (amsmath, amssymb, graphicx) — so a normal first compile after deploy is fast; only a document using packages outside that warm set pays a one-time slower download.
