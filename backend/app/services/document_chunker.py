from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.document_parser import ParsedDocument, ParsedSection


@dataclass(frozen=True)
class KnowledgeChunkDraft:
    content: str
    metadata: dict[str, str]
    token_count: int


class DocumentChunker:
    def __init__(self, chunk_size: int = 700, overlap: int = 100) -> None:
        if chunk_size <= overlap:
            raise ValueError("chunk_size 必须大于 overlap")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def build_chunks(self, document: ParsedDocument) -> list[KnowledgeChunkDraft]:
        drafts: list[KnowledgeChunkDraft] = []
        for section_index, section in enumerate(document.sections):
            clean_content = clean_text(section.content)
            if not clean_content:
                continue
            for chunk_index, content in enumerate(self._split_section(clean_content)):
                metadata = {
                    "document_title": document.title,
                    "source_path": document.source_path,
                    "file_type": document.file_type,
                    "section_title": section.title,
                    "section_index": str(section_index),
                    "chunk_index_in_section": str(chunk_index),
                }
                metadata.update({k: str(v) for k, v in section.metadata.items()})
                drafts.append(
                    KnowledgeChunkDraft(
                        content=content,
                        metadata=metadata,
                        token_count=estimate_token_count(content),
                    )
                )
        return drafts

    def _split_section(self, text: str) -> list[str]:
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
        if not paragraphs:
            return []

        chunks: list[str] = []
        current = ""
        for paragraph in paragraphs:
            if len(paragraph) > self.chunk_size:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.extend(self._split_long_text(paragraph))
                continue

            candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
            if len(candidate) <= self.chunk_size:
                current = candidate
            else:
                chunks.append(current)
                current = paragraph

        if current:
            chunks.append(current)

        return chunks

    def _split_long_text(self, text: str) -> list[str]:
        sentences = split_sentences(text)
        chunks: list[str] = []
        current = ""
        for sentence in sentences:
            candidate = f"{current}{sentence}" if current else sentence
            if len(candidate) <= self.chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                current = sentence
        if current:
            chunks.append(current)

        if not chunks:
            for start in range(0, len(text), self.chunk_size - self.overlap):
                chunks.append(text[start : start + self.chunk_size])

        return chunks


def clean_text(text: str) -> str:
    text = text.replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"([。！？；])\s+", r"\1", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？；.!?])", text)
    return [part.strip() for part in parts if part.strip()]


def estimate_token_count(text: str) -> int:
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    other_words = len(re.findall(r"[A-Za-z0-9_]+", text))
    return chinese_chars + other_words
