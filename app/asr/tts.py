import io
import asyncio
from typing import Optional
from app.core.logging_config import logger

# Edge-TTS Neural Voice mappings for Indian clinical kiosk
VOICE_MAP = {
    "en": "en-IN-NeerjaNeural",     # Indian English Female
    "te": "te-IN-ShrutiNeural",     # Telugu Female
    "hi": "hi-IN-SwaraNeural",      # Hindi Female
    "ta": "ta-IN-PallaviNeural",    # Tamil Female
    "mr": "mr-IN-AarohiNeural",     # Marathi Female
    "bn": "bn-IN-TanishaaNeural"    # Bengali Female
}

class TextToSpeechProvider:
    """
    Multilingual Text-to-Speech Engine for Patient Kiosks using Neural voices.
    Produces high-quality natural audio in Telugu, Hindi, English, and more.
    """

    @classmethod
    async def synthesize(cls, text: str, language: str = "en") -> Optional[bytes]:
        """
        Synthesize text into MP3 audio bytes.
        """
        if not text or not text.strip():
            return None

        voice = VOICE_MAP.get(language, VOICE_MAP["en"])
        logger.info(f"Synthesizing speech with voice '{voice}' for language '{language}'...")

        try:
            import edge_tts
            communicate = edge_tts.Communicate(text.strip(), voice=voice)
            audio_buffer = bytearray()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buffer.extend(chunk["data"])
            
            return bytes(audio_buffer)

        except Exception as e:
            logger.error(f"TTS synthesis error: {e}")
            return None
