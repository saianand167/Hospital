import io
import threading
from typing import Optional
from app.asr.base import ASRProvider
from app.core.config import settings
from app.core.logging_config import logger

# Medical domain vocabulary prompt hints to dramatically boost Telugu & Hindi accuracy
CLINICAL_PROMPTS = {
    "te": "రోగి లక్షణాలు: గుండె నొప్పి, ఎడమ వైపు నొప్పి, కడుపు నొప్పి, దగ్గు, జ్వరం, మోషన్స్, గ్యాస్, వాంతులు, 3 రోజులుగా, తీవ్రత, chest pain, BP, sugar, allergy",
    "hi": "मरीज के लक्षण: सीने में दर्द, बाईं तरफ दर्द, पेट दर्द, बुखार, खांसी, उल्टी, दस्त, चक्कर, 4 दिनों से, गैस, बीपी, शुगर, एलर्जी",
    "en": "Patient clinical symptoms: chest pain on left side, abdominal pain, fever, cough, diarrhea, duration, severity scale, medications, allergies"
}

class IndicASR(ASRProvider):
    """
    High-Performance Multilingual ASR Engine.
    Primary: Groq Cloud Whisper-Large-v3 (Sub-second latency, highest Telugu & Hindi accuracy)
    Fallback: Local faster-whisper with clinical prompt conditioning.
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
                    logger.warning(f"Could not initialize Groq ASR client: {e}")
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
                        logger.info(f"Local faster-whisper model '{model_size}' ready.")
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
        cls._get_local_model()

    async def transcribe(self, audio_bytes: bytes, language: str = "en") -> str:
        """
        Transcribes audio bytes with maximum Telugu, Hindi, and English accuracy and speed.
        """
        if not audio_bytes or len(audio_bytes) < 50:
            return ""

        if settings.MOCK_MODE:
            logger.info(f"Mock ASR mode active for language: {language}")
            if language == "te":
                return "నాకు నాలుగు రోజులుగా ఎడమ వైపు chest pain ఉంది"
            elif language == "hi":
                return "मुझे चार दिनों से सीने में बाईं तरफ दर्द है"
            return "I have had chest pain on the left side for four days"

        lang_code = language if language in ["en", "te", "hi", "ta", "kn", "ml", "mr", "bn", "gu", "pa", "ur"] else "en"
        prompt_hint = CLINICAL_PROMPTS.get(lang_code, CLINICAL_PROMPTS["en"])

        # 1. Primary High-Speed Engine: Groq Whisper-Large-v3 (~0.4s, top-tier Telugu/Hindi accuracy)
        groq_client = self._get_groq_client()
        if groq_client:
            try:
                logger.info(f"Running high-speed Whisper-Large-v3 for language '{lang_code}' ({len(audio_bytes)} bytes)...")
                transcription = groq_client.audio.transcriptions.create(
                    file=("patient_voice.wav", audio_bytes),
                    model="whisper-large-v3",
                    language=lang_code,
                    prompt=prompt_hint,
                    response_format="text",
                    temperature=0.0
                )
                
                result = str(transcription).strip() if transcription else ""
                if result:
                    logger.info(f"Whisper-Large-v3 transcription success ({lang_code}): '{result}'")
                    return result
            except Exception as e:
                logger.warning(f"Groq Whisper-Large-v3 error, falling back to local model: {e}")

        # 2. Fallback Engine: Local faster-whisper
        try:
            logger.info(f"Running local faster-whisper model (lang={lang_code})...")
            model = self._get_local_model(self.model_size, self.device, self.compute_type)
            if not model:
                return ""

            audio_stream = io.BytesIO(audio_bytes)
            segments, info = model.transcribe(
                audio_stream,
                language=lang_code,
                initial_prompt=prompt_hint,
                beam_size=3,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=300)
            )

            text_segments = [s.text.strip() for s in segments]
            result = " ".join(text_segments).strip()
            logger.info(f"Local faster-whisper result ({lang_code}): '{result}'")
            return result

        except Exception as e:
            logger.error(f"ASR transcription failed: {e}")
            return ""
