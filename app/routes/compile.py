# app/routes/compile.py

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import TECTONIC_TIMEOUT_SECONDS
from app.core.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.routes.documents import _get_owned_document
from app.services.compile_service import CompileError, CompileTimeout, compile_latex

logger = logging.getLogger("latexapp.compile")
router = APIRouter(prefix="/api/documents", tags=["compile"])


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
