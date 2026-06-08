from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Optional

from langchain_huggingface import HuggingFaceEmbeddings

from config.settings import EMBEDDING_MODEL, EMBEDDING_DEVICE

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class EmbeddingManager:

    def __init__(
        self,
        model_name: str = EMBEDDING_MODEL,
        device: str = EMBEDDING_DEVICE,
        cache_folder: Optional[str] = None,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.cache_folder = cache_folder

        self._embeddings: Optional[HuggingFaceEmbeddings] = None
        self._lock = threading.Lock()

    def get_embeddings(self) -> HuggingFaceEmbeddings:
        if self._embeddings is not None:
            return self._embeddings
        with self._lock:
            if self._embeddings is None:
                self._embeddings = self._load_model()
        return self._embeddings

    def reload(self) -> HuggingFaceEmbeddings:
        with self._lock:
            self._embeddings = None
            self._embeddings = self._load_model()
        return self._embeddings

    def _load_model(self) -> HuggingFaceEmbeddings:
        if self.cache_folder is not None:
            cache_path = Path(self.cache_folder)
            try:
                cache_path.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise RuntimeError(f"Cannot create/access embedding cache folder '{self.cache_folder}': {exc}") from exc

        logger.info(f"Loading embedding model '{self.model_name}' on device '{self.device}' (cache: {self.cache_folder or 'HuggingFace default'})")

        try:
            embeddings = HuggingFaceEmbeddings(
                model_name=self.model_name,
                model_kwargs={"device": self.device},
                encode_kwargs={"normalize_embeddings": True},
                cache_folder=self.cache_folder,
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to load embedding model '{self.model_name}': {exc}") from exc

        logger.info("Embedding model loaded successfully.")
        return embeddings