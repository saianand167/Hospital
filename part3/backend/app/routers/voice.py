"""
Voice / Speech Router — ASR using Groq Whisper-large-v3-turbo
POST /api/v1/voice/transcribe  → accepts audio file → returns transcript text
"""

import io
import logging
import requests as http_requests
from fastapi import APIRouter, UploadFile, File, Depends, Form
from fastapi.responses import JSONResponse

from app.config import settings
from app import auth, models

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["Voice & ASR"])

GROQ_ASR_MODELS = {
    "fast": "whisper-large-v3-turbo",     # Ultra-fast, lowest latency (<300ms)
    "medium": "whisper-large-v3-turbo",   # Balanced latency and high accuracy
    "accurate": "whisper-large-v3",       # Maximum accuracy for complex drug names
}

@router.post(
    "/transcribe",
    summary="Transcribe Audio using Groq Whisper ASR",
    description="Upload audio (WAV/WebM/MP3/MP4/OGG) and get back transcribed text. Uses Groq Whisper-large-v3-turbo by default.",
    responses={
        200: {"description": "Transcription successful"},
        400: {"description": "No audio data or unsupported format"},
        503: {"description": "Groq ASR service unavailable"},
    }
)
async def transcribe_audio(
    audio: UploadFile = File(..., description="Audio file (WAV, WebM, MP3, MP4, OGG, FLAC)"),
    language: str = Form(default="en", description="Language code: en, hi, te, ta, etc."),
    model_quality: str = Form(default="fast", description="'fast' (whisper-large-v3-turbo) or 'accurate' (whisper-large-v3)"),
):
    """Transcribe audio using Groq Whisper. No authentication required for patient kiosk use."""
    if not settings.GROK_API_KEY:
        return JSONResponse(
            status_code=503,
            content={"transcript": "", "error": "Groq API key not configured"}
        )

    model_id = GROQ_ASR_MODELS.get(model_quality, GROQ_ASR_MODELS["fast"])

    audio_bytes = await audio.read()
    if not audio_bytes:
        return JSONResponse(
            status_code=400,
            content={"transcript": "", "error": "Empty audio file received"}
        )

    # Determine content type
    content_type = audio.content_type or "audio/webm"
    filename = audio.filename or f"recording.{content_type.split('/')[-1]}"

    try:
        files = {
            "file": (filename, io.BytesIO(audio_bytes), content_type),
        }
        data = {
            "model": model_id,
            "language": language if language != "en" else None,
            "response_format": "json",
        }
        # Remove None values
        data = {k: v for k, v in data.items() if v is not None}

        response = http_requests.post(
            f"{settings.GROK_API_BASE}/audio/transcriptions",
            headers={"Authorization": f"Bearer {settings.GROK_API_KEY}"},
            files=files,
            data=data,
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            transcript = result.get("text", "").strip()
            logger.info(f"ASR transcription successful: '{transcript[:60]}...' using {model_id}")
            return {
                "transcript": transcript,
                "model_used": model_id,
                "language": language,
                "duration_seconds": result.get("duration"),
                "error": None
            }
        else:
            logger.error(f"Groq ASR error {response.status_code}: {response.text}")
            return JSONResponse(
                status_code=503,
                content={"transcript": "", "error": f"Groq Whisper returned error {response.status_code}: {response.text[:200]}"}
            )

    except Exception as e:
        logger.error(f"ASR transcription failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"transcript": "", "error": f"Transcription failed: {str(e)}"}
        )


@router.get("/models", summary="List Available ASR/TTS Models")
def list_voice_models():
    """Return the list of available voice models."""
    return {
        "asr_models": [
            {
                "id": "whisper-large-v3-turbo",
                "quality": "fast",
                "description": "Groq-hosted Whisper Large V3 Turbo — fast, supports 99 languages including Hindi and Telugu",
                "use_case": "Patient questionnaire responses, real-time voice"
            },
            {
                "id": "whisper-large-v3",
                "quality": "accurate",
                "description": "Groq-hosted Whisper Large V3 — highest accuracy, best for medical terminology",
                "use_case": "Doctor prescription dictation where accuracy is critical"
            }
        ],
        "tts_models": [
            {
                "id": "canopylabs/orpheus-v1-english",
                "language": "English",
                "description": "Orpheus TTS — natural sounding English voice for bot questions",
                "use_case": "Read clinical intake questions aloud for patients"
            }
        ],
        "currently_used_for": {
            "patient_intake_bot_speech": "canopylabs/orpheus-v1-english (TTS)",
            "patient_voice_response": "whisper-large-v3-turbo (ASR)",
            "doctor_prescription_dictation": "whisper-large-v3 (ASR, high accuracy)"
        }
    }
