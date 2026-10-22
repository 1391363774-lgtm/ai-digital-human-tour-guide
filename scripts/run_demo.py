"""Run an isolated, no-Key CPU demo on localhost; never reads the real .env."""
import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--state-dir', type=Path, default=ROOT / '.local-demo')
    args = parser.parse_args()
    args.state_dir.mkdir(parents=True, exist_ok=True)
    state = args.state_dir.resolve()
    os.chdir(state)
    os.environ.update(SCENIC_NO_ENV_FILE='1', DATABASE_URL=f'sqlite:///{(state / "demo.db").as_posix()}', DEMO_MODE='true',
                      TTS_PREWARM='false', DEEPSEEK_API_KEY='', QWEN_API_KEY='', APP_DEBUG='false')
    from app.core.config import get_settings
    get_settings.cache_clear()
    from alembic import command
    from alembic.config import Config
    migration = Config(str(ROOT / 'backend/alembic.ini'))
    migration.set_main_option('script_location', str(ROOT / 'backend/alembic'))
    command.upgrade(migration, 'head')
    from app.core.database import SessionLocal
    from app.models.scenic import ScenicSpot
    from app.models.knowledge import KnowledgeDocument
    from app.repositories.knowledge_repository import KnowledgeDocumentRepository
    from app.services.document_parser import DocumentParser
    from app.services.document_chunker import DocumentChunker
    from sqlalchemy import select
    with SessionLocal() as db:
        for code, name in [('demo-buddha', '灵山大佛'), ('demo-fountain', '九龙灌浴')]:
            if not db.scalar(select(ScenicSpot).where(ScenicSpot.code == code)):
                db.add(ScenicSpot(code=code, name=name))
        db.commit()
        if not db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.title == '本地演示样例')):
            repository = KnowledgeDocumentRepository(db)
            sample = ROOT / 'data/demo/guide.md'
            document = repository.create_upload_record('本地演示样例', str(sample))
            repository.replace_chunks(document, DocumentChunker().build_chunks(DocumentParser().parse(sample)))
    print(f'DEMO ONLY: simulated model and tone audio; SQLite in {state}; http://127.0.0.1:{args.port}')
    import uvicorn
    uvicorn.run('app.main:app', host='127.0.0.1', port=args.port, workers=1)


if __name__ == '__main__': main()
