"""
ChromaDB vector database wrapper with CRUD operations.

This module provides:
- Collection management
- Document storage and retrieval
- Semantic similarity search
- Hybrid search (vector + metadata filtering)
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from loguru import logger

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
except ImportError:
    chromadb = None
    logger.warning("chromadb not installed. Vector database features disabled.")

from config.schema import MemoryChunk, MemoryMetadata, QueryFilter, QueryResult


class VectorDB:
    """
    ChromaDB wrapper for vector storage and retrieval.

    Provides a clean interface for:
    - Storing memory chunks with embeddings and metadata
    - Semantic similarity search
    - Filtered queries combining vector search with metadata
    - CRUD operations on stored memories
    """

    def __init__(
        self,
        persist_directory: str = "./data/chroma_db",
        collection_name: str = "memory_palace",
        embedding_function: Optional[Any] = None,
    ):
        """
        Initialize the vector database.

        Args:
            persist_directory: Path to store the database
            collection_name: Name of the collection to use
            embedding_function: Optional custom embedding function for ChromaDB
        """
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self._client: Optional["chromadb.Client"] = None
        self._collection: Optional[Any] = None
        self._embedding_function = embedding_function

        self._init_db()

    def _init_db(self) -> None:
        """Initialize ChromaDB client and collection."""
        if chromadb is None:
            logger.error("chromadb not installed. Install with: pip install chromadb")
            return

        try:
            # Ensure persist directory exists
            Path(self.persist_directory).mkdir(parents=True, exist_ok=True)

            # Initialize persistent client
            self._client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True,
                ),
            )

            # Get or create collection
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
                embedding_function=self._embedding_function,
            )

            logger.info(
                f"Initialized ChromaDB collection '{self.collection_name}' "
                f"with {self._collection.count()} documents"
            )

        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise

    @property
    def is_available(self) -> bool:
        """Check if the database is available."""
        return self._collection is not None

    @property
    def count(self) -> int:
        """Get the number of documents in the collection."""
        if not self.is_available:
            return 0
        return self._collection.count()

    def add(
        self,
        chunks: Union[MemoryChunk, List[MemoryChunk]],
    ) -> List[str]:
        """
        Add memory chunks to the database.

        Args:
            chunks: Single chunk or list of chunks to add

        Returns:
            List of chunk IDs that were added

        Raises:
            RuntimeError: If database is not available
        """
        if not self.is_available:
            raise RuntimeError("Vector database not available")

        if isinstance(chunks, MemoryChunk):
            chunks = [chunks]

        if not chunks:
            return []

        ids = []
        documents = []
        embeddings = []
        metadatas = []

        for chunk in chunks:
            ids.append(chunk.id)
            documents.append(chunk.text)
            metadatas.append(chunk.metadata.to_chroma_metadata())

            if chunk.embedding is not None:
                embeddings.append(chunk.embedding)

        try:
            add_kwargs = {
                "ids": ids,
                "documents": documents,
                "metadatas": metadatas,
            }

            # Only include embeddings if provided
            if embeddings and len(embeddings) == len(ids):
                add_kwargs["embeddings"] = embeddings

            self._collection.add(**add_kwargs)
            logger.debug(f"Added {len(ids)} chunks to database")
            return ids

        except Exception as e:
            logger.error(f"Failed to add chunks: {e}")
            raise

    def query(
        self,
        query_embedding: Optional[List[float]] = None,
        query_text: Optional[str] = None,
        filters: Optional[QueryFilter] = None,
        top_k: int = 10,
        include_embeddings: bool = False,
    ) -> List[QueryResult]:
        """
        Query the database for similar memories.

        Args:
            query_embedding: Query vector for similarity search
            query_text: Query text (if embedding not provided)
            filters: Metadata filters to apply
            top_k: Number of results to return
            include_embeddings: Whether to include embeddings in results

        Returns:
            List of QueryResult objects
        """
        if not self.is_available:
            raise RuntimeError("Vector database not available")

        # Build where clause from filters
        where_clause = self._build_where_clause(filters) if filters else None

        query_kwargs = {
            "n_results": min(top_k, self.count) if self.count > 0 else top_k,
            "include": ["documents", "metadatas", "distances"],
        }

        if include_embeddings:
            query_kwargs["include"].append("embeddings")

        if where_clause:
            query_kwargs["where"] = where_clause

        try:
            if query_embedding is not None:
                query_kwargs["query_embeddings"] = [query_embedding]
                results = self._collection.query(**query_kwargs)
            elif query_text is not None:
                query_kwargs["query_texts"] = [query_text]
                results = self._collection.query(**query_kwargs)
            else:
                # No query provided, just filter by metadata
                # Use get() instead of query() for metadata-only filtering
                get_kwargs = {"include": ["documents", "metadatas"]}
                if where_clause:
                    get_kwargs["where"] = where_clause
                get_kwargs["limit"] = top_k

                get_results = self._collection.get(**get_kwargs)
                return self._convert_get_results(get_results)

            return self._convert_query_results(results)

        except Exception as e:
            logger.error(f"Query failed: {e}")
            raise

    def _build_where_clause(self, filters: QueryFilter) -> Optional[Dict]:
        """Build ChromaDB where clause from QueryFilter."""
        conditions = []

        # Temporal filters
        if filters.start_date:
            conditions.append({
                "timestamp": {"$gte": filters.start_date.isoformat()}
            })

        if filters.end_date:
            conditions.append({
                "timestamp": {"$lte": filters.end_date.isoformat()}
            })

        # Source filter
        if filters.source:
            conditions.append({
                "source": {"$eq": filters.source.value}
            })

        # Sentiment filters
        if filters.min_sentiment is not None:
            conditions.append({
                "sentiment": {"$gte": filters.min_sentiment}
            })

        if filters.max_sentiment is not None:
            conditions.append({
                "sentiment": {"$lte": filters.max_sentiment}
            })

        # Topic filter (uses $contains for comma-separated string)
        if filters.topics:
            topic_conditions = []
            for topic in filters.topics:
                topic_conditions.append({
                    "topics": {"$contains": topic}
                })
            if len(topic_conditions) == 1:
                conditions.append(topic_conditions[0])
            else:
                conditions.append({"$or": topic_conditions})

        # Participant filter
        if filters.participants:
            participant_conditions = []
            for participant in filters.participants:
                participant_conditions.append({
                    "participants": {"$contains": participant}
                })
            if len(participant_conditions) == 1:
                conditions.append(participant_conditions[0])
            else:
                conditions.append({"$or": participant_conditions})

        # Custom tag filter
        if filters.custom_tags:
            tag_conditions = []
            for tag in filters.custom_tags:
                tag_conditions.append({
                    "custom_tags": {"$contains": tag}
                })
            if len(tag_conditions) == 1:
                conditions.append(tag_conditions[0])
            else:
                conditions.append({"$or": tag_conditions})

        if not conditions:
            return None

        if len(conditions) == 1:
            return conditions[0]

        return {"$and": conditions}

    def _convert_query_results(self, results: Dict) -> List[QueryResult]:
        """Convert ChromaDB query results to QueryResult objects."""
        query_results = []

        if not results or not results.get("ids") or not results["ids"][0]:
            return query_results

        ids = results["ids"][0]
        documents = results["documents"][0] if results.get("documents") else []
        metadatas = results["metadatas"][0] if results.get("metadatas") else []
        distances = results["distances"][0] if results.get("distances") else []

        for i, chunk_id in enumerate(ids):
            # Convert distance to similarity score (cosine distance to similarity)
            distance = distances[i] if i < len(distances) else 0.0
            score = 1.0 - distance  # For cosine distance

            metadata = metadatas[i] if i < len(metadatas) else {}
            text = documents[i] if i < len(documents) else ""

            query_results.append(QueryResult(
                chunk_id=chunk_id,
                text=text,
                score=score,
                metadata=MemoryMetadata.from_chroma_metadata(metadata),
            ))

        return query_results

    def _convert_get_results(self, results: Dict) -> List[QueryResult]:
        """Convert ChromaDB get results to QueryResult objects."""
        query_results = []

        if not results or not results.get("ids"):
            return query_results

        ids = results["ids"]
        documents = results.get("documents", [])
        metadatas = results.get("metadatas", [])

        for i, chunk_id in enumerate(ids):
            metadata = metadatas[i] if i < len(metadatas) else {}
            text = documents[i] if i < len(documents) else ""

            query_results.append(QueryResult(
                chunk_id=chunk_id,
                text=text,
                score=1.0,  # No similarity score for get operations
                metadata=MemoryMetadata.from_chroma_metadata(metadata),
            ))

        return query_results

    def get(self, chunk_ids: Union[str, List[str]]) -> List[QueryResult]:
        """
        Get specific chunks by ID.

        Args:
            chunk_ids: Single ID or list of IDs

        Returns:
            List of QueryResult objects
        """
        if not self.is_available:
            raise RuntimeError("Vector database not available")

        if isinstance(chunk_ids, str):
            chunk_ids = [chunk_ids]

        try:
            results = self._collection.get(
                ids=chunk_ids,
                include=["documents", "metadatas"],
            )
            return self._convert_get_results(results)

        except Exception as e:
            logger.error(f"Failed to get chunks: {e}")
            raise

    def update(
        self,
        chunk_id: str,
        text: Optional[str] = None,
        embedding: Optional[List[float]] = None,
        metadata: Optional[MemoryMetadata] = None,
    ) -> bool:
        """
        Update a chunk's content or metadata.

        Args:
            chunk_id: ID of the chunk to update
            text: New text content
            embedding: New embedding
            metadata: New metadata

        Returns:
            True if update succeeded
        """
        if not self.is_available:
            raise RuntimeError("Vector database not available")

        update_kwargs = {"ids": [chunk_id]}

        if text is not None:
            update_kwargs["documents"] = [text]

        if embedding is not None:
            update_kwargs["embeddings"] = [embedding]

        if metadata is not None:
            update_kwargs["metadatas"] = [metadata.to_chroma_metadata()]

        try:
            self._collection.update(**update_kwargs)
            logger.debug(f"Updated chunk: {chunk_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update chunk {chunk_id}: {e}")
            return False

    def delete(self, chunk_ids: Union[str, List[str]]) -> bool:
        """
        Delete chunks from the database.

        Args:
            chunk_ids: Single ID or list of IDs to delete

        Returns:
            True if deletion succeeded
        """
        if not self.is_available:
            raise RuntimeError("Vector database not available")

        if isinstance(chunk_ids, str):
            chunk_ids = [chunk_ids]

        try:
            self._collection.delete(ids=chunk_ids)
            logger.debug(f"Deleted {len(chunk_ids)} chunks")
            return True

        except Exception as e:
            logger.error(f"Failed to delete chunks: {e}")
            return False

    def delete_by_doc_id(self, doc_id: str) -> int:
        """
        Delete all chunks belonging to a document.

        Args:
            doc_id: Document ID whose chunks should be deleted

        Returns:
            Number of chunks deleted
        """
        if not self.is_available:
            raise RuntimeError("Vector database not available")

        try:
            # Find all chunks with this doc_id
            results = self._collection.get(
                where={"doc_id": {"$eq": doc_id}},
                include=[],
            )

            if not results or not results.get("ids"):
                return 0

            chunk_ids = results["ids"]
            self._collection.delete(ids=chunk_ids)
            logger.info(f"Deleted {len(chunk_ids)} chunks for doc_id: {doc_id}")
            return len(chunk_ids)

        except Exception as e:
            logger.error(f"Failed to delete by doc_id {doc_id}: {e}")
            raise

    def list_doc_ids(self) -> List[str]:
        """
        Get a list of all unique document IDs in the database.

        Returns:
            List of document IDs
        """
        if not self.is_available:
            raise RuntimeError("Vector database not available")

        try:
            results = self._collection.get(include=["metadatas"])

            if not results or not results.get("metadatas"):
                return []

            doc_ids = set()
            for metadata in results["metadatas"]:
                if metadata and "doc_id" in metadata:
                    doc_ids.add(metadata["doc_id"])

            return sorted(list(doc_ids))

        except Exception as e:
            logger.error(f"Failed to list doc_ids: {e}")
            raise

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the database.

        Returns:
            Dictionary with database statistics
        """
        if not self.is_available:
            return {"available": False}

        try:
            total_chunks = self.count
            doc_ids = self.list_doc_ids()

            return {
                "available": True,
                "total_chunks": total_chunks,
                "total_documents": len(doc_ids),
                "collection_name": self.collection_name,
                "persist_directory": self.persist_directory,
            }

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"available": True, "error": str(e)}

    def clear(self) -> bool:
        """
        Clear all data from the collection.

        Returns:
            True if successful
        """
        if not self.is_available:
            raise RuntimeError("Vector database not available")

        try:
            # Delete and recreate the collection
            self._client.delete_collection(self.collection_name)
            self._collection = self._client.create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
                embedding_function=self._embedding_function,
            )
            logger.warning(f"Cleared all data from collection: {self.collection_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to clear collection: {e}")
            return False


# Global database instance
_db_instance: Optional[VectorDB] = None


def get_vector_db(
    persist_directory: str = "./data/chroma_db",
    collection_name: str = "memory_palace",
) -> VectorDB:
    """
    Get the global vector database instance.

    Args:
        persist_directory: Path to database storage
        collection_name: Name of the collection

    Returns:
        VectorDB instance
    """
    global _db_instance
    if _db_instance is None:
        _db_instance = VectorDB(persist_directory, collection_name)
    return _db_instance
