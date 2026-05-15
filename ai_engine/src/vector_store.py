from __future__ import annotations

import logging
import os
import threading
from typing import List, Optional

from qdrant_client import QdrantClient
from langchain_qdrant import QdrantVectorStore
from langchain_core.documents import Document

from src.embeddings import EmbeddingManager
from config.settings import COLLECTION_NAME, _ADD_BATCH_SIZE

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class VectorStoreError(Exception):
    """Base exception for VectorStoreManager failures."""


class VectorStoreManager:
    
    def __init__(
        self,
        collection_name: str = COLLECTION_NAME,
    ) -> None:
        self.collection_name = collection_name
        self.embedding_manager = EmbeddingManager()

        self._vector_store: Optional[QdrantVectorStore] = None
        self._client: Optional[QdrantClient] = None
        self._lock = threading.RLock()

    def _get_client(self) -> QdrantClient:
        if self._client is not None:
            return self._client
        
        url = os.getenv("QDRANT_URL")
        api_key = os.getenv("QDRANT_API_KEY")
        
        if not url or not api_key:
            logger.error("QDRANT_URL or QDRANT_API_KEY not found in environment variables.")
            raise VectorStoreError("Qdrant credentials missing.")

        logger.info(f"Connecting to Qdrant cloud at {url}")
        self._client = QdrantClient(url=url, api_key=api_key, timeout=60)
        return self._client

    def create_vector_store(
        self,
        documents: List[Document],
        overwrite: bool = False,
    ) -> QdrantVectorStore:
        
        if not documents:
            raise ValueError("Cannot create a vector store from an empty document list.")

        client = self._get_client()
        
        if overwrite:
            logger.info(f"Overwriting collection '{self.collection_name}' in Qdrant.")
            try:
                client.delete_collection(self.collection_name)
            except Exception as e:
                logger.warning(f"Could not delete collection (it might not exist): {e}")

        # Ensure collection exists before initializing QdrantVectorStore
        from qdrant_client.http import models
        try:
            client.get_collection(self.collection_name)
        except Exception:
            logger.info(f"Creating collection '{self.collection_name}' with 384 dimensions...")
            client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
            )

        logger.info(f"Initializing QdrantVectorStore for collection '{self.collection_name}'...")
        embeddings = self.embedding_manager.get_embeddings()

        # Ensure required payload indexes exist before any filtered search
        self._ensure_payload_indexes(client)

        with self._lock:
            self._vector_store = QdrantVectorStore(
                client=client,
                collection_name=self.collection_name,
                embedding=embeddings,
            )
            # Add documents separately
            self._vector_store.add_documents(documents)

        logger.info(f"Vector store created and documents persisted to Qdrant.")
        return self._vector_store

    def _ensure_payload_indexes(self, client: "QdrantClient") -> None:
        """Idempotently create the payload indexes required for filtered search.

        Qdrant requires a keyword index on every field used in a 'match' filter.
        Without it the search returns 400 Bad Request.
        This method is safe to call multiple times — it silently ignores
        'already exists' errors from Qdrant.
        """
        from qdrant_client.http import models

        required_keyword_fields = [
            "metadata.course_code",
        ]

        for field in required_keyword_fields:
            try:
                client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field,
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
                logger.info(f"Payload index ensured for field '{field}'.")
            except Exception as e:
                err_lower = str(e).lower()
                if "already exists" in err_lower or "conflict" in err_lower:
                    logger.debug(f"Payload index for '{field}' already exists — skipping.")
                else:
                    logger.warning(
                        f"Could not create payload index for '{field}': {e}"
                    )

    def load_vector_store(self) -> QdrantVectorStore:
        logger.info(f"Loading Qdrant vector store collection '{self.collection_name}' ...")
        embeddings = self.embedding_manager.get_embeddings()
        client = self._get_client()

        # Ensure required payload indexes exist before any filtered search
        self._ensure_payload_indexes(client)

        with self._lock:
            self._vector_store = QdrantVectorStore(
                client=client,
                collection_name=self.collection_name,
                embedding=embeddings,
            )

        logger.info(f"Qdrant vector store collection '{self.collection_name}' loaded.")
        return self._vector_store

    def add_documents(self, documents: List[Document]) -> None:
        if not documents:
            logger.warning("add_documents called with an empty list; nothing to do.")
            return

        store = self.get_vector_store()
        total = len(documents)
        batch_size = 50  # Upload 50 chunks at a time for better stability
        
        logger.info(f"Adding {total} document(s) to Qdrant in batches of {batch_size}...")

        try:
            for i in range(0, total, batch_size):
                batch = documents[i : i + batch_size]
                
                print(f"  🧠 Step 1: Generating embeddings for batch {i//batch_size + 1} on GPU...")
                # store.add_documents triggers the embedding model
                store.add_documents(batch)
                
                progress = min(i + batch_size, total)
                print(f"  🌐 Step 2: Batch {i//batch_size + 1} uploaded to Cloud! ({progress}/{total})")
                logger.info(f"Uploaded batch {i//batch_size + 1}: {progress}/{total}")
                
        except Exception as exc:
            print(f"❌ FATAL ERROR during upload: {exc}")
            raise VectorStoreError(f"Failed to add documents to Qdrant: {exc}") from exc

        logger.info(f"Successfully added {total} document(s) to Qdrant.")

    def get_vector_store(self) -> QdrantVectorStore:
        if self._vector_store is not None:
            return self._vector_store

        with self._lock:
            if self._vector_store is None:
                self.load_vector_store()

        return self._vector_store  # type: ignore[return-value]

    def get_all_sources(self) -> set:
        """Returns a set of all unique 'source' paths currently in the vector store."""
        try:
            client = self._get_client()
            sources = set()
            
            offset = None
            while True:
                response = client.scroll(
                    collection_name=self.collection_name,
                    with_payload=True,
                    with_vectors=False,
                    limit=100,
                    offset=offset
                )
                points, next_page_offset = response
                for p in points:
                    if p.payload and 'metadata' in p.payload:
                         meta = p.payload['metadata']
                         if 'source' in meta:
                             sources.add(meta['source'])
                    elif p.payload and 'source' in p.payload:
                         sources.add(p.payload['source'])
                
                if next_page_offset is None:
                    break
                offset = next_page_offset
                
            return sources
        except Exception as e:
            logger.warning(f"Could not retrieve existing sources from Qdrant: {e}")
            return set()

    def store_exists(self) -> bool:
        """Return ``True`` if the collection exists in Qdrant."""
        try:
            client = self._get_client()
            collections = client.get_collections().collections
            return any(c.name == self.collection_name for c in collections)
        except Exception:
            return False

    def _safe_count(self) -> int:
        try:
            client = self._get_client()
            return client.get_collection(self.collection_name).vectors_count
        except Exception:
            return 0