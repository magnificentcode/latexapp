# app/services/compile_service.py

import asyncio
import logging
import shutil
import tempfile
from pathlib import Path

from app.core.config import TECTONIC_TIMEOUT_SECONDS
from app.services.latex_render import answer_html_to_tex

logger = logging.getLogger("latexapp.compile")


class CompileError(Exception):
    def __init__(self, message: str, log: str):
        super().__init__(message)
        self.log = log


class CompileTimeout(Exception):
    pass


def _tail(log: str, max_chars: int = 4000) -> str:
    # tectonic's actual error ("! ..." lines) is near the bottom; the top
    # is package-fetch chatter that isn't useful to the user.
    return log[-max_chars:]


async def compile_latex(answer_html: str) -> bytes:
    """Compiles a document's saved rich-text content with tectonic in an
    isolated temp dir. The stored `answer_html` (text + <br> + <img>
    equations/screenshots, as saved by the rich-text editor) is first
    converted into real LaTeX source — embedded images are decoded into
    the same temp dir so \\includegraphics can find them.

    Returns PDF bytes on success. Raises CompileError (with tectonic's log
    attached) on a LaTeX-level failure, CompileTimeout if it runs past
    TECTONIC_TIMEOUT_SECONDS.
    """
    tmpdir = Path(tempfile.mkdtemp(prefix="latexapp_compile_"))
    try:
        tex_source = answer_html_to_tex(answer_html, tmpdir)
        tex_path = tmpdir / "document.tex"
        tex_path.write_text(tex_source, encoding="utf-8")

        proc = await asyncio.create_subprocess_exec(
            "tectonic",
            "--outdir",
            str(tmpdir),
            str(tex_path),
            cwd=str(tmpdir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=TECTONIC_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise CompileTimeout()

        pdf_path = tmpdir / "document.pdf"
        if proc.returncode != 0 or not pdf_path.exists():
            log = (
                stdout.decode(errors="replace") + "\n" + stderr.decode(errors="replace")
            ).strip()
            raise CompileError("LaTeX compile failed", log=_tail(log))

        return pdf_path.read_bytes()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
