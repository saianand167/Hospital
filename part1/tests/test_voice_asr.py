import io
import wave
import struct
import pytest
from app.asr.indic_asr import IndicASR
from app.asr.tts import TextToSpeechProvider
from app.asr.swecha_asr import SwechaTeluguASR
from app.core.config import settings

def create_synthetic_wav() -> bytes:
    """Generate a minimal valid 16kHz mono WAV file in memory."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        # 0.5s of silence
        data = struct.pack("<" + "h" * 8000, *([0] * 8000))
        wav_file.writeframes(data)
    return buffer.getvalue()

@pytest.mark.asyncio
async def test_indic_asr_empty():
    asr = IndicASR()
    res = await asr.transcribe(b"")
    assert res == ""

@pytest.mark.asyncio
async def test_indic_asr_mock_transcribe():
    orig_mock = settings.MOCK_MODE
    settings.MOCK_MODE = True
    try:
        asr = IndicASR()
        wav_data = create_synthetic_wav()
        
        # Test Telugu transcription
        res_te = await asr.transcribe(wav_data, language="te")
        assert "chest pain" in res_te or "నొప్పి" in res_te

        # Test Hindi transcription
        res_hi = await asr.transcribe(wav_data, language="hi")
        assert "दर्द" in res_hi

        # Test English transcription
        res_en = await asr.transcribe(wav_data, language="en")
        assert "chest pain" in res_en.lower()
    finally:
        settings.MOCK_MODE = orig_mock

@pytest.mark.asyncio
async def test_tts_synthesis():
    audio = await TextToSpeechProvider.synthesize("")
    assert audio is None
    
    audio_en = await TextToSpeechProvider.synthesize("Hello patient, where does it hurt?", language="en")
    assert audio_en is not None and len(audio_en) > 100

@pytest.mark.asyncio
async def test_swecha_telugu_asr():
    asr = SwechaTeluguASR()
    
    # Test empty audio
    res_empty = await asr.transcribe_with_meta(b"")
    assert res_empty.get("text") == ""
    assert res_empty.get("engine") == "Swecha Gonthuka ASR (Telugu)"
    
    # Test synthetic audio processing
    wav_data = create_synthetic_wav()
    res = await asr.transcribe_with_meta(wav_data)
    assert "text" in res
    assert res.get("language") == "te"
    assert "latency_sec" in res

@pytest.mark.asyncio
async def test_faster_whisper_medium_asr():
    asr = IndicASR(model_size="medium")
    wav_data = create_synthetic_wav()
    res = await asr.transcribe_with_meta(wav_data, language="en")
    assert "text" in res
    assert "latency_sec" in res
    assert res.get("language") in ["en", "auto"]
