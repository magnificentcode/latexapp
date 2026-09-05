# app/routes/pages.py

import os

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

router = APIRouter()

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "static")


def _page_file(page: str) -> str | None:
    """Absolute path of static/<page>.html, or None if no such page.

    Guards against path traversal: the resolved file must stay inside
    STATIC_DIR (a request like /..%2Fapp%2Fmain could otherwise escape)."""
    candidate = os.path.abspath(os.path.join(STATIC_DIR, f"{page}.html"))
    if not candidate.startswith(os.path.abspath(STATIC_DIR) + os.sep):
        return None
    return candidate if os.path.isfile(candidate) else None


@router.get("/")
async def serve_root():
    return RedirectResponse(url="/dashboard", status_code=302)


@router.get("/{page}.html")
async def redirect_legacy_html(page: str):
    """Old bookmarked/indexed /x.html URLs permanently redirect to /x."""
    return RedirectResponse(url=f"/{page}", status_code=301)


@router.get("/{page}")
async def serve_page(page: str):
    """Clean-URL page serving: /login -> static/login.html, etc.

    Registered after every other router in app/main.py, so real API
    routes always win over this catch-all; it only sees single-segment
    GETs nothing else claimed."""
    path = _page_file(page)
    if path:
        return FileResponse(path, media_type="text/html")
    return JSONResponse(status_code=404, content={"error": "Page not found"})
