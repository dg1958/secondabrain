"""
Fireflies.ai integration for Memory Palace.

This module provides:
- Fireflies API client
- Transcript fetching and syncing
- Periodic sync scheduling
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

import httpx
from loguru import logger

from config.schema import (
    Document,
    DocumentFormat,
    FirefliesTranscript,
    MemoryMetadata,
    SourceType,
)
from ingestion.batch_importer import BatchImporter, get_batch_importer


class FirefliesSync:
    """
    Fireflies.ai transcript synchronization service.

    Capabilities:
    - Fetch transcripts via Fireflies API
    - Incremental sync (only new transcripts)
    - Store transcript IDs to avoid reprocessing
    - Periodic automatic sync
    """

    # Fireflies GraphQL API endpoint
    API_URL = "https://api.fireflies.ai/graphql"

    def __init__(
        self,
        api_key: Optional[str] = None,
        importer: Optional[BatchImporter] = None,
    ):
        """
        Initialize the Fireflies sync service.

        Args:
            api_key: Fireflies API key
            importer: BatchImporter for ingesting transcripts
        """
        # TODO: ADD YOUR API KEY HERE
        self.api_key = api_key or ""
        self._importer = importer
        self._synced_ids: Set[str] = set()
        self._sync_running = False

        if not self.api_key:
            logger.warning(
                "Fireflies API key not configured. "
                "Set FIREFLIES_API_KEY or configure in settings.yaml"
            )

    @property
    def importer(self) -> BatchImporter:
        """Get the batch importer."""
        if self._importer is None:
            self._importer = get_batch_importer()
        return self._importer

    @property
    def is_configured(self) -> bool:
        """Check if the service is properly configured."""
        return bool(self.api_key)

    async def _make_request(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make a GraphQL request to Fireflies API.

        Args:
            query: GraphQL query string
            variables: Query variables

        Returns:
            Response data dictionary
        """
        if not self.is_configured:
            raise RuntimeError("Fireflies API key not configured")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.API_URL,
                json=payload,
                headers=headers,
                timeout=30.0,
            )

            response.raise_for_status()
            data = response.json()

            if "errors" in data:
                error_msg = data["errors"][0].get("message", "Unknown error")
                raise RuntimeError(f"Fireflies API error: {error_msg}")

            return data.get("data", {})

    async def fetch_transcripts(
        self,
        limit: int = 50,
        since_date: Optional[datetime] = None,
    ) -> List[FirefliesTranscript]:
        """
        Fetch transcripts from Fireflies.

        Args:
            limit: Maximum transcripts to fetch
            since_date: Only fetch transcripts after this date

        Returns:
            List of FirefliesTranscript objects
        """
        # TODO: COMPLETE OAUTH SETUP
        # For full OAuth flow, implement the authorization code flow:
        # 1. Redirect user to Fireflies authorization URL
        # 2. Handle callback with authorization code
        # 3. Exchange code for access token
        # See: https://docs.fireflies.ai/api-reference/authentication

        query = """
        query GetTranscripts($limit: Int) {
            transcripts(limit: $limit) {
                id
                title
                date
                duration
                participants
                transcript_url
                sentences {
                    speaker_name
                    text
                    start_time
                    end_time
                }
                summary {
                    overview
                    action_items
                    keywords
                }
            }
        }
        """

        variables = {"limit": limit}

        try:
            data = await self._make_request(query, variables)
            transcripts_data = data.get("transcripts", [])

            transcripts = []
            for t_data in transcripts_data:
                transcript = self._parse_transcript(t_data)

                # Filter by date if specified
                if since_date and transcript.date < since_date:
                    continue

                transcripts.append(transcript)

            logger.info(f"Fetched {len(transcripts)} transcripts from Fireflies")
            return transcripts

        except Exception as e:
            logger.error(f"Failed to fetch Fireflies transcripts: {e}")
            raise

    def _parse_transcript(self, data: Dict[str, Any]) -> FirefliesTranscript:
        """
        Parse Fireflies API response into FirefliesTranscript.

        Args:
            data: Raw transcript data from API

        Returns:
            FirefliesTranscript object
        """
        # Parse timestamp
        date_str = data.get("date")
        if date_str:
            try:
                date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                date = datetime.now()
        else:
            date = datetime.now()

        # Build transcript text from sentences
        sentences = data.get("sentences", [])
        transcript_text = self._format_sentences(sentences)

        # Extract summary data
        summary_data = data.get("summary", {}) or {}

        # Extract participants
        participants = data.get("participants", [])
        if isinstance(participants, list) and participants:
            if isinstance(participants[0], dict):
                participants = [p.get("name", str(p)) for p in participants]

        return FirefliesTranscript(
            id=data.get("id", ""),
            title=data.get("title", "Untitled Meeting"),
            date=date,
            duration_minutes=data.get("duration", 0),
            participants=participants,
            transcript_text=transcript_text,
            summary=summary_data.get("overview"),
            action_items=summary_data.get("action_items"),
            keywords=summary_data.get("keywords"),
            meeting_url=data.get("transcript_url"),
        )

    def _format_sentences(self, sentences: List[Dict]) -> str:
        """
        Format Fireflies sentences into transcript text.

        Args:
            sentences: List of sentence objects

        Returns:
            Formatted transcript text
        """
        lines = []
        current_speaker = None

        for sentence in sentences:
            speaker = sentence.get("speaker_name")
            text = sentence.get("text", "")

            if not text:
                continue

            if speaker and speaker != current_speaker:
                if lines:
                    lines.append("")  # Blank line for speaker change
                current_speaker = speaker

            if speaker:
                lines.append(f"{speaker}: {text}")
            else:
                lines.append(text)

        return "\n".join(lines)

    async def sync_transcripts(
        self,
        limit: int = 50,
        since_date: Optional[datetime] = None,
        sync_all: bool = False,
    ) -> Dict[str, Any]:
        """
        Sync transcripts from Fireflies to Memory Palace.

        Args:
            limit: Maximum transcripts to sync
            since_date: Only sync transcripts after this date
            sync_all: Ignore synced IDs and resync all

        Returns:
            Sync result summary
        """
        if not self.is_configured:
            return {
                "success": False,
                "message": "Fireflies API key not configured",
                "transcripts_synced": 0,
            }

        try:
            # Fetch transcripts
            transcripts = await self.fetch_transcripts(limit, since_date)

            synced_count = 0
            skipped_count = 0
            errors = []

            for transcript in transcripts:
                # Skip if already synced (unless sync_all)
                if not sync_all and transcript.id in self._synced_ids:
                    skipped_count += 1
                    continue

                # Convert to Document
                document = self._transcript_to_document(transcript)

                # Import
                try:
                    result = self.importer.import_document(
                        document,
                        extract_metadata=True,
                    )

                    if result.success:
                        synced_count += 1
                        self._synced_ids.add(transcript.id)
                    else:
                        errors.append(f"{transcript.title}: {result.error_message}")

                except Exception as e:
                    errors.append(f"{transcript.title}: {str(e)}")

            logger.info(
                f"Fireflies sync complete: {synced_count} synced, "
                f"{skipped_count} skipped, {len(errors)} errors"
            )

            return {
                "success": True,
                "message": f"Synced {synced_count} transcripts",
                "transcripts_synced": synced_count,
                "skipped": skipped_count,
                "errors": errors,
            }

        except Exception as e:
            logger.error(f"Fireflies sync failed: {e}")
            return {
                "success": False,
                "message": str(e),
                "transcripts_synced": 0,
            }

    def _transcript_to_document(
        self,
        transcript: FirefliesTranscript,
    ) -> Document:
        """
        Convert a FirefliesTranscript to a Document.

        Args:
            transcript: Fireflies transcript

        Returns:
            Document object
        """
        # Build full content
        content_parts = []

        if transcript.title:
            content_parts.append(f"# {transcript.title}")
            content_parts.append("")

        if transcript.summary:
            content_parts.append("## Summary")
            content_parts.append(transcript.summary)
            content_parts.append("")

        if transcript.action_items:
            content_parts.append("## Action Items")
            for item in transcript.action_items:
                content_parts.append(f"- {item}")
            content_parts.append("")

        content_parts.append("## Transcript")
        content_parts.append(transcript.transcript_text)

        content = "\n".join(content_parts)

        # Create metadata
        metadata = MemoryMetadata(
            doc_id=transcript.id,
            timestamp=transcript.date,
            source=SourceType.FIREFLIES,
            participants=transcript.participants,
            topics=transcript.keywords or [],
            conversation_id=transcript.id,
            platform="fireflies",
        )

        return Document(
            id=transcript.id,
            content=content,
            format=DocumentFormat.FIREFLIES_JSON,
            metadata=metadata,
        )

    async def start_periodic_sync(
        self,
        interval_minutes: int = 60,
        since_days: int = 7,
    ) -> None:
        """
        Start periodic sync in the background.

        Args:
            interval_minutes: Sync interval in minutes
            since_days: Only sync transcripts from last N days
        """
        if self._sync_running:
            logger.warning("Periodic sync already running")
            return

        self._sync_running = True
        logger.info(f"Starting periodic Fireflies sync every {interval_minutes} minutes")

        while self._sync_running:
            try:
                since_date = datetime.now() - timedelta(days=since_days)
                await self.sync_transcripts(since_date=since_date)
            except Exception as e:
                logger.error(f"Periodic sync error: {e}")

            await asyncio.sleep(interval_minutes * 60)

    def stop_periodic_sync(self) -> None:
        """Stop the periodic sync."""
        self._sync_running = False
        logger.info("Stopping periodic Fireflies sync")

    def get_synced_ids(self) -> Set[str]:
        """Get the set of synced transcript IDs."""
        return self._synced_ids.copy()

    def mark_as_synced(self, transcript_id: str) -> None:
        """Mark a transcript as synced."""
        self._synced_ids.add(transcript_id)

    def clear_sync_history(self) -> None:
        """Clear the sync history (will re-sync all on next run)."""
        self._synced_ids.clear()
        logger.info("Cleared Fireflies sync history")


# Global instance
_fireflies_sync: Optional[FirefliesSync] = None


def get_fireflies_sync(
    api_key: Optional[str] = None,
) -> FirefliesSync:
    """
    Get the global Fireflies sync instance.

    Args:
        api_key: Fireflies API key

    Returns:
        FirefliesSync instance
    """
    global _fireflies_sync
    if _fireflies_sync is None:
        _fireflies_sync = FirefliesSync(api_key)
    return _fireflies_sync
