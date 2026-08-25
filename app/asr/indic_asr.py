import io
import threading
from typing import Optional
from app.asr.base import ASRProvider
from app.core.config import settings
from app.core.logging_config import logger

class IndicASR(ASRProvider):
    """
    Local Multilingual ASR Engine powered by faster-whisper ('small' model by default).
    Supports English (en), Telugu (te), Hindi (hi), Tamil (ta), Kannada (kn), Marathi (mr),
    Bengali (bn), Gujarati (gu), Malayalam (ml), Punjabi (pa), Urdu (ur), and 90+ languages.
    """
    _model_instance = None
    _lock = threading.Lock()

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
    def _get_model(cls, model_size: str = "small", device: str = "auto", compute_type: str = "int8"):
        """
        Thread-safe singleton loader for faster-whisper model.
        Loads the model into RAM/VRAM once and reuses across all patient audio queries.
        """
        if cls._model_instance is None:
            with cls._lock:
                if cls._model_instance is None:
                    try:
                        from faster_whisper import WhisperModel
                        logger.info(f"Loading local faster-whisper model '{model_size}' (device={device}, compute_type={compute_type})...")
                        cls._model_instance = WhisperModel(
                            model_size,
                            device=device,
                            compute_type=compute_type
                        )
                        logger.info(f"Local faster-whisper model '{model_size}' loaded successfully.")
                    except Exception as e:
                        logger.error(f"Failed to load faster-whisper model '{model_size}': {e}")
                        cls._model_instance = None
        return cls._model_instance

    async def transcribe(self, audio_bytes: bytes, language: str = "en") -> str:
        """
        Transcribes raw audio bytes (WAV/WebM/MP3/OGG) to text using local faster-whisper.
        """
        if not audio_bytes or len(audio_bytes) < 100:
            return ""

        # If MOCK_MODE is enabled, return predictable clinical mock utterance
        if settings.MOCK_MODE:
            logger.info(f"Mock ASR mode active for language: {language}")
            if language == "te":
                return "నాకు నాలుగు రోజులుగా ఎడమ వైపు chest pain ఉంది"
            elif language == "hi":
                return "मुझे चार दिनों से सीने में बाईं तरफ दर्द है"
            return "I have had chest pain on the left side for four days"

        logger.info(f"Processing audio input ({len(audio_bytes)} bytes) with local faster-whisper (lang={language})...")

        try:
            model = self._get_model(self.model_size, self.device, self.compute_type)
            if model is None:
                logger.error("faster-whisper model is not available.")
                return ""

            audio_stream = io.BytesIO(audio_bytes)
            
            # Map standard ISO language codes
            lang_code = language if language in [
                "en", "te", "hi", "ta", "kn", "ml", "mr", "bn", "gu", "pa", "ur"
            ] else None

            segments, info = model.transcribe(
                audio_stream,
                language=lang_code,
                beam_size=5,
                vad_filter=True,  # Filter out silence & background hospital noises
                vad_parameters=dict(min_silence_duration_ms=500)
            )

            text_segments = [segment.text.strip() for segment in segments]
            transcribed_text = " ".join(text_segments).strip()
            
            detected_lang = getattr(info, "language", language)
            lang_prob = getattr(info, "language_probability", 1.0)
            logger.info(f"Transcribed successfully (lang={detected_lang}, prob={lang_prob:.2f}): '{transcribed_text}'")
            return transcribed_text

        except Exception as e:
            logger.error(f"Error during audio transcription: {e}")
            return ""
