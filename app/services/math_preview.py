# app/services/math_preview.py

import asyncio
import shutil
import tempfile
from pathlib import Path

# `standalone` + `preview` auto-crop the compiled page to the rendered
# math's own bounding box, so the result is a tight equation image
# instead of a full sheet of paper with the equation somewhere on it.
_PREVIEW_PREAMBLE = (
    "\\documentclass[preview,border=1pt]{standalone}\n"
    "\\usepackage{amsmath,amssymb}\n"
    "\\begin{document}\n"
    "$"
)
_PREVIEW_POSTAMBLE = "$\n\\end{document}\n"

_RENDER_TIMEOUT_SECONDS = 10


class PreviewRenderError(Exception):
    pass


async def render_latex_preview_svg(latex: str) -> bytes:
    """Renders a math snippet through the real LaTeX engine (the same one
    Compile-to-PDF uses), not a simplified approximation — so the live
    preview handles anything real LaTeX does (cases, matrices, aligned
    systems, ...) and matches the final PDF's math rendering exactly,
    instead of a client-side-only preview's necessarily narrower support.

    Raises PreviewRenderError (caller falls back to a plain error SVG) if
    the snippet doesn't compile or the run times out.
    """
    tmpdir = Path(tempfile.mkdtemp(prefix="latexapp_mathpreview_"))
    try:
        tex_path = tmpdir / "eq.tex"
        tex_path.write_text(_PREVIEW_PREAMBLE + latex + _PREVIEW_POSTAMBLE, encoding="utf-8")

        proc = await asyncio.create_subprocess_exec(
            "tectonic",
            "--outdir",
            str(tmpdir),
            # This renders arbitrary, untrusted, user-supplied LaTeX —
            # disable shell-escape and other known-insecure engine
            # features rather than trusting the input.
            "--untrusted",
            str(tex_path),
            cwd=str(tmpdir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            await asyncio.wait_for(proc.communicate(), timeout=_RENDER_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise PreviewRenderError("timed out")

        pdf_path = tmpdir / "eq.pdf"
        if proc.returncode != 0 or not pdf_path.exists():
            raise PreviewRenderError("tectonic compile failed")

        svg_path = tmpdir / "eq.svg"
        convert = await asyncio.create_subprocess_exec(
            "pdftocairo",
            "-svg",
            str(pdf_path),
            str(svg_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(convert.communicate(), timeout=_RENDER_TIMEOUT_SECONDS)
        if convert.returncode != 0 or not svg_path.exists():
            raise PreviewRenderError("pdf-to-svg conversion failed")

        return svg_path.read_bytes()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
