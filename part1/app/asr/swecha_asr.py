import io
import time
import threading
import numpy as np
import torch
import soundfile as sf
import scipy.signal
from typing import Optional, Dict, Any, Tuple
from app.asr.base import ASRProvider
from app.core.logging_config import logger

try:
    import av
    HAS_AV = True
except ImportError:
    HAS_AV = False


class SwechaTeluguASR(ASRProvider):
    """
    Telugu-Specific Local Automatic Speech Recognition Engine powered by Swecha Gonthuka ASR.
    Model: swechatelangana/swecha-gonthuka-asr (Wav2Vec2 architecture trained on 1.5M+ Telugu voice samples).
    Runs 100% locally on CPU/CUDA with sub-second latency.
    """
    MODEL_ID = "swechatelangana/swecha-gonthuka-asr"
    _processor = None
    _model = None
    _lock = threading.Lock()

    def __init__(self, device: Optional[str] = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

    @classmethod
    def _get_model_and_processor(cls, device: str = "cpu"):
        """Thread-safe singleton loader for Swecha Gonthuka ASR model and processor."""
        if cls._model is None or cls._processor is None:
            with cls._lock:
                if cls._model is None or cls._processor is None:
                    try:
                        from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
                        logger.info(f"Loading Swecha Gonthuka ASR model ('{cls.MODEL_ID}') on {device}...")
                        t0 = time.perf_counter()
                        processor = Wav2Vec2Processor.from_pretrained(cls.MODEL_ID)
                        model = Wav2Vec2ForCTC.from_pretrained(cls.MODEL_ID)
                        model.to(device)
                        model.eval()
                        cls._processor = processor
                        cls._model = model
                        logger.info(f"Swecha Gonthuka ASR loaded successfully in {time.perf_counter() - t0:.2f}s.")
                    except Exception as e:
                        logger.error(f"Failed to load Swecha Gonthuka ASR model: {e}", exc_info=True)
                        raise e
        return cls._processor, cls._model

    @classmethod
    def preload(cls):
        """Warm up Swecha Gonthuka ASR in a background daemon thread."""
        def _warm():
            try:
                device = "cuda" if torch.cuda.is_available() else "cpu"
                cls._get_model_and_processor(device=device)
            except Exception as e:
                logger.warning(f"Swecha ASR background preload warning: {e}")
        t = threading.Thread(target=_warm, daemon=True)
        t.start()

    @staticmethod
    def decode_audio_to_16k_mono(audio_bytes: bytes) -> np.ndarray:
        """
        Universal audio decoder converting raw bytes (WAV, WebM, OGG, MP3, etc.)
        into 16,000 Hz single-channel float32 numpy array.
        """
        if not audio_bytes or len(audio_bytes) < 40:
            return np.array([], dtype=np.float32)

        # 1. Fast Path: SoundFile (WAV, FLAC, OGG)
        try:
            data, sr = sf.read(io.BytesIO(audio_bytes))
            if len(data.shape) > 1:
                data = data.mean(axis=1)
            if sr != 16000:
                target_len = int(len(data) * 16000 / sr)
                data = scipy.signal.resample(data, target_len)
            return data.astype(np.float32)
        except Exception:
            pass

        # 2. Universal Path: PyAV (WebM, MP4, AAC, Opus, etc.)
        if HAS_AV:
            try:
                container = av.open(io.BytesIO(audio_bytes))
                resampler = av.AudioResampler(format="flt", layout="mono", rate=16000)
                frames = []
                for frame in container.decode(audio=0):
                    resampled_frames = resampler.resample(frame)
                    for rf in resampled_frames:
                        frames.append(rf.to_ndarray())
                if frames:
                    return np.concatenate(frames, axis=1).squeeze(0).astype(np.float32)
            except Exception:
                pass

        return np.array([], dtype=np.float32)

    async def transcribe(self, audio_bytes: bytes, language: str = "te") -> str:
        """Transcribe Telugu speech to text."""
        res = await self.transcribe_with_meta(audio_bytes)
        return res.get("text", "")

    async def transcribe_with_meta(self, audio_bytes: bytes) -> Dict[str, Any]:
        """
        Transcribe audio bytes with Swecha Gonthuka ASR, returning metadata and latency.
        """
        t0 = time.perf_counter()
        if not audio_bytes or len(audio_bytes) < 100:
            return {
                "text": "",
                "latency_sec": 0.0,
                "engine": "Swecha Gonthuka ASR (Telugu)",
                "language": "te",
                "model_id": self.MODEL_ID
            }

        try:
            audio_array = self.decode_audio_to_16k_mono(audio_bytes)
            if len(audio_array) == 0:
                return {
                    "text": "",
                    "latency_sec": round(time.perf_counter() - t0, 3),
                    "engine": "Swecha Gonthuka ASR (Telugu)",
                    "language": "te",
                    "error": "Failed to decode audio"
                }

            processor, model = self._get_model_and_processor(device=self.device)

            # Wav2Vec2 CTC Inference
            inputs = processor(audio_array, sampling_rate=16000, return_tensors="pt", padding=True)
            input_values = inputs.input_values.to(self.device)

            with torch.no_grad():
                logits = model(input_values).logits
                predicted_ids = torch.argmax(logits, dim=-1)
                transcription = processor.batch_decode(predicted_ids)[0]

            raw_text = transcription.strip()
            
            # Script optimization & ligature cleanup
            from app.asr.indic_asr import TeluguScriptOptimizer
            cleaned_text = TeluguScriptOptimizer.optimize(raw_text, language="te")
            latency = round(time.perf_counter() - t0, 3)

            logger.info(f"Swecha Gonthuka ASR transcribed in {latency}s: '{cleaned_text}'")

            return {
                "text": cleaned_text,
                "latency_sec": latency,
                "engine": "Swecha Gonthuka ASR (Telugu-Specific)",
                "language": "te",
                "model_id": self.MODEL_ID
            }

        except Exception as e:
            logger.error(f"Swecha Gonthuka ASR transcription failed: {e}", exc_info=True)
            return {
                "text": "",
                "latency_sec": round(time.perf_counter() - t0, 3),
                "engine": "Swecha Gonthuka ASR (Telugu)",
                "language": "te",
                "error": str(e)
            }
