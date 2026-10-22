"""Offline speech lifecycle regressions; no ASR/TTS model or network calls."""
import asyncio
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile
from pydantic import ValidationError

from app.schemas.speech import TtsRequest, TtsSegmentRequest
from app.services import speech_service as speech


@pytest.mark.parametrize("schema", [TtsRequest, TtsSegmentRequest])
@pytest.mark.parametrize("fields", [
    {"text": "   "}, {"text": "字" * 3001}, {"text": "test", "rate": 0.49},
    {"text": "test", "rate": 1.51}, {"text": "test", "rate": float("nan")},
    {"text": "test", "request_id": "bad\nrequest"},
])
def test_request_rejects_invalid_input_instead_of_truncating(schema, fields):
    with pytest.raises(ValidationError):
        schema(**fields)


@pytest.mark.parametrize("case", ["bounded", "close", "cancel", "failure"])
def test_segment_tasks_are_bounded_and_always_reclaimed(monkeypatch, case):
    async def run():
        created = []
        real_create = asyncio.create_task

        def create(coro, **kwargs):
            task = real_create(coro, **kwargs)
            created.append(task)
            return task

        monkeypatch.setattr(asyncio, "create_task", create)
        service = speech.TtsService()
        started = asyncio.Event()

        async def synth(text, **kwargs):
            started.set()
            if text == "0" and case in ("bounded", "close"):
                return b"audio"
            if text == "0" and case == "failure":
                await asyncio.sleep(0)
                raise speech.SpeechServiceError("synthetic failure")
            await asyncio.Event().wait()

        monkeypatch.setattr(service, "synthesize_segment", synth)
        stream = service.synthesize_segments_streaming(
            [str(i) for i in range(30)], first_batch_size=0, max_concurrency=2,
        )
        try:
            if case in ("bounded", "close"):
                assert (await anext(stream))[0] == 0
                if case == "bounded":
                    assert len(created) <= 2, "semaphore alone still allocates one task per segment"
                await stream.aclose()
                assert all(task.done() for task in created), "aclose must cancel and join pending synthesis"
            elif case == "failure":
                with pytest.raises(speech.SpeechServiceError):
                    await anext(stream)
                assert all(task.done() for task in created), "one failure must cancel sibling synthesis"
            else:
                consumer = real_create(anext(stream))
                await started.wait()
                consumer.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await consumer
                assert all(task.done() for task in created), "client cancellation must join children"
        finally:
            await stream.aclose()
            for task in created:
                task.cancel()
            await asyncio.gather(*created, return_exceptions=True)

    asyncio.run(run())


def test_audio_collector_closes_upstream_on_normal_completion():
    class Stream:
        closed = False
        calls = 0

        def __aiter__(self):
            return self

        async def __anext__(self):
            self.calls += 1
            if self.calls == 1:
                return {"type": "WordBoundary", "text": "not audio"}
            if self.calls == 2:
                return {"type": "audio", "data": b"mp3"}
            raise StopAsyncIteration

        async def aclose(self):
            self.closed = True

    upstream = Stream()
    provider = type("Provider", (), {"stream": lambda self: upstream})()
    assert asyncio.run(speech.TtsService._collect_audio_chunks(provider)) == [b"mp3"]
    assert upstream.closed, "do not rely on provider generator garbage collection"


def test_oversized_upload_closes_handle_before_deletion(monkeypatch, tmp_path):
    monkeypatch.setattr(speech.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(speech, "MAX_AUDIO_SIZE", 4)
    original_open, original_unlink = Path.open, Path.unlink
    open_handles = set()

    class TrackedFile:
        def __init__(self, path, file):
            self.path, self.file = path, file
        def __enter__(self):
            open_handles.add(self.path)
            return self.file.__enter__()
        def __exit__(self, *args):
            try:
                return self.file.__exit__(*args)
            finally:
                open_handles.remove(self.path)

    def open_file(path, *args, **kwargs):
        return TrackedFile(path, original_open(path, *args, **kwargs))

    def unlink(path, *args, **kwargs):
        assert path not in open_handles, "Windows cannot delete this still-open upload"
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_file)
    monkeypatch.setattr(Path, "unlink", unlink)
    with pytest.raises(speech.SpeechServiceError, match="限制"):
        speech.save_upload_audio(UploadFile(filename="sample.wav", file=BytesIO(b"123456")))
    assert list(tmp_path.iterdir()) == []
