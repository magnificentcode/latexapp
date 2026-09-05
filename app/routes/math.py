# app/routes/math.py

import io
import logging
import urllib.parse

from fastapi import APIRouter, Query
from fastapi.responses import Response
from matplotlib.backends.backend_svg import FigureCanvasSVG
from matplotlib.figure import Figure

router = APIRouter()
logger = logging.getLogger("latexapp.math")


def _render_mathtext_svg(latex: str) -> bytes:
    """Renders LaTeX math notation to SVG using matplotlib's mathtext —
    covers common notation (\\cdot, \\frac, \\sqrt, ^, _, Greek letters,
    etc.) without needing a full LaTeX installation. Figure size is a
    placeholder; bbox_inches='tight' on save crops to the actual rendered
    content regardless."""
    fig = Figure(figsize=(0.01, 0.01))
    FigureCanvasSVG(fig)
    fig.text(0, 0, f"${latex}$", fontsize=18)
    buf = io.BytesIO()
    fig.savefig(buf, format="svg", transparent=True, bbox_inches="tight", pad_inches=0.05)
    return buf.getvalue()


def _fallback_svg(text: str) -> bytes:
    """Shown when mathtext can't parse the expression (e.g. \\begin{matrix}
    environments it doesn't support) — the raw source in a plain box, so a
    malformed equation never comes back as a broken <img>, just a
    visibly-degraded one."""
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="220" height="36" viewBox="0 0 220 36">
  <rect width="220" height="36" fill="#fdecea" stroke="#f5c2c0" stroke-width="1"/>
  <text x="8" y="23" font-family="monospace" font-size="13" fill="#8a3330">{escaped}</text>
</svg>'''
    return svg.encode()


@router.get("/math.svg")
async def math_svg(latex: str = Query(...)):
    """Renders a LaTeX math expression as an SVG image, requested by the
    Digabi rich-text-editor's inline equation feature (static/editor.html)."""
    decoded_latex = urllib.parse.unquote(latex)

    try:
        svg_bytes = _render_mathtext_svg(decoded_latex)
    except Exception as e:
        logger.warning("mathtext render failed for %r: %s", decoded_latex, str(e))
        svg_bytes = _fallback_svg(decoded_latex)

    return Response(
        content=svg_bytes,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )
