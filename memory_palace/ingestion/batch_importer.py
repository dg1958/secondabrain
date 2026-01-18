"""
Batch import utilities for Memory Palace.

This module provides:
- Directory batch import
- Watch folder automatic ingestion
- Progress tracking and reporting
- Incremental import support
"""

import asyncio
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Union

from loguru import logger

from config.schema import (
    Document,
    IngestionResult,
    MemoryChunk,
    MemoryMetadata,
    SourceType,
)
from ingestion.chunker import TextChunker
from ingestion.metadata_extractor import MetadataExtractor, get_metadata_extractor
from ingestion.transcript_parser import TranscriptParser, get_parser
from storage.deduplication import DeduplicationService, get_deduplication_service
from storage.embedding_service import EmbeddingService, get_embedding_service
from storage.vector_db import VectorDB, get_vector_db


class BatchImporter:
    """
    Batch import service for ingesting documents.

    Supports:
    - Single file import
    - Directory batch import
    - Watch folder monitoring
    - Progress callbacks
    - Automatic metadata extraction
    - Deduplication
    """

    def __init__(
        self,
        vector_db: Optional[VectorDB] = None,
        embedding_service: Optional[EmbeddingService] = None,
        dedup_service: Optional[DeduplicationService] = None,
        metadata_extractor: Optional[MetadataExtractor] = None,
        transcript_parser: Optional[TranscriptParser] = None,
        chunker: Optional[TextChunker] = None,
    ):
        """
        Initialize the batch importer.

        Args:
            vector_db: Vector database for storage
            embedding_service: Service for generating embeddings
            dedup_service: Service for deduplication
            metadata_extractor: Service for metadata extraction
            transcript_parser: Parser for various formats
            chunker: Text chunking service
        """
        self._vector_db = vector_db
        self._embedding_service = embedding_service
        self._dedup_service = dedup_service
        self._metadata_extractor = metadata_extractor
        self._transcript_parser = transcript_parser
        self._chunker = chunker

        # Watch folder state
        self._watching = False
        self._processed_files: Set[str] = set()

    @property
    def vector_db(self) -> VectorDB:
        """Get the vector database, initializing if needed."""
        if self._vector_db is None:
            self._vector_db = get_vector_db()
        return self._vector_db

    @property
    def embedding_service(self) -> EmbeddingService:
        """Get the embedding service, initializing if needed."""
        if self._embedding_service is None:
            self._embedding_service = get_embedding_service()
        return self._embedding_service

    @property
    def dedup_service(self) -> DeduplicationService:
        """Get the deduplication service, initializing if needed."""
        if self._dedup_service is None:
            self._dedup_service = get_deduplication_service()
        return self._dedup_service

    @property
    def metadata_extractor(self) -> MetadataExtractor:
        """Get the metadata extractor, initializing if needed."""
        if self._metadata_extractor is None:
            self._metadata_extractor = get_metadata_extractor()
        return self._metadata_extractor

    @property
    def transcript_parser(self) -> TranscriptParser:
        """Get the transcript parser, initializing if needed."""
        if self._transcript_parser is None:
            self._transcript_parser = get_parser()
        return self._transcript_parser

    @property
    def chunker(self) -> TextChunker:
        """Get the chunker, initializing if needed."""
        if self._chunker is None:
            self._chunker = TextChunker()
        return self._chunker

    def import_file(
        self,
        file_path: Union[str, Path],
        source: SourceType = SourceType.IMPORT,
        custom_tags: Optional[List[str]] = None,
        extract_metadata: bool = True,
        check_duplicates: bool = True,
    ) -> IngestionResult:
        """
        Import a single file.

        Args:
            file_path: Path to the file
            source: Source type for metadata
            custom_tags: Custom tags to apply
            extract_metadata: Whether to extract NER/sentiment/topics
            check_duplicates: Whether to check for duplicates

        Returns:
            IngestionResult with import status
        """
        start_time = time.time()
        file_path = Path(file_path)

        if not file_path.exists():
            return IngestionResult(
                doc_id="",
                success=False,
                error_message=f"File not found: {file_path}",
                processing_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            # Parse the file
            document = self.transcript_parser.parse_file(
                file_path,
                source=source,
                custom_tags=custom_tags or [],
            )

            # Import the document
            result = self.import_document(
                document,
                extract_metadata=extract_metadata,
                check_duplicates=check_duplicates,
            )

            result.processing_time_ms = (time.time() - start_time) * 1000
            return result

        except Exception as e:
            logger.error(f"Failed to import {file_path}: {e}")
            return IngestionResult(
                doc_id="",
                success=False,
                error_message=str(e),
                processing_time_ms=(time.time() - start_time) * 1000,
            )

    def import_document(
        self,
        document: Document,
        extract_metadata: bool = True,
        check_duplicates: bool = True,
    ) -> IngestionResult:
        """
        Import a parsed document.

        Args:
            document: Document to import
            extract_metadata: Whether to extract metadata
            check_duplicates: Whether to check for duplicates

        Returns:
            IngestionResult with import status
        """
        start_time = time.time()

        try:
            # Extract metadata if enabled
            if extract_metadata:
                document.metadata = self.metadata_extractor.enrich_metadata(
                    document.content,
                    document.metadata,
                )

            # Chunk the document
            chunks = self.chunker.chunk_document(document)

            if not chunks:
                return IngestionResult(
                    doc_id=document.id,
                    success=False,
                    error_message="No chunks created (document may be empty)",
                    processing_time_ms=(time.time() - start_time) * 1000,
                )

            # Generate embeddings
            texts = [chunk.text for chunk in chunks]
            embeddings = self.embedding_service.embed_documents(
                texts,
                show_progress=False,
            )

            for i, chunk in enumerate(chunks):
                chunk.embedding = embeddings[i].tolist()

            # Check for duplicates
            if check_duplicates:
                unique_chunks, duplicates = self.dedup_service.deduplicate_chunks(
                    chunks,
                    check_semantic=True,
                )

                if len(unique_chunks) == 0:
                    return IngestionResult(
                        doc_id=document.id,
                        success=True,
                        chunks_created=0,
                        duplicate=True,
                        processing_time_ms=(time.time() - start_time) * 1000,
                    )

                chunks = unique_chunks

            # Store in vector database
            chunk_ids = self.vector_db.add(chunks)

            # Add to deduplication index
            for chunk in chunks:
                self.dedup_service.add_to_index(
                    chunk.id,
                    chunk.text,
                    embedding=embeddings[chunks.index(chunk)] if chunk.embedding else None,
                )

            logger.info(
                f"Imported document {document.id} with {len(chunk_ids)} chunks"
            )

            return IngestionResult(
                doc_id=document.id,
                success=True,
                chunks_created=len(chunk_ids),
                processing_time_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            logger.error(f"Failed to import document {document.id}: {e}")
            return IngestionResult(
                doc_id=document.id,
                success=False,
                error_message=str(e),
                processing_time_ms=(time.time() - start_time) * 1000,
            )

    def import_directory(
        self,
        directory: Union[str, Path],
        patterns: Optional[List[str]] = None,
        recursive: bool = True,
        source: SourceType = SourceType.IMPORT,
        custom_tags: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        move_processed: bool = False,
        processed_dir: Optional[Union[str, Path]] = None,
    ) -> Dict[str, IngestionResult]:
        """
        Import all matching files from a directory.

        Args:
            directory: Directory to import from
            patterns: File patterns to match (e.g., ["*.txt", "*.json"])
            recursive: Whether to search subdirectories
            source: Source type for metadata
            custom_tags: Custom tags to apply to all files
            progress_callback: Callback(current, total, filename) for progress
            move_processed: Whether to move processed files
            processed_dir: Directory to move processed files to

        Returns:
            Dictionary mapping filenames to IngestionResults
        """
        directory = Path(directory)
        patterns = patterns or ["*.txt", "*.md", "*.json"]

        if not directory.exists():
            logger.error(f"Directory not found: {directory}")
            return {}

        # Find matching files
        files = []
        for pattern in patterns:
            if recursive:
                files.extend(directory.rglob(pattern))
            else:
                files.extend(directory.glob(pattern))

        # Remove duplicates and sort
        files = sorted(set(files))
        total_files = len(files)

        logger.info(f"Found {total_files} files to import from {directory}")

        results = {}
        for i, file_path in enumerate(files):
            if progress_callback:
                progress_callback(i + 1, total_files, str(file_path.name))

            result = self.import_file(
                file_path,
                source=source,
                custom_tags=custom_tags,
            )

            results[str(file_path)] = result

            # Move processed file if requested
            if move_processed and result.success and processed_dir:
                self._move_processed_file(file_path, Path(processed_dir))

        # Summary
        successful = sum(1 for r in results.values() if r.success)
        duplicates = sum(1 for r in results.values() if r.duplicate)
        failed = sum(1 for r in results.values() if not r.success)

        logger.info(
            f"Import complete: {successful} successful, "
            f"{duplicates} duplicates, {failed} failed"
        )

        return results

    def _move_processed_file(
        self,
        source_path: Path,
        dest_dir: Path,
    ) -> None:
        """Move a processed file to the destination directory."""
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)

            # Add timestamp to avoid conflicts
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest_name = f"{timestamp}_{source_path.name}"
            dest_path = dest_dir / dest_name

            shutil.move(str(source_path), str(dest_path))
            logger.debug(f"Moved {source_path.name} to {dest_path}")

        except Exception as e:
            logger.warning(f"Failed to move processed file: {e}")

    async def watch_directory(
        self,
        directory: Union[str, Path],
        patterns: Optional[List[str]] = None,
        interval_seconds: int = 30,
        source: SourceType = SourceType.WATCH_FOLDER,
        custom_tags: Optional[List[str]] = None,
        move_processed: bool = True,
        processed_dir: Optional[Union[str, Path]] = None,
        callback: Optional[Callable[[IngestionResult], None]] = None,
    ) -> None:
        """
        Watch a directory for new files and import them automatically.

        Args:
            directory: Directory to watch
            patterns: File patterns to match
            interval_seconds: Polling interval
            source: Source type for metadata
            custom_tags: Custom tags to apply
            move_processed: Whether to move processed files
            processed_dir: Directory for processed files
            callback: Callback for each processed file
        """
        directory = Path(directory)
        patterns = patterns or ["*.txt", "*.md", "*.json"]
        processed_dir = Path(processed_dir) if processed_dir else directory / "processed"

        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)

        logger.info(f"Starting watch on directory: {directory}")
        self._watching = True

        while self._watching:
            try:
                # Find new files
                files = []
                for pattern in patterns:
                    files.extend(directory.glob(pattern))

                # Filter to unprocessed files
                new_files = [
                    f for f in files
                    if str(f) not in self._processed_files
                ]

                for file_path in new_files:
                    logger.info(f"Processing new file: {file_path.name}")

                    result = self.import_file(
                        file_path,
                        source=source,
                        custom_tags=custom_tags,
                    )

                    self._processed_files.add(str(file_path))

                    if callback:
                        callback(result)

                    if move_processed and result.success:
                        self._move_processed_file(file_path, processed_dir)

                await asyncio.sleep(interval_seconds)

            except asyncio.CancelledError:
                logger.info("Watch cancelled")
                break
            except Exception as e:
                logger.error(f"Error in watch loop: {e}")
                await asyncio.sleep(interval_seconds)

        logger.info("Watch stopped")

    def stop_watching(self) -> None:
        """Stop the directory watch."""
        self._watching = False
        logger.info("Stopping directory watch...")

    def import_text(
        self,
        text: str,
        timestamp: Optional[datetime] = None,
        source: SourceType = SourceType.API,
        participants: Optional[List[str]] = None,
        custom_tags: Optional[List[str]] = None,
        extract_metadata: bool = True,
    ) -> IngestionResult:
        """
        Import raw text directly.

        Args:
            text: Text content to import
            timestamp: Optional timestamp
            source: Source type
            participants: Optional participant list
            custom_tags: Optional custom tags
            extract_metadata: Whether to extract metadata

        Returns:
            IngestionResult
        """
        from config.schema import Document, DocumentFormat

        metadata = MemoryMetadata(
            doc_id="",
            timestamp=timestamp or datetime.now(),
            source=source,
            participants=participants or [],
            custom_tags=custom_tags or [],
        )

        document = Document(
            content=text,
            format=DocumentFormat.PLAIN_TEXT,
            metadata=metadata,
        )
        document.metadata.doc_id = document.id

        return self.import_document(
            document,
            extract_metadata=extract_metadata,
        )

    def get_import_stats(self) -> Dict[str, int]:
        """
        Get import statistics.

        Returns:
            Dictionary with import statistics
        """
        db_stats = self.vector_db.get_stats()
        dedup_stats = self.dedup_service.get_stats()

        return {
            "total_chunks": db_stats.get("total_chunks", 0),
            "total_documents": db_stats.get("total_documents", 0),
            "dedup_hash_entries": dedup_stats.get("hash_entries", 0),
            "dedup_embedding_entries": dedup_stats.get("embedding_entries", 0),
            "processed_watch_files": len(self._processed_files),
        }


# Global batch importer instance
_importer: Optional[BatchImporter] = None


def get_batch_importer() -> BatchImporter:
    """Get the global batch importer instance."""
    global _importer
    if _importer is None:
        _importer = BatchImporter()
    return _importer
