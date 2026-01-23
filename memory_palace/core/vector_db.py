"""Vector database wrapper using ChromaDB for Memory Palace."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

logger = logging.getLogger(__name__)


class VectorDB:
    """
    ChromaDB wrapper for vector storage and semantic search.

    Handles embedding generation, storage, and retrieval of memories
    with support for metadata filtering.
    """

    COLLECTION_NAME = "memory_palace"

    def __init__(
        self,
        persist_path: str,
        embedding_model: str = "all-MiniLM-L6-v2"
    ):
        """
        Initialize the vector database.

        Args:
            persist_path: Path to persist ChromaDB data
            embedding_model: Sentence transformer model name for embeddings
        """
        self.persist_path = Path(persist_path)
        self.embedding_model = embedding_model
        self._client: Optional[chromadb.PersistentClient] = None
        self._collection: Optional[chromadb.Collection] = None
        self._embedding_function = None

    async def initialize(self) -> None:
        """Initialize the database and embedding model."""
        # Create persist directory if needed
        self.persist_path.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client
        self._client = chromadb.PersistentClient(
            path=str(self.persist_path),
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        # Load embedding function
        try:
            from chromadb.utils import embedding_functions
            self._embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=self.embedding_model
            )
            logger.info(f"Loaded embedding model: {self.embedding_model}")
        except Exception as e:
            logger.warning(f"Failed to load embedding model: {e}. Using default.")
            self._embedding_function = None

        # Get or create collection
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            embedding_function=self._embedding_function,
            metadata={"hnsw:space": "cosine"}
        )

        logger.info(f"Vector DB initialized at {self.persist_path}")
        logger.info(f"Collection '{self.COLLECTION_NAME}' has {self._collection.count()} documents")

    def _ensure_initialized(self) -> None:
        """Ensure the database is initialized."""
        if self._collection is None:
            raise RuntimeError("VectorDB not initialized. Call initialize() first.")

    def _serialize_metadata(self, metadata: dict) -> dict:
        """Convert metadata to ChromaDB-compatible format."""
        serialized = {}
        for key, value in metadata.items():
            if value is None:
                continue
            elif isinstance(value, datetime):
                serialized[key] = value.isoformat()
            elif isinstance(value, (list, dict)):
                import json
                serialized[key] = json.dumps(value)
            elif isinstance(value, bool):
                serialized[key] = str(value).lower()
            else:
                serialized[key] = value
        return serialized

    def _deserialize_metadata(self, metadata: dict) -> dict:
        """Convert ChromaDB metadata back to Python types."""
        import json
        deserialized = {}
        for key, value in metadata.items():
            if value is None:
                continue
            # Try to parse as JSON for lists/dicts
            if isinstance(value, str):
                if value.startswith('[') or value.startswith('{'):
                    try:
                        deserialized[key] = json.loads(value)
                        continue
                    except json.JSONDecodeError:
                        pass
                # Try to parse as datetime
                if 'T' in value and (value.endswith('Z') or '+' in value or len(value) > 20):
                    try:
                        from dateutil.parser import parse
                        deserialized[key] = parse(value)
                        continue
                    except (ValueError, ImportError):
                        pass
                # Handle booleans
                if value.lower() in ('true', 'false'):
                    deserialized[key] = value.lower() == 'true'
                    continue
            deserialized[key] = value
        return deserialized

    async def add_memory(
        self,
        id: str,
        content: str,
        metadata: dict
    ) -> None:
        """
        Add a memory to the vector database.

        Args:
            id: Unique identifier for the memory
            content: Text content to embed and store
            metadata: Associated metadata
        """
        self._ensure_initialized()

        serialized_meta = self._serialize_metadata(metadata)

        self._collection.add(
            ids=[id],
            documents=[content],
            metadatas=[serialized_meta]
        )

        logger.debug(f"Added memory {id} to vector DB")

    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[dict] = None,
        min_relevance: float = 0.0
    ) -> list[dict]:
        """
        Search for similar memories.

        Args:
            query: Search query text
            limit: Maximum number of results
            filters: Metadata filters to apply
            min_relevance: Minimum similarity score (0-1)

        Returns:
            List of matching memories with scores
        """
        self._ensure_initialized()

        # Build where clause from filters
        where = None
        if filters:
            where = self._build_where_clause(filters)

        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=limit,
                where=where,
                include=["documents", "metadatas", "distances"]
            )
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []

        # Process results
        memories = []
        if results and results['ids'] and results['ids'][0]:
            for i, id in enumerate(results['ids'][0]):
                # ChromaDB returns distances, convert to similarity
                # For cosine distance: similarity = 1 - distance
                distance = results['distances'][0][i] if results['distances'] else 0
                similarity = 1 - distance

                if similarity < min_relevance:
                    continue

                memory = {
                    'id': id,
                    'content': results['documents'][0][i] if results['documents'] else '',
                    'metadata': self._deserialize_metadata(
                        results['metadatas'][0][i] if results['metadatas'] else {}
                    ),
                    'relevance_score': similarity
                }
                memories.append(memory)

        return memories

    def _build_where_clause(self, filters: dict) -> Optional[dict]:
        """Build ChromaDB where clause from filters."""
        conditions = []

        for key, value in filters.items():
            if value is None:
                continue

            if key == 'date_from':
                conditions.append({
                    'timestamp': {'$gte': value.isoformat() if hasattr(value, 'isoformat') else value}
                })
            elif key == 'date_to':
                conditions.append({
                    'timestamp': {'$lte': value.isoformat() if hasattr(value, 'isoformat') else value}
                })
            elif key == 'memory_types' and isinstance(value, list):
                if len(value) == 1:
                    conditions.append({'memory_type': value[0]})
                else:
                    conditions.append({'memory_type': {'$in': value}})
            elif key == 'importance':
                conditions.append({'importance': value})
            elif key == 'memory_type':
                conditions.append({'memory_type': value})
            # Topics and entities are stored as JSON strings, so we can't filter them directly
            # Those need to be filtered post-query

        if not conditions:
            return None
        elif len(conditions) == 1:
            return conditions[0]
        else:
            return {'$and': conditions}

    async def get_by_id(self, id: str) -> Optional[dict]:
        """
        Get a memory by its ID.

        Args:
            id: Memory ID

        Returns:
            Memory dict or None if not found
        """
        self._ensure_initialized()

        try:
            results = self._collection.get(
                ids=[id],
                include=["documents", "metadatas"]
            )

            if results and results['ids']:
                return {
                    'id': results['ids'][0],
                    'content': results['documents'][0] if results['documents'] else '',
                    'metadata': self._deserialize_metadata(
                        results['metadatas'][0] if results['metadatas'] else {}
                    )
                }
        except Exception as e:
            logger.error(f"Error getting memory {id}: {e}")

        return None

    async def update(
        self,
        id: str,
        content: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> bool:
        """
        Update a memory.

        Args:
            id: Memory ID
            content: New content (if updating)
            metadata: New metadata (if updating)

        Returns:
            True if updated, False if not found
        """
        self._ensure_initialized()

        try:
            update_kwargs = {'ids': [id]}

            if content is not None:
                update_kwargs['documents'] = [content]

            if metadata is not None:
                update_kwargs['metadatas'] = [self._serialize_metadata(metadata)]

            self._collection.update(**update_kwargs)
            logger.debug(f"Updated memory {id}")
            return True
        except Exception as e:
            logger.error(f"Error updating memory {id}: {e}")
            return False

    async def delete(self, id: str) -> bool:
        """
        Delete a memory.

        Args:
            id: Memory ID

        Returns:
            True if deleted, False if error
        """
        self._ensure_initialized()

        try:
            self._collection.delete(ids=[id])
            logger.debug(f"Deleted memory {id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting memory {id}: {e}")
            return False

    async def get_all_ids(self) -> list[str]:
        """
        Get all memory IDs in the database.

        Returns:
            List of all memory IDs
        """
        self._ensure_initialized()

        try:
            results = self._collection.get(include=[])
            return results['ids'] if results else []
        except Exception as e:
            logger.error(f"Error getting all IDs: {e}")
            return []

    async def count(self) -> int:
        """Get total number of memories."""
        self._ensure_initialized()
        return self._collection.count()

    async def get_all(
        self,
        limit: int = 1000,
        offset: int = 0
    ) -> list[dict]:
        """
        Get all memories (paginated).

        Args:
            limit: Maximum number to return
            offset: Number to skip

        Returns:
            List of memory dicts
        """
        self._ensure_initialized()

        try:
            results = self._collection.get(
                include=["documents", "metadatas"],
                limit=limit,
                offset=offset
            )

            memories = []
            if results and results['ids']:
                for i, id in enumerate(results['ids']):
                    memories.append({
                        'id': id,
                        'content': results['documents'][i] if results['documents'] else '',
                        'metadata': self._deserialize_metadata(
                            results['metadatas'][i] if results['metadatas'] else {}
                        )
                    })
            return memories
        except Exception as e:
            logger.error(f"Error getting all memories: {e}")
            return []

    async def reset(self) -> None:
        """Reset the database (delete all data)."""
        self._ensure_initialized()

        self._client.delete_collection(self.COLLECTION_NAME)
        self._collection = self._client.create_collection(
            name=self.COLLECTION_NAME,
            embedding_function=self._embedding_function,
            metadata={"hnsw:space": "cosine"}
        )
        logger.warning("Vector DB reset - all data deleted")
