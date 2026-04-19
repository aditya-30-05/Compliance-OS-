"""
Document upload and processing routes.
Handles PDF, DOCX, TXT file upload → extraction → AI analysis → vector embedding.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
import os
import time
from sqlalchemy import select, desc
from typing import Optional

from backend.db.session import get_db
from backend.auth.dependencies import get_current_user, get_optional_user
from backend.models.user import User
from backend.models.document import Document
from backend.models.base import generate_uuid
from backend.services.document_processor import validate_file, save_uploaded_file, extract_text
from backend.services.ai_engine import run_ai_pipeline
from backend.services.vector_service import embed_document
from backend.utils.rate_limiter import ai_limiter
from backend.utils.malware_scanner import scan_file
from backend.utils.logger import logger

router = APIRouter(prefix="/api/documents", tags=["Documents"])


@router.post("/upload")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    industry: str = Form(default="banking"),
    company_name: str = Form(default="Organization"),
    auto_analyze: bool = Form(default=True),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    Upload document → extract text → optionally analyze → embed in vector DB.
    Works for both authenticated and anonymous users.
    """
    ai_limiter.check(request)

    # Read file
    content = await file.read()

    # Validate
    is_valid, error_msg = validate_file(file.filename or "unnamed", len(content))
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    # Save to disk
    stored_path, file_type = save_uploaded_file(content, file.filename or "unnamed")

    # Malware Scan
    if not scan_file(stored_path):
        os.remove(stored_path)  # Cleanup
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="File security scan failed. Potential threat detected."
        )

    # Extract text
    extracted_text, page_count = extract_text(stored_path, file_type)
    if not extracted_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not extract text from the uploaded file. Ensure it contains readable text."
        )

    doc_id = generate_uuid()

    # Persist document record for authenticated users
    if current_user:
        try:
            doc = Document(
                id=doc_id,
                tenant_id=current_user.tenant_id,
                user_id=current_user.id,
                filename=file.filename or "unnamed",
                file_type=file_type,
                file_size_bytes=len(content),
                stored_path=stored_path,
                extracted_text=extracted_text[:10000],  # Store first 10K chars
                page_count=page_count,
            )
            db.add(doc)
            await db.commit()
        except Exception as e:
            logger.error(f"Document save error: {e}")

    # Embed in vector DB
    try:
        metadata = {"type": "document", "file_type": file_type, "industry": industry}
        if current_user:
            metadata["tenant_id"] = current_user.tenant_id
        await embed_document(extracted_text, doc_id, collection_name="regulations", metadata=metadata)
    except Exception as e:
        logger.warning(f"Vector embedding skipped: {e}")

    response = {
        "status": "success",
        "document_id": doc_id,
        "filename": file.filename,
        "file_type": file_type,
        "page_count": page_count,
        "text_length": len(extracted_text),
        "text_preview": extracted_text[:500],
    }

    # Optionally run AI analysis on extracted text
    if auto_analyze and extracted_text:
        try:
            report = await run_ai_pipeline(extracted_text[:10000], industry, company_name)
            response["analysis"] = report
        except Exception as e:
            logger.warning(f"Auto-analysis skipped: {e}")

    return response


@router.get("/")
async def list_documents(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """List uploaded documents for the current tenant."""
    if not current_user:
        return {"documents": [], "total": 0}

    result = await db.execute(
        select(Document)
        .where(Document.tenant_id == current_user.tenant_id)
        .order_by(desc(Document.created_at))
        .limit(50)
    )
    docs = result.scalars().all()

    return {
        "documents": [
            {
                "id": d.id,
                "filename": d.filename,
                "file_type": d.file_type,
                "page_count": d.page_count,
                "file_size_bytes": d.file_size_bytes,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in docs
        ],
        "total": len(docs),
    }
