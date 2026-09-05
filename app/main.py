# app/main.py

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import ALLOWED_ORIGINS
from app.db.session import init_models
from app.middleware.auth import AuthMiddleware
from app.routes import auth, documents, health, pages
from app.routes import compile as compile_routes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("latexapp")

app = FastAPI(title="latexapp", description="Personal LaTeX editor", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Starlette runs last-added middleware outermost, so AuthMiddleware (added
# here) wraps every request, including the page-serving catch-all below.
app.add_middleware(AuthMiddleware)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(compile_routes.router)

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
