import io
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import knowledge_upload_service as uploads


@pytest.mark.parametrize('failure', ['oversize', 'database'])
def test_failed_upload_closes_and_removes_partial_file(tmp_path, monkeypatch, failure):
    monkeypatch.chdir(tmp_path)
    service = uploads.KnowledgeUploadService.__new__(uploads.KnowledgeUploadService)
    def save(**kwargs): raise RuntimeError('database unavailable')
    service.repository = SimpleNamespace(create_upload_record=save)
    monkeypatch.setattr(uploads, 'MAX_UPLOAD_SIZE', 2 if failure == 'oversize' else 100)
    with pytest.raises(uploads.KnowledgeUploadError if failure == 'oversize' else RuntimeError):
        service.save_upload(SimpleNamespace(filename='../../fixture.md', file=io.BytesIO(b'contents')))
    assert list(Path('data/raw/uploads').iterdir()) == []
