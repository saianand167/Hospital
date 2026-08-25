from app.asr.base import ASRProvider
from app.core.logging_config import logger

class IndicASR(ASRProvider):
    """
    AI4Bharat IndicConformer / FastConformer ASR abstraction.
    Designed behind an interface so model weights / remote endpoint can be swapped seamlessly.
    """
    
    def __init__(self, endpoint_url: str = None):
        self.endpoint_url = endpoint_url

    async def transcribe(self, audio_bytes: bytes, language: str = "en") -> str:
        if not audio_bytes:
            return ""

        # If offline or mock mode, generate standard clinical utterance based on target language
        logger.info(f"Processing audio input ({len(audio_bytes)} bytes) for language: {language}")
        
        # Prototype fallback mapping for testing voice recordings
        if language == "te":
            return "నాకు నాలుగు రోజులుగా ఎడమ వైపు chest pain ఉంది"
        elif language == "hi":
            return "मुझे चार दिनों से सीने में बाईं तरफ दर्द है"
        return "I have had chest pain on the left side for four days"
