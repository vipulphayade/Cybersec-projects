from __future__ import annotations

import math
import os
from functools import lru_cache

from sentence_transformers import SentenceTransformer
import torch


DEFAULT_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2"
)
DEFAULT_EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))


class EmbeddingService:
    def __init__(self, model_name: str = DEFAULT_MODEL_NAME) -> None:
        self.model_name = model_name
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model: SentenceTransformer | None = None
        self._fallback = False

    def load(self) -> None:
        if self._model is not None or self._fallback:
            return
        try:
            self._model = SentenceTransformer(self.model_name, device=self.device)
        except Exception:
            self._fallback = True

    def encode(self, texts: list[str]) -> list[list[float]]:
        self.load()
        if self._model is not None:
            vectors = self._model.encode(
                texts,
                batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "32")),
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return [vector.tolist() for vector in vectors]
        return [self._fallback_vector(text) for text in texts]

    def encode_one(self, text: str) -> list[float]:
        return self.encode([text])[0]

    def _fallback_vector(self, text: str) -> list[float]:
        vector = [0.0] * DEFAULT_EMBEDDING_DIM
        tokens = [token for token in text.lower().split() if token]
        if not tokens:
            return vector

        for token in tokens:
            bucket = hash(token) % DEFAULT_EMBEDDING_DIM
            vector[bucket] += 1.0

        magnitude = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / magnitude for value in vector]


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()
