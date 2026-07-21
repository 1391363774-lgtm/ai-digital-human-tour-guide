"""构建知识库向量索引。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal  # noqa: E402
from app.services.knowledge_index_service import KnowledgeIndexService  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="构建 Chroma 知识库向量索引")
    parser.add_argument("--document-id", type=int, help="只索引指定知识文档")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    with SessionLocal() as db:
        service = KnowledgeIndexService(db)
        result = service.index_document(args.document_id) if args.document_id else service.index_all()
    print(f"索引完成：{result['indexed_count']} 个知识块。")


if __name__ == "__main__":
    main()
