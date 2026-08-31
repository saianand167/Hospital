import os
import requests
import numpy as np
import logging
from app.config import settings

logger = logging.getLogger(__name__)

def _flatten_to_float_vector(data) -> list[float]:
    """
    Recursively unwraps nested list responses from Hugging Face Inference API
    (e.g., [[[0.1, 0.2, ...]]] -> [0.1, 0.2, ...]) and validates element types.
    """
    if isinstance(data, dict):
        if "error" in data:
            raise ValueError(f"HF API Error: {data.get('error')}")
        raise ValueError(f"HF API returned unexpected dictionary payload: {data}")

    curr = data
    # Recursively descend if element 0 is a list
    while isinstance(curr, list) and len(curr) > 0 and isinstance(curr[0], list):
        curr = curr[0]

    if not isinstance(curr, list) or not all(isinstance(x, (float, int)) for x in curr):
        raise ValueError(f"Invalid embedding vector structure from HF API: {type(curr)}")

    return [float(x) for x in curr]


class HuggingFaceEmbeddingProvider:
    def __init__(self):
        self.hf_token = os.getenv("HF_TOKEN") or settings.HF_TOKEN
        self.model_name = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-small-en-v1.5")
        self.api_url = f"https://api-inference.huggingface.co/models/{self.model_name}"
        self.headers = {"Authorization": f"Bearer {self.hf_token}"}

    def embed_query(self, text: str) -> list[float]:
        """Generates an embedding vector using Hugging Face Cloud API without local downloads."""
        if not self.hf_token:
            raise ValueError("HF_TOKEN is missing in .env")

        response = requests.post(
            self.api_url,
            headers=self.headers,
            json={"inputs": text, "options": {"wait_for_model": True}},
            timeout=15,
        )
        if response.status_code != 200:
            raise RuntimeError(f"HF API Error ({response.status_code}): {response.text}")

        result = response.json()
        return _flatten_to_float_vector(result)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Batch embed multiple strings."""
        if not self.hf_token:
            raise ValueError("HF_TOKEN is missing in .env")

        response = requests.post(
            self.api_url,
            headers=self.headers,
            json={"inputs": texts, "options": {"wait_for_model": True}},
            timeout=30,
        )
        if response.status_code != 200:
            raise RuntimeError(f"HF API Error ({response.status_code}): {response.text}")

        result = response.json()
        if isinstance(result, dict):
            raise ValueError(f"HF API Error: {result.get('error', result)}")

        if isinstance(result, list):
            vectors = []
            for item in result:
                vectors.append(_flatten_to_float_vector(item))
            return vectors

        raise ValueError(f"Unexpected batch payload: {type(result)}")


class EmbeddingProvider:
    def __init__(self, model_name: str = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL_NAME
        self.use_hf_api = os.getenv("USE_HF_EMBEDDINGS_API", "").lower() == "true" or settings.USE_HF_EMBEDDINGS_API
        self.hf_token = os.getenv("HF_TOKEN") or settings.HF_TOKEN
        
        self.hf_provider = None
        self.local_model = None

        if self.use_hf_api or (self.hf_token and self.hf_token.startswith("hf_")):
            logger.info("Initializing HuggingFace Serverless Cloud Embedding Provider")
            self.hf_provider = HuggingFaceEmbeddingProvider()
        else:
            self._load_local_model()

    def _load_local_model(self):
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading SentenceTransformer model: {self.model_name}")
            self.local_model = SentenceTransformer(self.model_name)
        except Exception as e:
            logger.warning(f"Could not load SentenceTransformer ({str(e)}). Falling back to deterministic embedding vector generator.")
            self.local_model = None

    def embed(self, text: str) -> list[float]:
        """
        Embed a single text string into a 384-dimensional vector.
        """
        if not text:
            return [0.0] * 384

        if self.hf_provider is not None:
            try:
                vec = self.hf_provider.embed_query(text)
                if isinstance(vec, list) and len(vec) > 0:
                    return vec
            except Exception as e:
                logger.error(f"Hugging Face Cloud API error: {str(e)}. Falling back to local/deterministic fallback.")

        if self.local_model is not None:
            try:
                vec = self.local_model.encode(text, convert_to_numpy=True)
                return vec.tolist()
            except Exception as e:
                logger.error(f"Error generating embedding via local model: {str(e)}")

        # Fallback deterministic pseudo-embedding (384 dimensions)
        np.random.seed(abs(hash(text)) % (2**32))
        random_vector = np.random.randn(384)
        normalized = random_vector / np.linalg.norm(random_vector)
        return normalized.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if self.hf_provider is not None:
            try:
                vecs = self.hf_provider.embed_documents(texts)
                if isinstance(vecs, list) and len(vecs) == len(texts):
                    return vecs
            except Exception as e:
                logger.error(f"Hugging Face Cloud API batch error: {str(e)}")

        return [self.embed(t) for t in texts]

# Global provider instance
embedding_provider = EmbeddingProvider()
