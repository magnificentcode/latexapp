# latexapp

A personal LaTeX editor: sign in, keep your own homework/exercise documents,
write with the same rich-text + equation editor used in the Finnish
matriculation exam system, and compile to a real PDF on demand.

## Stack

- **Backend**: FastAPI, SQLAlchemy (async) + asyncpg against Railway Postgres, own email/password auth (bcrypt + JWT in an httpOnly cookie).
- **Editor**: [Digabi's `rich-text-editor`](https://github.com/digabi/rich-text-editor) (loaded from its CDN bundle, same as it's used in Abibotti) — a contenteditable answer area with an equation editor (MathQuill + raw LaTeX side by side), a special-character toolbar, its own undo/redo, and clipboard image paste. No frontend build step: it's a `<script type="module">` tag plus a small vanilla-JS file ([static/js/editor.js](static/js/editor.js)) that wires it to the API.
- **Math preview**: equations render inline as SVG via matplotlib's mathtext (`/math.svg`, ported from Abibotti) as you type — no LaTeX install needed for that.
- **Compile**: on "Compile to PDF", the saved rich-text content is converted into real LaTeX source ([app/services/latex_render.py](app/services/latex_render.py) — text escaped, `<br>` → line breaks, equation `<img>`s → `$...$`, pasted images → `\includegraphics`) and compiled with [tectonic](https://tectonic-typesetting.github.io/), a self-contained LaTeX engine, per-request in an isolated temp dir.

## Local development

Prerequisites:

```bash
brew install tectonic postgresql@16
```

Backend (no Node/npm needed — the editor loads from a CDN at runtime):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in DATABASE_URL and JWT_SECRET
uvicorn app.main:app --reload --port 8080
```

Then visit `http://localhost:8080` (redirects to `/login`).

## Deploying to Railway

1. Create a Railway project, attach a **Postgres** plugin — it injects `DATABASE_URL` automatically.
2. Set `JWT_SECRET` (generate with `python -c "import secrets; print(secrets.token_hex(32))"`).
3. Make sure the service is configured to build from the **Dockerfile** (Railway's auto-detect builder doesn't know about tectonic) — see the Dockerfile's tectonic install + cache pre-warm steps.
4. `ALLOWED_ORIGINS` can stay unset — the app is served same-origin (static pages + API on one FastAPI process), so there's no cross-origin frontend to allow.

## Notes / known limitations (v1, personal-scale tradeoffs)

- No Alembic — schema is created via `Base.metadata.create_all` on startup. If columns change later, migrate by hand or introduce Alembic then.
- Signup is open (no invite codes, no email verification) — anyone who finds the URL can create an account.
- The editor's UI strings (toolbar/help dialog) ship only in Finnish/Swedish upstream — [editor.js](static/js/editor.js) does a small text-relabeling pass to English for the known strings after the editor mounts.
- Pasted screenshots are stored as inline base64 `data:` URLs in the document's saved HTML (the package's default paste behavior) — fine at personal scale, but large/many images will bloat the row in Postgres. A real upload endpoint (`getPasteSource`) could replace this later if it becomes a problem.
- tectonic's package cache lives at `/var/cache/latexapp` inside the container and does **not** persist across redeploys (no volume attached). To avoid paying tectonic's ~55s bootstrap-bundle download on every fresh container, the Dockerfile pre-warms the cache at *build time* with a small document using common packages (amsmath, amssymb, graphicx) — so a normal first compile after deploy is fast; only a document using packages outside that warm set pays a one-time slower download.
