import importlib.util
import io
import struct
import wave
from pathlib import Path


def test_fixed_synthetic_wav_has_real_silent_gaps():
    spec=importlib.util.spec_from_file_location('fixture',Path(__file__).resolve().parents[2]/'scripts/mouth_fixture_server.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    with wave.open(io.BytesIO(mod.fixture_bytes())) as audio:
        assert audio.getframerate()==8000 and audio.getnframes()==12800
        values=struct.unpack('<12800h',audio.readframes(12800))
    assert any(values[:2400]) and any(values[6400:8800])
    assert not any(values[2400:6400]) and not any(values[8800:])
