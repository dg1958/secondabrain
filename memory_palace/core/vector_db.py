"""
ChromaDB vector database wrapper for Memory Palace.

Handles storage and retrieval of memory embeddings for semantic search.
"""

import logging
from typing import Optional, Any
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from ..config import get_settings
from .models import Memory

logger = logging.getLogger(__name__)


class VectorDB:
    """
    ChromaDB wrapper for semantic memory search.

    Stores memory content as embeddings and supports similarity search.
    """

    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: Optional[str] = None,
        embedding_model: Optional[str] = None,
    ):
        """
        Initialize the vector database.

        Args:
            persist_directory: Path to store ChromaDB data
            collection_name: Name of the collection
            embedding_model: Sentence transformer model name
        """
        settings = get_settings()

        self.persist_directory = persist_directory or settings.storage.vector_db_path
        self.collection_name = collection_name or settings.vector_db.collection_name
        self.embedding_model = embedding_model or settings.vector_db.embedding_model

        # Ensure directory exists
        Path(self.persist_directory).mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client
        self._client: Optional[chromadb.Client] = None
        self._collection: Optional[chromadb.Collection] = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy initialization of ChromaDB."""
        if self._initialized:
            return

        logger.info(f"Initializing ChromaDB at {self.persist_directory}")

        self._client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True,
            )
        )

        # Get or create collection with sentence transformer embeddings
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
            embedding_function=chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=self.embedding_model
            )
        )

        self._initialized = True
        logger.info(f"ChromaDB initialized with collection '{self.collection_name}'")

    @property
    def collection(self) -> chromadb.Collection:
        """Get the ChromaDB collection."""
        self._ensure_initialized()
        return self._collection

    async def add_memory(self, memory: Memory) -> str:
        """
        Add a memory to the vector database.

        Args:
            memory: The memory to store

        Returns:
            The memory ID
        """
        self._ensure_initialized()

        # Prepare document text for embedding
        document = memory.to_search_text()

        # Prepare metadata (ChromaDB only supports str, int, float, bool)
        metadata = {
            "memory_type": memory.memory_type,
            "importance": memory.importance,
            "created_at": memory.created_at.isoformat(),
            "topics": ",".join(memory.topics) if memory.topics else "",
            "entities": ",".join(memory.entities) if memory.entities else "",
        }

        if memory.occurred_at:
            metadata["occurred_at"] = memory.occurred_at.isoformat()
        if memory.sentiment_score is not None:
            metadata["sentiment_score"] = memory.sentiment_score
        if memory.source:
            metadata["source"] = memory.source

        # Add to collection
        self.collection.add(
            ids=[memory.id],
            documents=[document],
            metadatas=[metadata]
        )

        logger.debug(f"Added memory {memory.id} to vector DB")
        return memory.id

    async def update_memory(self, memory: Memory) -> None:
        """
        Update a memory in the vector database.

        Args:
            memory: The updated memory
        """
        self._ensure_initialized()

        document = memory.to_search_text()

        metadata = {
            "memory_type": memory.memory_type,
            "importance": memory.importance,
            "created_at": memory.created_at.isoformat(),
            "updated_at": memory.updated_at.isoformat(),
            "topics": ",".join(memory.topics) if memory.topics else "",
            "entities": ",".join(memory.entities) if memory.entities else "",
        }

        if memory.occurred_at:
            metadata["occurred_at"] = memory.occurred_at.isoformat()
        if memory.sentiment_score is not None:
            metadata["sentiment_score"] = memory.sentiment_score
        if memory.source:
            metadata["source"] = memory.source

        self.collection.update(
            ids=[memory.id],
            documents=[document],
            metadatas=[metadata]
        )

        logger.debug(f"Updated memory {memory.id} in vector DB")

    async def delete_memory(self, memory_id: str) -> bool:
        """
        Delete a memory from the vector database.

        Args:
            memory_id: ID of the memory to delete

        Returns:
            True if deleted successfully
        """
        self._ensure_initialized()

        try:
            self.collection.delete(ids=[memory_id])
            logger.debug(f"Deleted memory {memory_id} from vector DB")
            return True
        except Exception as e:
            logger.error(f"Failed to delete memory {memory_id}: {e}")
            return False

    async def search(
        self,
        query: str,
        limit: int = 10,
        where: Optional[dict[str, Any]] = None,
        where_document: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """
        Semantic search for memories.

        Args:
            query: Search query text
            limit: Maximum results to return
            where: Metadata filters (ChromaDB where clause)
            where_document: Document content filters

        Returns:
            List of search results with scores
        """
        self._ensure_initialized()

        results = self.collection.query(
            query_texts=[query],
            n_results=limit,
            where=where,
            where_document=where_document,
            include=["documents", "metadatas", "distances"]
        )

        # Convert results to list of dicts
        search_results = []
        if results["ids"] and results["ids"][0]:
            for i, memory_id in enumerate(results["ids"][0]):
                # Convert distance to similarity score (cosine distance to similarity)
                distance = results["distances"][0][i] if results["distances"] else 0
                similarity = 1 - (distance / 2)  # Cosine distance range is [0, 2]

                search_results.append({
                    "id": memory_id,
                    "document": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "similarity": similarity,
                })

        return search_results

    async def get_by_ids(self, ids: list[str]) -> list[dict[str, Any]]:
        """
        Get memories by their IDs.

        Args:
            ids: List of memory IDs

        Returns:
            List of memory data
        """
        self._ensure_initialized()

        if not ids:
            return []

        results = self.collection.get(
            ids=ids,
            include=["documents", "metadatas"]
        )

        memories = []
        if results["ids"]:
            for i, memory_id in enumerate(results["ids"]):
                memories.append({
                    "id": memory_id,
                    "document": results["documents"][i] if results["documents"] else "",
                    "metadata": results["metadatas"][i] if results["metadatas"] else {},
                })

        return memories

    async def get_count(self) -> int:
        """Get total number of memories in the collection."""
        self._ensure_initialized()
        return self.collection.count()

    async def clear(self) -> None:
        """Clear all memories from the collection."""
        self._ensure_initialized()
        # Delete and recreate collection
        self._client.delete_collection(self.collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
            embedding_function=chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=self.embedding_model
            )
        )
        logger.info("Cleared vector database")


# Global instance for convenience
_vector_db: Optional[VectorDB] = None


def get_vector_db() -> VectorDB:
    """Get the global VectorDB instance."""
    global _vector_db
    if _vector_db is None:
        _vector_db = VectorDB()
    return _vector_db


def reset_vector_db() -> None:
    """Reset the global VectorDB instance (for testing)."""
    global _vector_db
    _vector_db = None
