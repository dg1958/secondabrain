"""
Content deduplication service for Memory Palace.

This module provides:
- Hash-based exact duplicate detection
- Semantic similarity-based near-duplicate detection
- Deduplication during ingestion
"""

import hashlib
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
from loguru import logger

from config.schema import MemoryChunk
from storage.embedding_service import EmbeddingService, get_embedding_service


class DeduplicationService:
    """
    Service for detecting and handling duplicate content.

    Supports two modes of deduplication:
    1. Hash-based: Fast, exact duplicate detection using content hashes
    2. Semantic: Slower, but detects near-duplicates using embeddings
    """

    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        similarity_threshold: float = 0.95,
    ):
        """
        Initialize the deduplication service.

        Args:
            embedding_service: Service for generating embeddings
            similarity_threshold: Threshold for semantic similarity (0-1)
        """
        self._embedding_service = embedding_service
        self._similarity_threshold = similarity_threshold
        self._hash_index: Dict[str, str] = {}  # hash -> chunk_id
        self._embedding_index: Dict[str, np.ndarray] = {}  # chunk_id -> embedding

    @property
    def embedding_service(self) -> EmbeddingService:
        """Get the embedding service, initializing if needed."""
        if self._embedding_service is None:
            self._embedding_service = get_embedding_service()
        return self._embedding_service

    @property
    def similarity_threshold(self) -> float:
        """Get the similarity threshold for near-duplicate detection."""
        return self._similarity_threshold

    @similarity_threshold.setter
    def similarity_threshold(self, value: float) -> None:
        """Set the similarity threshold (0-1)."""
        if not 0 <= value <= 1:
            raise ValueError("Similarity threshold must be between 0 and 1")
        self._similarity_threshold = value

    def compute_hash(self, text: str) -> str:
        """
        Compute a hash for text content.

        Uses SHA-256 for reliable duplicate detection.

        Args:
            text: Text content to hash

        Returns:
            Hex digest of the hash
        """
        # Normalize text before hashing
        normalized = self._normalize_text(text)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for consistent hashing.

        Removes extra whitespace and converts to lowercase.

        Args:
            text: Text to normalize

        Returns:
            Normalized text
        """
        # Collapse whitespace and lowercase
        return " ".join(text.lower().split())

    def is_exact_duplicate(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Check if text is an exact duplicate of indexed content.

        Args:
            text: Text to check

        Returns:
            Tuple of (is_duplicate, existing_chunk_id or None)
        """
        content_hash = self.compute_hash(text)

        if content_hash in self._hash_index:
            return True, self._hash_index[content_hash]

        return False, None

    def is_near_duplicate(
        self,
        text: str,
        embedding: Optional[np.ndarray] = None,
    ) -> Tuple[bool, Optional[str], float]:
        """
        Check if text is semantically similar to indexed content.

        Args:
            text: Text to check
            embedding: Pre-computed embedding (optional)

        Returns:
            Tuple of (is_duplicate, existing_chunk_id or None, similarity_score)
        """
        if not self._embedding_index:
            return False, None, 0.0

        # Get embedding
        if embedding is None:
            try:
                embedding = self.embedding_service.embed(text)
            except Exception as e:
                logger.warning(f"Failed to generate embedding for dedup: {e}")
                return False, None, 0.0

        # Compare with indexed embeddings
        max_similarity = 0.0
        most_similar_id = None

        for chunk_id, indexed_embedding in self._embedding_index.items():
            similarity = self.embedding_service.compute_similarity(
                embedding, indexed_embedding
            )

            if similarity > max_similarity:
                max_similarity = similarity
                most_similar_id = chunk_id

        is_duplicate = max_similarity >= self._similarity_threshold

        return is_duplicate, most_similar_id if is_duplicate else None, max_similarity

    def check_duplicate(
        self,
        text: str,
        embedding: Optional[np.ndarray] = None,
        check_semantic: bool = True,
    ) -> Tuple[bool, Optional[str], str]:
        """
        Check if text is a duplicate using both hash and semantic methods.

        Args:
            text: Text to check
            embedding: Pre-computed embedding (optional)
            check_semantic: Whether to perform semantic similarity check

        Returns:
            Tuple of (is_duplicate, existing_chunk_id, method used)
        """
        # First check exact duplicates (fast)
        is_exact, exact_id = self.is_exact_duplicate(text)
        if is_exact:
            return True, exact_id, "exact_hash"

        # Then check semantic duplicates (slower)
        if check_semantic:
            is_near, near_id, similarity = self.is_near_duplicate(text, embedding)
            if is_near:
                return True, near_id, f"semantic_{similarity:.3f}"

        return False, None, "none"

    def add_to_index(
        self,
        chunk_id: str,
        text: str,
        embedding: Optional[np.ndarray] = None,
    ) -> None:
        """
        Add content to the deduplication index.

        Args:
            chunk_id: Unique identifier for the chunk
            text: Text content
            embedding: Pre-computed embedding (optional)
        """
        # Add hash
        content_hash = self.compute_hash(text)
        self._hash_index[content_hash] = chunk_id

        # Add embedding
        if embedding is not None:
            self._embedding_index[chunk_id] = embedding
        else:
            try:
                self._embedding_index[chunk_id] = self.embedding_service.embed(text)
            except Exception as e:
                logger.warning(f"Failed to index embedding for {chunk_id}: {e}")

    def remove_from_index(self, chunk_id: str, text: Optional[str] = None) -> None:
        """
        Remove content from the deduplication index.

        Args:
            chunk_id: Chunk ID to remove
            text: Original text (needed to remove hash entry)
        """
        # Remove embedding
        if chunk_id in self._embedding_index:
            del self._embedding_index[chunk_id]

        # Remove hash if text provided
        if text:
            content_hash = self.compute_hash(text)
            if content_hash in self._hash_index:
                del self._hash_index[content_hash]

    def deduplicate_chunks(
        self,
        chunks: List[MemoryChunk],
        check_semantic: bool = True,
    ) -> Tuple[List[MemoryChunk], List[Tuple[MemoryChunk, str, str]]]:
        """
        Filter out duplicate chunks from a list.

        Args:
            chunks: List of chunks to deduplicate
            check_semantic: Whether to check semantic similarity

        Returns:
            Tuple of (unique_chunks, duplicate_info)
            duplicate_info contains (chunk, existing_id, method) for each duplicate
        """
        unique_chunks = []
        duplicates = []

        # Track hashes within this batch to avoid self-duplicates
        batch_hashes: Set[str] = set()

        for chunk in chunks:
            # Check within batch first
            chunk_hash = self.compute_hash(chunk.text)
            if chunk_hash in batch_hashes:
                duplicates.append((chunk, "batch_duplicate", "batch_hash"))
                continue

            # Check against index
            is_dup, existing_id, method = self.check_duplicate(
                chunk.text,
                embedding=np.array(chunk.embedding) if chunk.embedding else None,
                check_semantic=check_semantic,
            )

            if is_dup:
                duplicates.append((chunk, existing_id, method))
            else:
                unique_chunks.append(chunk)
                batch_hashes.add(chunk_hash)

        if duplicates:
            logger.info(
                f"Deduplication: {len(unique_chunks)} unique, "
                f"{len(duplicates)} duplicates removed"
            )

        return unique_chunks, duplicates

    def build_index_from_db(self, vector_db) -> int:
        """
        Build deduplication index from existing database content.

        Args:
            vector_db: VectorDB instance to index

        Returns:
            Number of chunks indexed
        """
        from storage.vector_db import VectorDB

        if not isinstance(vector_db, VectorDB):
            raise TypeError("Expected VectorDB instance")

        try:
            # Get all chunks from database
            results = vector_db._collection.get(
                include=["documents", "embeddings"],
            )

            if not results or not results.get("ids"):
                return 0

            indexed = 0
            for i, chunk_id in enumerate(results["ids"]):
                text = results["documents"][i] if results.get("documents") else ""
                embedding = (
                    np.array(results["embeddings"][i])
                    if results.get("embeddings") and results["embeddings"][i]
                    else None
                )

                if text:
                    self.add_to_index(chunk_id, text, embedding)
                    indexed += 1

            logger.info(f"Built deduplication index with {indexed} chunks")
            return indexed

        except Exception as e:
            logger.error(f"Failed to build deduplication index: {e}")
            raise

    def clear_index(self) -> None:
        """Clear the deduplication index."""
        self._hash_index.clear()
        self._embedding_index.clear()
        logger.debug("Deduplication index cleared")

    def get_stats(self) -> Dict[str, int]:
        """
        Get deduplication index statistics.

        Returns:
            Dictionary with index statistics
        """
        return {
            "hash_entries": len(self._hash_index),
            "embedding_entries": len(self._embedding_index),
            "similarity_threshold": self._similarity_threshold,
        }


# Global deduplication service instance
_dedup_service: Optional[DeduplicationService] = None


def get_deduplication_service(
    similarity_threshold: float = 0.95,
) -> DeduplicationService:
    """
    Get the global deduplication service instance.

    Args:
        similarity_threshold: Threshold for semantic similarity

    Returns:
        DeduplicationService instance
    """
    global _dedup_service
    if _dedup_service is None:
        _dedup_service = DeduplicationService(
            similarity_threshold=similarity_threshold
        )
    return _dedup_service
