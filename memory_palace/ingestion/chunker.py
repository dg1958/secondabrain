"""
Intelligent text chunking algorithms for Memory Palace.

This module provides:
- Semantic chunking (split on meaningful boundaries)
- Fixed-size chunking with overlap
- Paragraph-based chunking
- Token counting and management
"""

import re
from typing import List

from loguru import logger

try:
    import tiktoken
except ImportError:
    tiktoken = None
    logger.warning("tiktoken not installed. Using approximate token counting.")

from config.schema import Document, MemoryChunk, MemoryMetadata


class TextChunker:
    """
    Intelligent text chunking service.

    Supports multiple chunking strategies:
    - semantic: Split on natural boundaries (paragraphs, sentences)
    - fixed: Fixed-size chunks with configurable overlap
    - paragraph: Split on paragraph boundaries
    """

    def __init__(
        self,
        target_tokens: int = 500,
        overlap_tokens: int = 50,
        min_chunk_tokens: int = 100,
        max_chunk_tokens: int = 1000,
        strategy: str = "semantic",
    ):
        """
        Initialize the chunker.

        Args:
            target_tokens: Target number of tokens per chunk
            overlap_tokens: Overlap between consecutive chunks
            min_chunk_tokens: Minimum chunk size
            max_chunk_tokens: Maximum chunk size
            strategy: Chunking strategy (semantic, fixed, paragraph)
        """
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens
        self.min_chunk_tokens = min_chunk_tokens
        self.max_chunk_tokens = max_chunk_tokens
        self.strategy = strategy

        # Initialize tokenizer
        self._tokenizer = None
        if tiktoken is not None:
            try:
                self._tokenizer = tiktoken.get_encoding("cl100k_base")
            except Exception as e:
                logger.warning(f"Failed to load tiktoken encoder: {e}")

        # Sentence separators for semantic chunking
        self._sentence_separators = [
            "\n\n",  # Paragraph break
            "\n",    # Line break
            ". ",    # Period
            "! ",    # Exclamation
            "? ",    # Question
            "; ",    # Semicolon
            ": ",    # Colon
        ]

    def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in text.

        Args:
            text: Text to count tokens for

        Returns:
            Approximate token count
        """
        if self._tokenizer is not None:
            return len(self._tokenizer.encode(text))

        # Fallback: approximate with word count * 1.3
        return int(len(text.split()) * 1.3)

    def count_words(self, text: str) -> int:
        """
        Count the number of words in text.

        Args:
            text: Text to count words for

        Returns:
            Word count
        """
        return len(text.split())

    def chunk(self, text: str) -> List[str]:
        """
        Split text into chunks using the configured strategy.

        Args:
            text: Text to chunk

        Returns:
            List of text chunks
        """
        if not text or not text.strip():
            return []

        if self.strategy == "semantic":
            return self._semantic_chunk(text)
        elif self.strategy == "fixed":
            return self._fixed_chunk(text)
        elif self.strategy == "paragraph":
            return self._paragraph_chunk(text)
        else:
            logger.warning(f"Unknown strategy '{self.strategy}', using semantic")
            return self._semantic_chunk(text)

    def _semantic_chunk(self, text: str) -> List[str]:
        """
        Split text on semantic boundaries (sentences, paragraphs).

        This tries to create chunks that end at natural boundaries
        while staying close to the target size.

        Args:
            text: Text to chunk

        Returns:
            List of semantically coherent chunks
        """
        # First split into sentences/segments
        segments = self._split_into_segments(text)

        if not segments:
            return [text] if text.strip() else []

        chunks = []
        current_chunk = []
        current_tokens = 0

        for segment in segments:
            segment_tokens = self.count_tokens(segment)

            # Handle segments that are too large
            if segment_tokens > self.max_chunk_tokens:
                # Save current chunk if any
                if current_chunk:
                    chunk_text = "".join(current_chunk).strip()
                    if chunk_text:
                        chunks.append(chunk_text)
                    current_chunk = []
                    current_tokens = 0

                # Split large segment
                sub_chunks = self._split_large_segment(segment)
                chunks.extend(sub_chunks)
                continue

            # Check if adding this segment exceeds target
            if current_tokens + segment_tokens > self.target_tokens:
                # Save current chunk if it meets minimum
                if current_tokens >= self.min_chunk_tokens:
                    chunk_text = "".join(current_chunk).strip()
                    if chunk_text:
                        chunks.append(chunk_text)

                    # Start new chunk with overlap
                    if self.overlap_tokens > 0 and current_chunk:
                        overlap = self._get_overlap(current_chunk)
                        current_chunk = [overlap, segment] if overlap else [segment]
                        current_tokens = self.count_tokens("".join(current_chunk))
                    else:
                        current_chunk = [segment]
                        current_tokens = segment_tokens
                else:
                    # Chunk too small, add segment anyway
                    current_chunk.append(segment)
                    current_tokens += segment_tokens
            else:
                current_chunk.append(segment)
                current_tokens += segment_tokens

        # Don't forget the last chunk
        if current_chunk:
            chunk_text = "".join(current_chunk).strip()
            if chunk_text and self.count_tokens(chunk_text) >= self.min_chunk_tokens:
                chunks.append(chunk_text)
            elif chunk_text and chunks:
                # Merge with previous if too small
                chunks[-1] = chunks[-1] + " " + chunk_text
            elif chunk_text:
                chunks.append(chunk_text)

        return chunks

    def _split_into_segments(self, text: str) -> List[str]:
        """
        Split text into segments at natural boundaries.

        Args:
            text: Text to split

        Returns:
            List of text segments
        """
        segments = [text]

        for separator in self._sentence_separators:
            new_segments = []
            for segment in segments:
                parts = segment.split(separator)
                for i, part in enumerate(parts):
                    if i < len(parts) - 1:
                        new_segments.append(part + separator)
                    elif part:
                        new_segments.append(part)
            segments = new_segments

        return [s for s in segments if s.strip()]

    def _split_large_segment(self, segment: str) -> List[str]:
        """
        Split a segment that's too large into smaller pieces.

        Args:
            segment: Large segment to split

        Returns:
            List of smaller chunks
        """
        words = segment.split()
        chunks = []
        current_words = []
        current_tokens = 0

        for word in words:
            word_tokens = self.count_tokens(word + " ")

            if current_tokens + word_tokens > self.target_tokens:
                if current_words:
                    chunks.append(" ".join(current_words))
                current_words = [word]
                current_tokens = word_tokens
            else:
                current_words.append(word)
                current_tokens += word_tokens

        if current_words:
            chunks.append(" ".join(current_words))

        return chunks

    def _get_overlap(self, segments: List[str]) -> str:
        """
        Get overlap text from the end of segments.

        Args:
            segments: List of text segments

        Returns:
            Overlap text (up to overlap_tokens)
        """
        full_text = "".join(segments)
        words = full_text.split()

        overlap_words = []
        current_tokens = 0

        # Work backwards from the end
        for word in reversed(words):
            word_tokens = self.count_tokens(word + " ")
            if current_tokens + word_tokens > self.overlap_tokens:
                break
            overlap_words.insert(0, word)
            current_tokens += word_tokens

        return " ".join(overlap_words) + " " if overlap_words else ""

    def _fixed_chunk(self, text: str) -> List[str]:
        """
        Split text into fixed-size chunks with overlap.

        Args:
            text: Text to chunk

        Returns:
            List of fixed-size chunks
        """
        words = text.split()
        if not words:
            return []

        # Calculate words per chunk (approximate)
        words_per_chunk = int(self.target_tokens / 1.3)
        overlap_words = int(self.overlap_tokens / 1.3)

        chunks = []
        start = 0

        while start < len(words):
            end = min(start + words_per_chunk, len(words))
            chunk = " ".join(words[start:end])
            chunks.append(chunk)

            # Move start with overlap
            start = end - overlap_words if end < len(words) else end

        return chunks

    def _paragraph_chunk(self, text: str) -> List[str]:
        """
        Split text on paragraph boundaries.

        Args:
            text: Text to chunk

        Returns:
            List of paragraphs (may be combined if too small)
        """
        # Split on double newlines
        paragraphs = re.split(r"\n\s*\n", text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        if not paragraphs:
            return []

        # Combine small paragraphs
        chunks = []
        current_chunk = []
        current_tokens = 0

        for para in paragraphs:
            para_tokens = self.count_tokens(para)

            if para_tokens > self.max_chunk_tokens:
                # Save current and split large paragraph
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = []
                    current_tokens = 0

                # Split the large paragraph
                sub_chunks = self._semantic_chunk(para)
                chunks.extend(sub_chunks)
            elif current_tokens + para_tokens > self.target_tokens:
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_tokens = para_tokens
            else:
                current_chunk.append(para)
                current_tokens += para_tokens

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks

    def chunk_document(
        self,
        document: Document,
        generate_embeddings: bool = False,
    ) -> List[MemoryChunk]:
        """
        Chunk a document and create MemoryChunk objects.

        Args:
            document: Document to chunk
            generate_embeddings: Whether to generate embeddings

        Returns:
            List of MemoryChunk objects
        """
        text_chunks = self.chunk(document.content)

        if not text_chunks:
            return []

        memory_chunks = []

        for i, text in enumerate(text_chunks):
            # Create metadata for this chunk
            chunk_metadata = MemoryMetadata(
                doc_id=document.id,
                chunk_index=i,
                total_chunks=len(text_chunks),
                timestamp=document.metadata.timestamp,
                source=document.metadata.source,
                source_file=document.metadata.source_file,
                participants=document.metadata.participants.copy(),
                topics=document.metadata.topics.copy(),
                entities=document.metadata.entities.copy(),
                sentiment=document.metadata.sentiment,
                sentiment_label=document.metadata.sentiment_label,
                custom_tags=document.metadata.custom_tags.copy(),
                conversation_id=document.metadata.conversation_id,
                platform=document.metadata.platform,
                language=document.metadata.language,
                word_count=self.count_words(text),
                token_count=self.count_tokens(text),
            )

            chunk = MemoryChunk(
                id=chunk_metadata.chunk_id,
                text=text,
                metadata=chunk_metadata,
            )

            memory_chunks.append(chunk)

        logger.debug(
            f"Chunked document {document.id} into {len(memory_chunks)} chunks"
        )

        return memory_chunks


def chunk_document(
    document: Document,
    target_tokens: int = 500,
    overlap_tokens: int = 50,
    strategy: str = "semantic",
) -> List[MemoryChunk]:
    """
    Convenience function to chunk a document.

    Args:
        document: Document to chunk
        target_tokens: Target tokens per chunk
        overlap_tokens: Overlap between chunks
        strategy: Chunking strategy

    Returns:
        List of MemoryChunk objects
    """
    chunker = TextChunker(
        target_tokens=target_tokens,
        overlap_tokens=overlap_tokens,
        strategy=strategy,
    )
    return chunker.chunk_document(document)
