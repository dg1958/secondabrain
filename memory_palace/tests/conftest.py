"""
Pytest configuration and fixtures for Memory Palace tests.
"""

import os
import pytest
import hashlib
from unittest.mock import patch


# Create a mock embedding function to avoid loading sentence-transformers
class MockEmbeddingFunction:
    """Mock embedding function that returns fixed-size vectors."""

    def __call__(self, input):
        """Return mock embeddings.

        Args:
            input: List of texts to embed (ChromaDB's new API uses 'input' not 'texts')
        """
        return self._embed(input)

    def _embed(self, texts):
        """Generate embeddings for texts."""
        embeddings = []
        for text in texts:
            hash_bytes = hashlib.md5(text.encode()).digest()
            embedding = []
            for i in range(384):
                byte_idx = i % 16
                embedding.append((hash_bytes[byte_idx] + i) / 256.0)
            embeddings.append(embedding)
        return embeddings

    def embed_documents(self, input):
        """Embed documents (for adding to collection)."""
        return self._embed(input)

    def embed_query(self, input):
        """Embed a query (for searching)."""
        if isinstance(input, str):
            return self._embed([input])[0]
        return self._embed(input)

    def name(self):
        """Return the name of this embedding function."""
        return "mock_embedding_function"


def pytest_configure(config):
    """Configure pytest."""
    # Set test environment
    os.environ["MEMORY_PALACE_LOG_LEVEL"] = "WARNING"


@pytest.fixture(scope="session", autouse=True)
def mock_sentence_transformers():
    """Mock the sentence transformers embedding function for all tests."""
    with patch(
        'chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction',
        return_value=MockEmbeddingFunction()
    ):
        yield


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use default event loop policy."""
    import asyncio
    return asyncio.DefaultEventLoopPolicy()
