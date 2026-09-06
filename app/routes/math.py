# app/routes/math.py

import logging
import urllib.parse

from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.services.math_preview import PreviewRenderError, render_latex_preview_svg

router = APIRouter()
logger = logging.getLogger("latexapp.math")


def _fallback_svg(text: str) -> bytes:
    """Shown when the snippet doesn't compile (often because the user is
    still mid-edit, e.g. an unclosed brace) — the raw source in a plain
    box, so a malformed equation never comes back as a broken <img>, just
    a visibly-degraded one."""
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="220" height="36" viewBox="0 0 220 36">
  <rect width="220" height="36" fill="#fdecea" stroke="#f5c2c0" stroke-width="1"/>
  <text x="8" y="23" font-family="monospace" font-size="13" fill="#8a3330">{escaped}</text>
</svg>'''
    return svg.encode()


@router.get("/math.svg")
async def math_svg(latex: str = Query(...)):
    """Renders a LaTeX math expression as an SVG image via the real LaTeX
    engine (tectonic) — requested by the Digabi rich-text-editor's inline
    equation feature (static/editor.html). Using the same engine
    Compile-to-PDF does means the live preview handles anything real
    LaTeX does (cases, matrices, ...) and matches the final PDF exactly,
    rather than a simplified approximation with its own gaps."""
    decoded_latex = urllib.parse.unquote(latex)

    try:
        svg_bytes = await render_latex_preview_svg(decoded_latex)
    except PreviewRenderError as e:
        logger.info("math preview render failed for %r: %s", decoded_latex, str(e))
        svg_bytes = _fallback_svg(decoded_latex)
    except Exception as e:
        logger.warning("unexpected math preview error for %r: %s", decoded_latex, str(e))
        svg_bytes = _fallback_svg(decoded_latex)

    return Response(
        content=svg_bytes,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )
