from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.knowledge_repository import KnowledgeDocumentRepository
from app.schemas.knowledge import (
    KnowledgeChunkOut,
    KnowledgeDocumentOut,
    ParsedDocumentOut,
    ParsedSectionOut,
)
from app.schemas.response import success
from app.services.document_chunker import DocumentChunker
from app.services.document_parser import DocumentParser, DocumentParserError
from app.services.knowledge_index_service import KnowledgeIndexService
from app.services.knowledge_upload_service import KnowledgeUploadError, KnowledgeUploadService

router = APIRouter(prefix="/api/admin/knowledge", tags=["knowledge"])


@router.post("/upload")
def upload_knowledge_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    try:
        document = KnowledgeUploadService(db).save_upload(file)
    except KnowledgeUploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success(KnowledgeDocumentOut.model_validate(document).model_dump())


@router.get("")
def list_knowledge_documents(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    documents = KnowledgeDocumentRepository(db).list(limit=limit, offset=offset)
    return success([KnowledgeDocumentOut.model_validate(item).model_dump() for item in documents])


@router.get("/{document_id}/parse-preview")
def parse_knowledge_document_preview(
    document_id: int,
    db: Session = Depends(get_db),
):
    repository = KnowledgeDocumentRepository(db)
    document = repository.get(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="知识文档不存在")
    if not document.file_path:
        raise HTTPException(status_code=400, detail="知识文档缺少文件路径")

    try:
        parsed = DocumentParser().parse(document.file_path)
    except DocumentParserError as exc:
        repository.mark_parse_failed(document, str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    sections = [
        ParsedSectionOut(
            title=section.title,
            content_preview=section.content[:300],
            metadata=section.metadata,
        )
        for section in parsed.sections[:10]
    ]
    data = ParsedDocumentOut(
        title=parsed.title,
        file_type=parsed.file_type,
        section_count=len(parsed.sections),
        char_count=len(parsed.text),
        sections=sections,
    )
    return success(data.model_dump())


@router.post("/{document_id}/parse")
def parse_knowledge_document_alias(
    document_id: int,
    db: Session = Depends(get_db),
):
    return parse_knowledge_document_preview(document_id=document_id, db=db)


@router.post("/{document_id}/chunks")
def build_knowledge_document_chunks(
    document_id: int,
    chunk_size: int = 700,
    overlap: int = 100,
    db: Session = Depends(get_db),
):
    repository = KnowledgeDocumentRepository(db)
    document = repository.get(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="知识文档不存在")
    if not document.file_path:
        raise HTTPException(status_code=400, detail="知识文档缺少文件路径")

    try:
        parsed = DocumentParser().parse(document.file_path)
        drafts = DocumentChunker(chunk_size=chunk_size, overlap=overlap).build_chunks(parsed)
        chunks = repository.replace_chunks(document, drafts)
    except (DocumentParserError, ValueError) as exc:
        repository.mark_parse_failed(document, str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    data = [
        KnowledgeChunkOut(
            id=chunk.id,
            document_id=chunk.document_id,
            spot_id=chunk.spot_id,
            chunk_index=chunk.chunk_index,
            content_preview=chunk.content[:200],
            token_count=chunk.token_count,
        ).model_dump()
        for chunk in chunks
    ]
    return success({"chunk_count": len(chunks), "chunks": data[:20]})


@router.post("/{document_id}/chunk")
def build_knowledge_document_chunk_alias(
    document_id: int,
    chunk_size: int = 700,
    overlap: int = 100,
    db: Session = Depends(get_db),
):
    return build_knowledge_document_chunks(
        document_id=document_id,
        chunk_size=chunk_size,
        overlap=overlap,
        db=db,
    )


@router.post("/{document_id}/index")
def index_knowledge_document(
    document_id: int,
    db: Session = Depends(get_db),
):
    document = KnowledgeDocumentRepository(db).get(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="知识文档不存在")
    try:
        result = KnowledgeIndexService(db).index_document(document_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return success(result)


@router.delete("/{document_id}")
def delete_knowledge_document(
    document_id: int,
    db: Session = Depends(get_db),
):
    repository = KnowledgeDocumentRepository(db)
    document = repository.get(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="知识文档不存在")
    repository.delete(document)
    return success({"deleted": True})
