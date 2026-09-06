# app/routes/compile.py

import io
import logging
import re
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import TECTONIC_TIMEOUT_SECONDS
from app.core.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.routes.documents import _get_owned_document
from app.services.compile_service import CompileError, CompileTimeout, compile_latex
from app.services.latex_render import answer_html_to_tex

logger = logging.getLogger("latexapp.compile")
router = APIRouter(prefix="/api/documents", tags=["compile"])


def _safe_filename(title: str, fallback: str = "document") -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", title or "").strip("_")
    return name or fallback


@router.post("/{document_id}/compile")
async def compile_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = await _get_owned_document(db, current_user, document_id)

    try:
        pdf_bytes = await compile_latex(document.content)
    except CompileError as exc:
        return JSONResponse(
            status_code=422,
            content={"detail": "LaTeX compile failed", "log": exc.log},
        )
    except CompileTimeout:
        raise HTTPException(
            status_code=504, detail=f"Compile timed out after {TECTONIC_TIMEOUT_SECONDS}s"
        )
    except FileNotFoundError:
        logger.error("tectonic binary not found on PATH")
        raise HTTPException(status_code=500, detail="Internal compile error")
    except Exception:
        logger.exception("Unexpected compile error for document %s", document_id)
        raise HTTPException(status_code=500, detail="Internal compile error")

    return Response(content=pdf_bytes, media_type="application/pdf")


@router.get("/{document_id}/export")
async def export_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Downloads the document as real LaTeX source — the same conversion
    Compile-to-PDF uses — so it can be opened and edited in Overleaf,
    TeXShop, VS Code, or any other LaTeX tool. Plain .tex when there are
    no embedded images; a .zip bundling document.tex with them otherwise,
    so \\includegraphics references still resolve elsewhere.
    """
    document = await _get_owned_document(db, current_user, document_id)

    tmpdir = Path(tempfile.mkdtemp(prefix="latexapp_export_"))
    try:
        tex_source = answer_html_to_tex(document.content, tmpdir)
        image_files = list(tmpdir.iterdir())
        base_name = _safe_filename(document.title)

        if not image_files:
            return Response(
                content=tex_source.encode("utf-8"),
                media_type="application/x-tex",
                headers={"Content-Disposition": f'attachment; filename="{base_name}.tex"'},
            )

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("document.tex", tex_source)
            for image_path in image_files:
                zf.write(image_path, arcname=image_path.name)

        return Response(
            content=buf.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{base_name}.zip"'},
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
