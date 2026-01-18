"""
Result synthesis for Memory Palace queries.

This module provides:
- LLM-powered result summarization
- Timeline reconstruction
- Cross-reference analysis
- Export formatting
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

from config.schema import QueryResult


class ResultSynthesizer:
    """
    Service for synthesizing and summarizing query results.

    Capabilities:
    - Generate natural language summaries of results
    - Create chronological timelines
    - Identify patterns and themes
    - Format for export (Markdown, JSON)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
    ):
        """
        Initialize the synthesizer.

        Args:
            api_key: Anthropic API key
            model: Model to use for synthesis
        """
        self.model = model
        self._client = None

        if api_key and Anthropic is not None:
            self._client = Anthropic(api_key=api_key)

    @property
    def is_available(self) -> bool:
        """Check if LLM synthesis is available."""
        return self._client is not None

    def synthesize(
        self,
        query: str,
        results: List[QueryResult],
        max_chunks: int = 20,
    ) -> str:
        """
        Generate a synthesis of query results.

        Args:
            query: Original query
            results: List of query results
            max_chunks: Maximum chunks to include in synthesis

        Returns:
            Synthesized summary text
        """
        if not results:
            return "No relevant memories found for this query."

        if not self.is_available:
            return self._basic_synthesis(query, results[:max_chunks])

        try:
            return self._llm_synthesis(query, results[:max_chunks])
        except Exception as e:
            logger.error(f"LLM synthesis failed: {e}")
            return self._basic_synthesis(query, results[:max_chunks])

    def _basic_synthesis(
        self,
        query: str,
        results: List[QueryResult],
    ) -> str:
        """Create a basic synthesis without LLM."""
        lines = [
            f"Found {len(results)} relevant memories for: \"{query}\"",
            "",
        ]

        # Group by date
        by_date: Dict[str, List[QueryResult]] = {}
        for result in results:
            date_str = result.metadata.timestamp.strftime("%Y-%m-%d")
            if date_str not in by_date:
                by_date[date_str] = []
            by_date[date_str].append(result)

        for date_str in sorted(by_date.keys(), reverse=True):
            lines.append(f"### {date_str}")
            for result in by_date[date_str]:
                preview = result.text[:200] + "..." if len(result.text) > 200 else result.text
                lines.append(f"- {preview}")
            lines.append("")

        return "\n".join(lines)

    def _llm_synthesis(
        self,
        query: str,
        results: List[QueryResult],
    ) -> str:
        """Generate synthesis using LLM."""
        # Prepare context from results
        context_parts = []
        for i, result in enumerate(results):
            timestamp = result.metadata.timestamp.strftime("%Y-%m-%d %H:%M")
            participants = ", ".join(result.metadata.participants) if result.metadata.participants else "Unknown"
            topics = ", ".join(result.metadata.topics) if result.metadata.topics else "N/A"

            context_parts.append(f"""
[Memory {i+1}]
Date: {timestamp}
Participants: {participants}
Topics: {topics}
Content: {result.text[:1000]}
---""")

        context = "\n".join(context_parts)

        system_prompt = """You are a personal memory assistant helping the user recall and understand their past conversations and notes.

Given a query and relevant memory fragments, synthesize a helpful response that:
1. Directly answers the query
2. Summarizes key points from the memories
3. Notes any patterns or changes over time
4. Mentions relevant participants and dates
5. Highlights important insights

Be concise but comprehensive. Use natural language, not bullet points unless appropriate.
If the memories don't fully answer the query, say so."""

        user_prompt = f"""Query: {query}

Relevant memories:
{context}

Synthesize a response:"""

        response = self._client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        return response.content[0].text.strip()

    def create_timeline(
        self,
        results: List[QueryResult],
        include_content: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Create a chronological timeline from results.

        Args:
            results: Query results to arrange
            include_content: Whether to include full content

        Returns:
            List of timeline entries sorted chronologically
        """
        timeline = []

        for result in results:
            entry = {
                "timestamp": result.metadata.timestamp.isoformat(),
                "date": result.metadata.timestamp.strftime("%Y-%m-%d"),
                "time": result.metadata.timestamp.strftime("%H:%M"),
                "participants": result.metadata.participants,
                "topics": result.metadata.topics,
                "sentiment": result.metadata.sentiment,
                "source": result.metadata.source.value,
            }

            if include_content:
                entry["content"] = result.text
                entry["preview"] = result.text[:200] + "..." if len(result.text) > 200 else result.text
            else:
                entry["preview"] = result.text[:200] + "..." if len(result.text) > 200 else result.text

            timeline.append(entry)

        # Sort by timestamp
        timeline.sort(key=lambda x: x["timestamp"])

        return timeline

    def identify_themes(
        self,
        results: List[QueryResult],
        max_themes: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Identify common themes across results.

        Args:
            results: Query results to analyze
            max_themes: Maximum themes to identify

        Returns:
            List of theme objects with frequency and examples
        """
        if not results:
            return []

        # Count topic frequencies
        topic_counts: Dict[str, int] = {}
        topic_examples: Dict[str, List[str]] = {}

        for result in results:
            for topic in result.metadata.topics:
                topic_lower = topic.lower()
                topic_counts[topic_lower] = topic_counts.get(topic_lower, 0) + 1

                if topic_lower not in topic_examples:
                    topic_examples[topic_lower] = []
                if len(topic_examples[topic_lower]) < 3:
                    preview = result.text[:100] + "..."
                    topic_examples[topic_lower].append(preview)

        # Sort by frequency
        sorted_topics = sorted(
            topic_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:max_themes]

        themes = []
        for topic, count in sorted_topics:
            themes.append({
                "theme": topic,
                "frequency": count,
                "percentage": round(count / len(results) * 100, 1),
                "examples": topic_examples.get(topic, []),
            })

        return themes

    def analyze_participants(
        self,
        results: List[QueryResult],
    ) -> Dict[str, Any]:
        """
        Analyze participant patterns in results.

        Args:
            results: Query results to analyze

        Returns:
            Analysis of participant patterns
        """
        participant_stats: Dict[str, Dict[str, Any]] = {}

        for result in results:
            for participant in result.metadata.participants:
                if participant not in participant_stats:
                    participant_stats[participant] = {
                        "mention_count": 0,
                        "first_seen": result.metadata.timestamp,
                        "last_seen": result.metadata.timestamp,
                        "topics": set(),
                    }

                stats = participant_stats[participant]
                stats["mention_count"] += 1

                if result.metadata.timestamp < stats["first_seen"]:
                    stats["first_seen"] = result.metadata.timestamp
                if result.metadata.timestamp > stats["last_seen"]:
                    stats["last_seen"] = result.metadata.timestamp

                stats["topics"].update(result.metadata.topics)

        # Convert to serializable format
        analysis = {}
        for participant, stats in participant_stats.items():
            analysis[participant] = {
                "mention_count": stats["mention_count"],
                "first_seen": stats["first_seen"].isoformat(),
                "last_seen": stats["last_seen"].isoformat(),
                "common_topics": list(stats["topics"])[:10],
            }

        return analysis

    def export_markdown(
        self,
        query: str,
        results: List[QueryResult],
        include_synthesis: bool = True,
    ) -> str:
        """
        Export results as formatted Markdown.

        Args:
            query: Original query
            results: Query results
            include_synthesis: Whether to include LLM synthesis

        Returns:
            Markdown-formatted string
        """
        lines = [
            f"# Memory Query Results",
            f"",
            f"**Query:** {query}",
            f"**Results:** {len(results)} memories found",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"",
        ]

        # Add synthesis
        if include_synthesis and results:
            lines.append("## Summary")
            lines.append("")
            synthesis = self.synthesize(query, results)
            lines.append(synthesis)
            lines.append("")

        # Add timeline
        lines.append("## Timeline")
        lines.append("")

        timeline = self.create_timeline(results)
        current_date = None

        for entry in timeline:
            if entry["date"] != current_date:
                current_date = entry["date"]
                lines.append(f"### {current_date}")
                lines.append("")

            participants_str = ", ".join(entry["participants"]) if entry["participants"] else "Unknown"
            lines.append(f"**{entry['time']}** ({participants_str})")
            lines.append("")
            lines.append(f"> {entry['preview']}")
            lines.append("")

        # Add themes
        themes = self.identify_themes(results)
        if themes:
            lines.append("## Common Themes")
            lines.append("")
            for theme in themes:
                lines.append(f"- **{theme['theme']}** ({theme['frequency']} occurrences, {theme['percentage']}%)")
            lines.append("")

        return "\n".join(lines)

    def export_json(
        self,
        query: str,
        results: List[QueryResult],
        include_synthesis: bool = True,
    ) -> str:
        """
        Export results as JSON.

        Args:
            query: Original query
            results: Query results
            include_synthesis: Whether to include synthesis

        Returns:
            JSON-formatted string
        """
        export_data = {
            "query": query,
            "generated_at": datetime.now().isoformat(),
            "total_results": len(results),
            "results": [],
        }

        if include_synthesis and results:
            export_data["synthesis"] = self.synthesize(query, results)

        for result in results:
            export_data["results"].append({
                "chunk_id": result.chunk_id,
                "score": result.score,
                "text": result.text,
                "metadata": {
                    "timestamp": result.metadata.timestamp.isoformat(),
                    "source": result.metadata.source.value,
                    "participants": result.metadata.participants,
                    "topics": result.metadata.topics,
                    "sentiment": result.metadata.sentiment,
                    "custom_tags": result.metadata.custom_tags,
                },
            })

        export_data["themes"] = self.identify_themes(results)
        export_data["timeline"] = self.create_timeline(results, include_content=False)

        return json.dumps(export_data, indent=2)


# Global synthesizer instance
_synthesizer: Optional[ResultSynthesizer] = None


def get_result_synthesizer(
    api_key: Optional[str] = None,
    model: str = "claude-sonnet-4-20250514",
) -> ResultSynthesizer:
    """
    Get the global result synthesizer instance.

    Args:
        api_key: Anthropic API key
        model: Model to use

    Returns:
        ResultSynthesizer instance
    """
    global _synthesizer
    if _synthesizer is None:
        _synthesizer = ResultSynthesizer(api_key, model)
    return _synthesizer


def synthesize_results(
    query: str,
    results: List[QueryResult],
    api_key: Optional[str] = None,
) -> str:
    """
    Convenience function to synthesize results.

    Args:
        query: Original query
        results: Query results
        api_key: Optional API key

    Returns:
        Synthesis text
    """
    synthesizer = get_result_synthesizer(api_key)
    return synthesizer.synthesize(query, results)
