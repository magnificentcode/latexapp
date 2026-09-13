# app/main.py

import logging
import os

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import ALLOWED_ORIGINS
from app.db.session import init_models
from app.middleware.auth import AuthMiddleware
from app.routes import auth, documents, health, math, pages
from app.routes import compile as compile_routes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("latexapp")

app = FastAPI(title="latexapp", description="Personal LaTeX editor", version="1.0.0")

# Only mount CORS when an explicit allowlist is configured. With
# allow_credentials=True, Starlette's CORSMiddleware reflects the request's
# actual Origin header instead of a literal "*" (browsers reject wildcard
# origin + credentials otherwise) — falling back to ["*"] here would silently
# let any website make authenticated requests using the visitor's session
# cookie. The app is served same-origin (see README), so no CORS at all is
# the correct default; set ALLOWED_ORIGINS only if a separate frontend
# origin genuinely needs credentialed cross-origin access.
if ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Starlette runs last-added middleware outermost, so AuthMiddleware (added
# here) wraps every request, including the page-serving catch-all below.
app.add_middleware(AuthMiddleware)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # FastAPI's default handler echoes the rejected value back in each
    # error's "input" field. That's fine for a typo'd email, but the
    # document-content size-limit validator (see app/models/document.py)
    # can reject a payload tens of megabytes large — echoing it back would
    # turn a 10MB "too big to save" request into a 10MB+ response too,
    # doubling the bandwidth wasted on the exact request being rejected.
    errors = [{k: v for k, v in error.items() if k != "input"} for error in exc.errors()]
    return JSONResponse(status_code=422, content=jsonable_encoder({"detail": errors}))


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(compile_routes.router)
app.include_router(math.router)

# Registered last on purpose: it has a catch-all GET /{page} route that
# would otherwise shadow every other GET route declared after it.
app.include_router(pages.router)


@app.on_event("startup")
async def on_startup():
    await init_models()
    logger.info("latexapp started")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8080, reload=True)
