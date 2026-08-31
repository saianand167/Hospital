from abc import ABC, abstractmethod
from typing import Optional

class ASRProvider(ABC):
    """
    Abstract Speech-to-Text interface for multilingual clinical input.
    """
    
    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, language: str = "en") -> str:
        """
        Transcribe audio bytes to text in target Indian language.
        """
        pass
