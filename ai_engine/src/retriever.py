from __future__ import annotations

import logging
import threading
from typing import List, Optional, Tuple

import numpy as np
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder

from src.vector_store import VectorStoreManager
from config.settings import TOP_K_RESULTS

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

_RERANKER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_reranker_instance: Optional[CrossEncoder] = None
_reranker_lock = threading.Lock()

def _get_reranker() -> CrossEncoder:
    global _reranker_instance
    if _reranker_instance is not None:
        return _reranker_instance
    with _reranker_lock:
        if _reranker_instance is None:
            logger.info(f"Loading CrossEncoder reranker: {_RERANKER_MODEL_NAME}")
            _reranker_instance = CrossEncoder(_RERANKER_MODEL_NAME)
            logger.info("Reranker loaded successfully.")
    return _reranker_instance

def _normalize(scores: np.ndarray) -> np.ndarray:
    min_s, max_s = scores.min(), scores.max()
    if max_s - min_s < 1e-9:
        return np.zeros_like(scores, dtype=float)
    return (scores - min_s) / (max_s - min_s)

class Retriever:
    def __init__(
        self,
        top_k: int = TOP_K_RESULTS,
        dense_weight: float = 0.7,
        bm25_weight: float = 0.3,
        vector_store_manager: Optional["VectorStoreManager"] = None,
    ) -> None:
        if not (0.0 <= dense_weight <= 1.0 and 0.0 <= bm25_weight <= 1.0):
            raise ValueError("Weights must be between 0 and 1.")
        if abs(dense_weight + bm25_weight - 1.0) > 1e-6:
            raise ValueError("dense_weight + bm25_weight must equal 1.0.")

        self.top_k = top_k
        self.dense_weight = dense_weight
        self.bm25_weight = bm25_weight
        self.vector_store_manager = vector_store_manager or VectorStoreManager()

        self._bm25_lock = threading.Lock()
        self._bm25: Optional[BM25Okapi] = None
        self._all_docs: Optional[List[Document]] = None
        self._reranker = _get_reranker()

    def _initialize_bm25(self) -> None:
        if self._bm25 is not None:
            return
        with self._bm25_lock:
            if self._bm25 is not None:
                return
            logger.info("Building BM25 index …")
            vector_store = self.vector_store_manager.get_vector_store()
            try:
                # 1. Fetch all IDs first (safe)
                all_ids = vector_store._collection.get(include=[])["ids"]
                if not all_ids:
                    logger.warning("No documents found in vector store to build BM25 index.")
                    return

                all_docs = []
                # 2. Fetch documents in chunks to avoid SQLite "too many SQL variables" error
                chunk_size = 500
                for i in range(0, len(all_ids), chunk_size):
                    batch_ids = all_ids[i:i + chunk_size]
                    batch_data = vector_store._collection.get(ids=batch_ids, include=["documents", "metadatas"])
                    
                    for d, m in zip(batch_data["documents"], batch_data["metadatas"]):
                        all_docs.append(Document(page_content=d, metadata=m))

                if not all_docs:
                    return

                tokenized = [_tokenize(doc.page_content) for doc in all_docs]
                self._all_docs = all_docs
                self._bm25 = BM25Okapi(tokenized)
                logger.info(f"BM25 index built with {len(all_docs)} documents.")
            except Exception as exc:
                logger.error(f"Failed to build BM25 index: {exc}")
                self._all_docs = []
                self._bm25 = None

    def invalidate_bm25(self) -> None:
        with self._bm25_lock:
            self._bm25 = None
            self._all_docs = None
        logger.info("BM25 index invalidated.")

    # ------------------------------------------------------------------
    # ★ التعديل الأساسي: استقبال قائمة المواد للفلترة ★
    # ------------------------------------------------------------------
    def retrieve(
        self,
        query: str,
        user_courses: Optional[List[str]] = None, # Expects a list of course codes (e.g. ["CS101", "MA111"])
    ) -> List[Document]:
        
        logger.info(f"Retrieving for query: {query[:80]!r}")
        vector_store = self.vector_store_manager.get_vector_store()
        self._initialize_bm25()

        # ---- Step 1: Dense retrieval with Course Filtering --------
        where_filter = None
        if user_courses:
            # Clean course codes for metadata matching
            clean_codes = [c.upper().strip() for c in user_courses if c.strip()]
            if clean_codes:
                from qdrant_client.http import models
                where_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="metadata.course_code",
                            match=models.MatchAny(any=clean_codes)
                        )
                    ]
                )
                logger.info(f"Applying course_code filter: {clean_codes}")

        dense_results: List[Tuple[Document, float]] = (
            vector_store.similarity_search_with_score(
                query,
                k=self.top_k * 2,
                filter=where_filter,
            )
        )

        # Removed fallback to global search to strictly enforce course-code filtering
        pass

        if not dense_results:
            logger.warning("Dense retrieval returned no results.")
            return []

        dense_docs = [doc for doc, _ in dense_results]
        raw_dense = np.array([max(0.0, 1.0 - (score / 2.0)) for _, score in dense_results])
        norm_dense = _normalize(raw_dense)

        dense_score_map: dict[tuple, float] = {
            _doc_key(doc): float(norm_dense[i])
            for i, doc in enumerate(dense_docs)
        }

        # ---- Step 2: BM25 retrieval -----------------------------------------
        bm25_score_map: dict[tuple, float] = {}
        if self._bm25 and self._all_docs:
            tokenized_query = _tokenize(query)
            raw_bm25 = np.array(self._bm25.get_scores(tokenized_query))
            norm_bm25 = _normalize(raw_bm25)
            for doc, score in zip(self._all_docs, norm_bm25):
                bm25_score_map[_doc_key(doc)] = float(score)

        # ---- Step 3: Combine and STRICTLY Filter ----------------------------
        combined: List[Tuple[Document, float]] = []
        
        # Normalize allowed codes for robust comparison
        allowed_codes = set()
        if user_courses:
            allowed_codes = {c.upper().strip() for c in user_courses if c.strip()}
            logger.info(f"STRICT FILTER ACTIVE. Allowed: {allowed_codes}")

        for doc in dense_docs:
            # Get and normalize the document's course code
            doc_course_raw = doc.metadata.get("course_code", "")
            doc_course = doc_course_raw.upper().strip() if doc_course_raw else ""
            
            # DEBUG: Log every document's code to see what's leaking
            logger.info(f"Checking Doc: [{doc_course_raw}] -> Normalized: [{doc_course}]")

            if allowed_codes and doc_course not in allowed_codes:
                logger.warning(f"BLOCKING document from course '{doc_course_raw}' - Not in allowed list.")
                continue

            key = _doc_key(doc)
            d_score = dense_score_map.get(key, 0.0)
            b_score = bm25_score_map.get(key, 0.0)
            final = self.dense_weight * d_score + self.bm25_weight * b_score
            combined.append((doc, final))

        combined.sort(key=lambda x: x[1], reverse=True)
        candidates = [doc for doc, _ in combined[: self.top_k * 2]]
        
        logger.info(f"Final candidate count after strict filtering: {len(candidates)}")
        return self._rerank(query, candidates)

    def retrieve_with_scores(
        self, query: str, user_courses: Optional[List[str]] = None
    ) -> List[Tuple[str, dict, float]]:
        candidates = self.retrieve(query, user_courses=user_courses)
        if not candidates:
            return []
        pairs = [[query, doc.page_content] for doc in candidates]
        try:
            scores: List[float] = self._reranker.predict(pairs).tolist()
        except Exception as exc:
            scores = [0.0] * len(candidates)
        return [(doc.page_content, doc.metadata, score) for doc, score in zip(candidates, scores)]

    def _rerank(self, query: str, docs: List[Document]) -> List[Document]:
        if not docs:
            return []
        try:
            pairs = [[query, doc.page_content] for doc in docs]
            scores: np.ndarray = self._reranker.predict(pairs)
            reranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
            final = [doc for doc, _ in reranked[: self.top_k]]
            return final
        except Exception as exc:
            logger.error(f"Reranking failed ({exc}); returning hybrid-scored order.")
            return docs[: self.top_k]

def _tokenize(text: str) -> List[str]:
    import re
    cleaned = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return cleaned.split()

def _doc_key(doc: Document) -> tuple:
    return (doc.page_content, doc.metadata.get("source", ""))