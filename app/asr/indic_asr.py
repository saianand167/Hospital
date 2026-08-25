import io
import threading
from typing import Optional, Tuple
from app.asr.base import ASRProvider
from app.core.config import settings
from app.core.logging_config import logger

def detect_audio_mime(audio_bytes: bytes) -> Tuple[str, str]:
    """Detect format from audio magic bytes for proper API decoding."""
    if audio_bytes.startswith(b"RIFF"):
        return "patient_voice.wav", "audio/wav"
    elif audio_bytes.startswith(b"\x1a\x45\xdf\xa3") or b"webm" in audio_bytes[:64].lower():
        return "patient_voice.webm", "audio/webm"
    elif audio_bytes.startswith(b"OggS"):
        return "patient_voice.ogg", "audio/ogg"
    elif audio_bytes.startswith(b"ID3") or audio_bytes.startswith(b"\xff\xfb"):
        return "patient_voice.mp3", "audio/mp3"
    elif b"ftyp" in audio_bytes[:16]:
        return "patient_voice.mp4", "audio/mp4"
    return "patient_voice.webm", "audio/webm"

# Unified multilingual clinical vocabulary hint allowing seamless cross-language switching
MULTILINGUAL_CLINICAL_PROMPT = (
    "Hospital patient consultation. Common symptoms: "
    "గుండె నొప్పి, ఎడమ వైపు నొప్పి, కడుపు నొప్పి, దగ్గు, జ్వరం, మోషన్స్, గ్యాస్, వాంతులు, "
    "सीने में दर्द, बाईं तरफ दर्द, पेट दर्द, बुखार, खांसी, उल्टी, दस्त, चक्कर, "
    "chest pain on left side, severe abdominal pain, high fever, duration days, scale rating."
)

class IndicASR(ASRProvider):
    """
    Ultra-Fast Multilingual ASR Engine with Cross-Language Auto-Detection.
    Allows speaking in Telugu, Hindi, English, or mixed languages at any time.
    Primary: Groq Cloud Whisper-Large-v3-Turbo (~0.2s latency, high accuracy)
    Fallback: Local faster-whisper.
    """
    _local_model_instance = None
    _lock = threading.Lock()
    _groq_client = None

    def __init__(
        self,
        model_size: Optional[str] = None,
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
        endpoint_url: Optional[str] = None
    ):
        self.model_size = model_size or getattr(settings, "ASR_MODEL_SIZE", "small")
        self.device = device or getattr(settings, "ASR_DEVICE", "auto")
        self.compute_type = compute_type or getattr(settings, "ASR_COMPUTE_TYPE", "int8")
        self.endpoint_url = endpoint_url

    @classmethod
    def _get_groq_client(cls):
        if cls._groq_client is None:
            api_key = settings.GROQ_API_KEY
            if api_key:
                try:
                    import groq
                    cls._groq_client = groq.Groq(api_key=api_key)
                except Exception as e:
                    logger.warning(f"Could not initialize Groq client: {e}")
        return cls._groq_client

    @classmethod
    def _get_local_model(cls, model_size: str = "small", device: str = "auto", compute_type: str = "int8"):
        """Thread-safe singleton loader for local faster-whisper model."""
        if cls._local_model_instance is None:
            with cls._lock:
                if cls._local_model_instance is None:
                    try:
                        from faster_whisper import WhisperModel
                        actual_device = "cpu" if device in ["auto", "cpu"] else device
                        logger.info(f"Loading local faster-whisper model '{model_size}'...")
                        cls._local_model_instance = WhisperModel(
                            model_size,
                            device=actual_device,
                            compute_type=compute_type,
                            cpu_threads=4
                        )
                    except Exception as e:
                        logger.error(f"Failed to load local faster-whisper model: {e}")
        return cls._local_model_instance

    @classmethod
    def preload(cls):
        """Warm up engines in background thread."""
        t = threading.Thread(target=cls._warmup, daemon=True)
        t.start()

    @classmethod
    def _warmup(cls):
        cls._get_groq_client()

    async def transcribe(self, audio_bytes: bytes, language: str = "en") -> str:
        """
        Transcribes audio bytes with automatic language detection and lightning speed.
        Patients can speak in Telugu, Hindi, English, or switch languages freely.
        """
        if not audio_bytes or len(audio_bytes) < 150:
            return ""

        if settings.MOCK_MODE:
            logger.info(f"Mock ASR mode active for language: {language}")
            if language == "te":
                return "నాకు నాలుగు రోజులుగా ఎడమ వైపు chest pain ఉంది"
            elif language == "hi":
                return "मुझे चार दिनों से सीने में बाईं तरफ दर्द है"
            return "I have had chest pain on the left side for four days"

        filename, mime_type = detect_audio_mime(audio_bytes)

        # 1. Primary Engine: Groq Whisper-Large-v3-Turbo (Ultra-fast ~0.3s, Auto-Language Detection)
        groq_client = self._get_groq_client()
        if groq_client:
            try:
                logger.info(f"Invoking Groq Whisper-Large-v3-Turbo (Auto-Detect, mime={mime_type}, bytes={len(audio_bytes)})...")
                
                # Note: Not restricting language code allows auto-detecting Telugu, Hindi, English, etc.
                transcription = groq_client.audio.transcriptions.create(
                    file=(filename, audio_bytes, mime_type),
                    model="whisper-large-v3-turbo",
                    prompt=MULTILINGUAL_CLINICAL_PROMPT,
                    response_format="text",
                    temperature=0.0
                )
                
                result = str(transcription).strip() if transcription else ""
                
                if result and not self._is_hallucination(result):
                    logger.info(f"Groq Whisper-Turbo transcription success: '{result}'")
                    return result
            except Exception as e:
                logger.warning(f"Groq Whisper Turbo error, falling back: {e}")

        # 2. Fallback Engine: Local faster-whisper (Auto-detecting language)
        try:
            logger.info("Running local faster-whisper fallback...")
            model = self._get_local_model(self.model_size, self.device, self.compute_type)
            if not model:
                return ""

            audio_stream = io.BytesIO(audio_bytes)
            # language=None triggers automatic language identification
            segments, info = model.transcribe(
                audio_stream,
                language=None,
                initial_prompt=MULTILINGUAL_CLINICAL_PROMPT,
                temperature=0.0,
                beam_size=3,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=300)
            )

            text_segments = [s.text.strip() for s in segments]
            result = " ".join(text_segments).strip()
            
            if self._is_hallucination(result):
                return ""

            logger.info(f"Local faster-whisper detected '{info.language}' ({info.language_probability:.2f}): '{result}'")
            return result

        except Exception as e:
            logger.error(f"ASR transcription failed: {e}")
            return ""

    @staticmethod
    def _is_hallucination(text: str) -> bool:
        """Filter out common Whisper silence hallucination patterns."""
        if not text or len(text.strip()) == 0:
            return True
        # Check repeated character clusters (e.g. "నింనిందింనించి")
        if len(text) > 10 and len(set(text)) < 5:
            return True
        return False
