from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.knowledge import KnowledgeDocument
from app.repositories.knowledge_repository import KnowledgeDocumentRepository

ALLOWED_SUFFIXES = {".txt", ".md", ".csv", ".tsv", ".docx", ".xlsx"}
MAX_UPLOAD_SIZE = 30 * 1024 * 1024


class KnowledgeUploadError(ValueError):
    pass


class KnowledgeUploadService:
    def __init__(self, db: Session) -> None:
        self.repository = KnowledgeDocumentRepository(db)
        self.settings = get_settings()

    def save_upload(self, file: UploadFile, uploaded_by: int | None = None) -> KnowledgeDocument:
        original_name = file.filename or "uploaded_file"
        suffix = Path(original_name).suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            raise KnowledgeUploadError(f"暂不支持的文件类型：{suffix}")

        upload_dir = Path("data/raw/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        target_name = f"{uuid.uuid4().hex}{suffix}"
        target_path = upload_dir / target_name

        size = 0
        with target_path.open("wb") as output:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_SIZE:
                    target_path.unlink(missing_ok=True)
                    raise KnowledgeUploadError("上传文件超过 30MB 限制")
                output.write(chunk)

        title = Path(original_name).stem
        return self.repository.create_upload_record(
            title=title,
            file_path=str(target_path),
            uploaded_by=uploaded_by,
        )

    def copy_local_file(self, source: str | Path, uploaded_by: int | None = None) -> KnowledgeDocument:
        source_path = Path(source)
        if not source_path.exists():
            raise KnowledgeUploadError(f"文件不存在：{source_path}")
        suffix = source_path.suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            raise KnowledgeUploadError(f"暂不支持的文件类型：{suffix}")

        upload_dir = Path("data/raw/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        target_path = upload_dir / f"{uuid.uuid4().hex}{suffix}"
        shutil.copy2(source_path, target_path)
        return self.repository.create_upload_record(
            title=source_path.stem,
            file_path=str(target_path),
            uploaded_by=uploaded_by,
        )
