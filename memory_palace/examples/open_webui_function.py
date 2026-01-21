"""
Memory Palace Function for Open WebUI

This file defines a function that can be installed in Open WebUI
to provide Memory Palace functionality.

Installation:
1. Start the Memory Palace HTTP server:
   python -m memory_palace.scripts.run_http

2. In Open WebUI:
   - Go to Workspace > Functions
   - Click "+" to add a new function
   - Copy and paste this entire file
   - Save and enable the function

3. The Memory Palace tools will now be available to all models

Configuration:
- Update MEMORY_PALACE_URL below to match your server address
- If running on a different machine, use the appropriate IP/hostname

title: Memory Palace
description: Search and save memories via Memory Palace MCP server
author: Memory Palace Contributors
version: 1.0.0
"""

import httpx
from pydantic import BaseModel, Field
from typing import Optional, List, Any


# Configuration - update this to match your server
MEMORY_PALACE_URL = "http://localhost:8765/api"


class Tools:
    """Memory Palace tools for Open WebUI."""

    def __init__(self):
        self.base_url = MEMORY_PALACE_URL

    async def search_memories(
        self,
        query: str,
        limit: int = 10,
        memory_types: Optional[List[str]] = None,
        __user__: dict = {}
    ) -> str:
        """
        Search the memory palace for relevant information.

        Use this to find past conversations, decisions, preferences, and facts.
        The search uses AI to understand meaning, not just keywords.

        :param query: Natural language search query (e.g., "What did we discuss about Python?")
        :param limit: Maximum number of results to return (default 10)
        :param memory_types: Optional filter by type: fact, preference, decision, event, insight
        :return: Matching memories with relevance scores
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            payload = {"query": query, "limit": limit}
            if memory_types:
                payload["memory_types"] = memory_types

            response = await client.post(
                f"{self.base_url}/tools/search_memories",
                json={"arguments": payload}
            )
            result = response.json()

            if not result.get("memories"):
                return "No relevant memories found."

            formatted = []
            for item in result["memories"]:
                m = item["memory"]
                score = item["relevance_score"]
                date = m["created_at"][:10]
                content = m["content"]
                topics = ", ".join(m.get("topics", []))

                entry = f"[{date}] ({score:.0%} relevant)\n{content}"
                if topics:
                    entry += f"\nTopics: {topics}"
                formatted.append(entry)

            return "\n\n---\n\n".join(formatted)

    async def save_memory(
        self,
        content: str,
        memory_type: str = "fact",
        importance: str = "medium",
        topics: Optional[List[str]] = None,
        __user__: dict = {}
    ) -> str:
        """
        Save new information to the memory palace.

        Use this to remember important facts, preferences, decisions, or insights.

        :param content: The information to remember
        :param memory_type: Type: fact, preference, decision, event, insight (default: fact)
        :param importance: Level: low, medium, high, critical (default: medium)
        :param topics: Optional list of topics/tags for categorization
        :return: Confirmation message with extracted metadata
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            payload = {
                "content": content,
                "memory_type": memory_type,
                "importance": importance,
            }
            if topics:
                payload["topics"] = topics

            response = await client.post(
                f"{self.base_url}/tools/save_memory",
                json={"arguments": payload}
            )
            result = response.json()

            if "error" in result:
                return f"Error saving memory: {result['error']}"

            output = f"Memory saved: {result.get('memory_id', 'unknown')}"
            if result.get("extracted_entities"):
                output += f"\nEntities detected: {', '.join(result['extracted_entities'])}"
            if result.get("extracted_topics"):
                output += f"\nTopics: {', '.join(result['extracted_topics'])}"

            return output

    async def timeline_query(
        self,
        topic: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        __user__: dict = {}
    ) -> str:
        """
        Get chronological timeline of memories on a topic.

        Use this to understand how a topic evolved over time, trace the history
        of decisions, or review past discussions chronologically.

        :param topic: Topic to trace through time (e.g., "database migration")
        :param date_from: Optional start date (YYYY-MM-DD format)
        :param date_to: Optional end date (YYYY-MM-DD format)
        :return: Timeline with grouped entries and summaries
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            payload = {"topic": topic}
            if date_from:
                payload["date_from"] = date_from
            if date_to:
                payload["date_to"] = date_to

            response = await client.post(
                f"{self.base_url}/tools/timeline_query",
                json={"arguments": payload}
            )
            result = response.json()

            if not result.get("entries"):
                return f"No timeline entries found for '{topic}'."

            formatted = [f"# Timeline: {topic}"]
            formatted.append(f"Date range: {result['date_range'][0]} to {result['date_range'][1]}")
            formatted.append(f"Total memories: {result['total_memories']}\n")

            for entry in result["entries"]:
                formatted.append(f"## {entry['period_label']} ({entry['memory_count']} memories)")

                if entry.get("summary"):
                    formatted.append(entry["summary"])

                if entry.get("key_events"):
                    formatted.append("\nKey events:")
                    for event in entry["key_events"]:
                        formatted.append(f"- {event}")

                formatted.append("")  # Empty line between periods

            return "\n".join(formatted)

    async def list_entities(
        self,
        entity_type: Optional[str] = None,
        limit: int = 20,
        __user__: dict = {}
    ) -> str:
        """
        List all known entities in the memory palace.

        Shows people, organizations, projects, and other named things
        that have been mentioned in memories.

        :param entity_type: Optional filter: PERSON, ORG, PROJECT, LOCATION, etc.
        :param limit: Maximum entities to return (default 20)
        :return: List of entities with memory counts
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            payload = {"limit": limit}
            if entity_type:
                payload["entity_type"] = entity_type

            response = await client.post(
                f"{self.base_url}/tools/list_entities",
                json={"arguments": payload}
            )
            result = response.json()

            if not result.get("entities"):
                return "No entities found."

            formatted = [f"Found {result['total_count']} entities:\n"]
            for entity in result["entities"]:
                entry = f"- {entity['name']} ({entity['entity_type']})"
                if entity.get("memory_count"):
                    entry += f" - {entity['memory_count']} memories"
                formatted.append(entry)

            return "\n".join(formatted)

    async def get_entity_profile(
        self,
        entity_name: str,
        __user__: dict = {}
    ) -> str:
        """
        Get comprehensive information about a specific entity.

        Returns everything known about a person, organization, project, etc.
        including recent memories, related entities, and associated topics.

        :param entity_name: Name of the entity to look up
        :return: Complete entity profile
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/tools/get_entity_profile",
                json={"arguments": {"entity_name": entity_name}}
            )
            result = response.json()

            if "error" in result:
                return f"Entity '{entity_name}' not found."

            entity = result["entity"]
            formatted = [f"# {entity['name']} ({entity['entity_type']})"]

            if entity.get("description"):
                formatted.append(entity["description"])

            formatted.append(f"\nMemory count: {entity.get('memory_count', 0)}")

            if entity.get("first_seen"):
                formatted.append(f"First seen: {entity['first_seen'][:10]}")
            if entity.get("last_seen"):
                formatted.append(f"Last seen: {entity['last_seen'][:10]}")

            if result.get("associated_topics"):
                formatted.append(f"\nAssociated topics: {', '.join(result['associated_topics'])}")

            if result.get("related_entities"):
                formatted.append("\nRelated entities:")
                for rel in result["related_entities"][:5]:
                    formatted.append(f"  - {rel['name']} ({rel['entity_type']})")

            if result.get("recent_memories"):
                formatted.append("\nRecent memories:")
                for m in result["recent_memories"][:5]:
                    date = m["created_at"][:10]
                    content = m["content"][:100] + "..." if len(m["content"]) > 100 else m["content"]
                    formatted.append(f"  [{date}] {content}")

            return "\n".join(formatted)

    async def get_memory_stats(
        self,
        __user__: dict = {}
    ) -> str:
        """
        Get statistics about the memory palace.

        Returns overview of stored memories, entities, topics, and trends.

        :return: Memory palace statistics
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/tools/get_memory_stats",
                json={"arguments": {}}
            )
            result = response.json()

            formatted = ["# Memory Palace Statistics\n"]
            formatted.append(f"Total memories: {result.get('total_memories', 0)}")
            formatted.append(f"Total entities: {result.get('total_entities', 0)}")
            formatted.append(f"Total topics: {result.get('total_topics', 0)}")

            if result.get("date_range"):
                formatted.append(f"\nDate range: {result['date_range'][0]} to {result['date_range'][1]}")

            if result.get("memories_by_type"):
                formatted.append("\nMemories by type:")
                for mem_type, count in result["memories_by_type"].items():
                    formatted.append(f"  - {mem_type}: {count}")

            if result.get("top_topics"):
                formatted.append("\nTop topics:")
                for topic in result["top_topics"][:10]:
                    formatted.append(f"  - {topic['name']}: {topic['count']} memories")

            if result.get("top_entities"):
                formatted.append("\nTop entities:")
                for entity in result["top_entities"][:10]:
                    formatted.append(f"  - {entity['name']} ({entity['type']}): {entity['count']} memories")

            return "\n".join(formatted)

    async def list_recent(
        self,
        limit: int = 10,
        days: Optional[int] = None,
        __user__: dict = {}
    ) -> str:
        """
        Get the most recent memories.

        Use this to see what was recently added or discussed.

        :param limit: Number of memories to return (default 10)
        :param days: Optional: only include memories from last N days
        :return: Recent memories in chronological order
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            payload = {"limit": limit}
            if days:
                payload["days"] = days

            response = await client.post(
                f"{self.base_url}/tools/list_recent",
                json={"arguments": payload}
            )
            result = response.json()

            if not result.get("memories"):
                return "No recent memories found."

            formatted = ["# Recent Memories\n"]
            for item in result["memories"]:
                m = item["memory"]
                date = m["created_at"][:16].replace("T", " ")
                mem_type = m["memory_type"]
                content = m["content"]

                formatted.append(f"[{date}] ({mem_type})")
                formatted.append(content)
                if m.get("topics"):
                    formatted.append(f"Topics: {', '.join(m['topics'])}")
                formatted.append("")  # Empty line between memories

            return "\n".join(formatted)
