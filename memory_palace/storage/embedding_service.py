"""
Embedding generation service using sentence-transformers.

This module handles:
- Loading and managing the embedding model
- Generating embeddings for text
- Batch embedding processing
"""

from typing import List, Optional, Union

import numpy as np
from loguru import logger

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None
    logger.warning("sentence-transformers not installed. Embedding features disabled.")


class EmbeddingService:
    """
    Service for generating text embeddings using sentence-transformers.

    Uses the all-MiniLM-L6-v2 model by default, which provides a good
    balance between quality and speed for semantic search.
    """

    _instance: Optional["EmbeddingService"] = None
    _model: Optional["SentenceTransformer"] = None

    def __new__(cls, model_name: str = "all-MiniLM-L6-v2", device: str = "cpu") -> "EmbeddingService":
        """
        Singleton pattern to avoid loading the model multiple times.

        Args:
            model_name: Name of the sentence-transformers model
            device: Device to use ("cpu", "cuda", "mps")
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_model(model_name, device)
        return cls._instance

    def _init_model(self, model_name: str, device: str) -> None:
        """Initialize the embedding model."""
        self.model_name = model_name
        self.device = device
        self._embedding_dim: Optional[int] = None

        if SentenceTransformer is None:
            logger.error(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )
            return

        try:
            logger.info(f"Loading embedding model: {model_name} on {device}")
            self._model = SentenceTransformer(model_name, device=device)
            self._embedding_dim = self._model.get_sentence_embedding_dimension()
            logger.info(
                f"Model loaded. Embedding dimension: {self._embedding_dim}"
            )
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            self._model = None

    @property
    def embedding_dimension(self) -> int:
        """Get the dimensionality of the embeddings."""
        if self._embedding_dim is None:
            # Default dimension for all-MiniLM-L6-v2
            return 384
        return self._embedding_dim

    @property
    def is_available(self) -> bool:
        """Check if the embedding service is available."""
        return self._model is not None

    def embed(
        self,
        text: Union[str, List[str]],
        normalize: bool = True,
        batch_size: int = 32,
        show_progress: bool = False,
    ) -> np.ndarray:
        """
        Generate embeddings for text.

        Args:
            text: Single string or list of strings to embed
            normalize: Whether to normalize embeddings to unit length
            batch_size: Batch size for processing multiple texts
            show_progress: Show progress bar for batch processing

        Returns:
            numpy array of embeddings. Shape: (embedding_dim,) for single text,
            (n_texts, embedding_dim) for multiple texts.

        Raises:
            RuntimeError: If embedding model is not available
        """
        if not self.is_available:
            raise RuntimeError(
                "Embedding model not available. "
                "Ensure sentence-transformers is installed."
            )

        if isinstance(text, str):
            texts = [text]
            single_input = True
        else:
            texts = text
            single_input = False

        try:
            embeddings = self._model.encode(
                texts,
                normalize_embeddings=normalize,
                batch_size=batch_size,
                show_progress_bar=show_progress,
                convert_to_numpy=True,
            )

            if single_input:
                return embeddings[0]
            return embeddings

        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise

    def embed_query(self, query: str, normalize: bool = True) -> np.ndarray:
        """
        Generate embedding for a search query.

        This is a convenience method for embedding search queries.
        Some models may handle queries differently than documents.

        Args:
            query: Search query text
            normalize: Whether to normalize the embedding

        Returns:
            Query embedding as numpy array
        """
        return self.embed(query, normalize=normalize)

    def embed_documents(
        self,
        documents: List[str],
        normalize: bool = True,
        batch_size: int = 32,
        show_progress: bool = True,
    ) -> np.ndarray:
        """
        Generate embeddings for multiple documents.

        Args:
            documents: List of document texts
            normalize: Whether to normalize embeddings
            batch_size: Processing batch size
            show_progress: Show progress bar

        Returns:
            Document embeddings as numpy array of shape (n_docs, embedding_dim)
        """
        if not documents:
            return np.array([])

        return self.embed(
            documents,
            normalize=normalize,
            batch_size=batch_size,
            show_progress=show_progress,
        )

    def compute_similarity(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray,
    ) -> float:
        """
        Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding
            embedding2: Second embedding

        Returns:
            Cosine similarity score (0 to 1 for normalized embeddings)
        """
        # Ensure 1D arrays
        e1 = embedding1.flatten()
        e2 = embedding2.flatten()

        # Compute cosine similarity
        dot_product = np.dot(e1, e2)
        norm1 = np.linalg.norm(e1)
        norm2 = np.linalg.norm(e2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def find_most_similar(
        self,
        query_embedding: np.ndarray,
        embeddings: np.ndarray,
        top_k: int = 10,
    ) -> List[tuple]:
        """
        Find most similar embeddings to a query.

        Args:
            query_embedding: Query embedding vector
            embeddings: Matrix of embeddings to search
            top_k: Number of top results to return

        Returns:
            List of (index, similarity_score) tuples, sorted by similarity
        """
        if len(embeddings) == 0:
            return []

        # Compute similarities
        query = query_embedding.flatten()
        similarities = np.dot(embeddings, query) / (
            np.linalg.norm(embeddings, axis=1) * np.linalg.norm(query)
        )

        # Get top-k indices
        top_indices = np.argsort(similarities)[::-1][:top_k]

        return [(int(idx), float(similarities[idx])) for idx in top_indices]

    def reload_model(self, model_name: Optional[str] = None, device: Optional[str] = None) -> None:
        """
        Reload the embedding model.

        Args:
            model_name: New model name (optional)
            device: New device (optional)
        """
        new_model = model_name or self.model_name
        new_device = device or self.device

        logger.info(f"Reloading embedding model: {new_model}")
        self._init_model(new_model, new_device)


# Global embedding service instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service(
    model_name: str = "all-MiniLM-L6-v2",
    device: str = "cpu",
) -> EmbeddingService:
    """
    Get the global embedding service instance.

    Args:
        model_name: Name of the embedding model
        device: Device to use

    Returns:
        EmbeddingService instance
    """
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService(model_name, device)
    return _embedding_service
