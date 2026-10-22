from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models  # noqa: F401
from app.core.database import Base
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.history import MessageOut


def test_outcomes_survive_database_reload(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'outcomes.db'}")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            repo = ConversationRepository(session)
            conversation = repo.get_or_create(None, 'fixture')
            conversation_id = conversation.id
            for status in ('completed', 'partial', 'failed', 'cancelled', 'refused'):
                repo.add_message(conversation, 'assistant', 'fixture', status=status,
                                 request_id='a' * 32, error_code='model_unavailable' if status == 'partial' else None)
        with Session(engine) as session:
            rows = ConversationRepository(session).get_with_messages(conversation_id).messages
            assert [MessageOut.model_validate(m).status for m in rows] == ['completed', 'partial', 'failed', 'cancelled', 'refused']
            assert rows[1].error_code == 'model_unavailable'
            assert all(m.request_id == 'a' * 32 for m in rows)
    finally:
        engine.dispose()
