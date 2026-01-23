"""
LLM-powered query planning for Memory Palace.

This module provides:
- Query decomposition for complex queries
- Multi-step query planning
- Automatic query refinement
- Context-aware search strategies
"""

import json
from typing import Any, Dict, List, Optional

from loguru import logger

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None
    logger.warning("anthropic not installed. LLM features disabled.")



class QueryPlan:
    """
    Represents a multi-step query plan.

    Each step contains:
    - search_query: The actual search text
    - filters: Metadata filters to apply
    - purpose: What this step is trying to find
    - depends_on: List of step indices this depends on
    """

    def __init__(self, steps: List[Dict[str, Any]]):
        """
        Initialize the query plan.

        Args:
            steps: List of query steps
        """
        self.steps = steps
        self.results: Dict[int, Any] = {}

    def __len__(self) -> int:
        return len(self.steps)

    def __iter__(self):
        return iter(self.steps)

    def get_step(self, index: int) -> Optional[Dict[str, Any]]:
        """Get a step by index."""
        if 0 <= index < len(self.steps):
            return self.steps[index]
        return None

    def set_result(self, index: int, result: Any) -> None:
        """Store the result of a step."""
        self.results[index] = result

    def get_result(self, index: int) -> Any:
        """Get the result of a step."""
        return self.results.get(index)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "steps": self.steps,
            "total_steps": len(self.steps),
        }


class AgenticPlanner:
    """
    LLM-powered query planner for complex information needs.

    Uses Claude to:
    - Understand complex natural language queries
    - Break them into searchable sub-queries
    - Determine optimal search strategies
    - Refine queries based on initial results
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
    ):
        """
        Initialize the agentic planner.

        Args:
            api_key: Anthropic API key
            model: Model to use for planning
        """
        self.model = model
        self._client = None

        if api_key and Anthropic is not None:
            self._client = Anthropic(api_key=api_key)

    @property
    def is_available(self) -> bool:
        """Check if LLM planning is available."""
        return self._client is not None

    def plan_query(
        self,
        query: str,
        context: Optional[str] = None,
        available_topics: Optional[List[str]] = None,
        available_participants: Optional[List[str]] = None,
    ) -> QueryPlan:
        """
        Create a query plan for a complex information need.

        Args:
            query: Natural language query
            context: Optional context about the knowledge base
            available_topics: List of known topics in the database
            available_participants: List of known participants

        Returns:
            QueryPlan with steps to execute
        """
        if not self.is_available:
            # Fall back to simple single-step plan
            return self._create_simple_plan(query)

        try:
            plan = self._generate_plan_with_llm(
                query,
                context,
                available_topics,
                available_participants,
            )
            return plan

        except Exception as e:
            logger.error(f"LLM planning failed: {e}")
            return self._create_simple_plan(query)

    def _create_simple_plan(self, query: str) -> QueryPlan:
        """Create a simple single-step plan."""
        return QueryPlan([{
            "search_query": query,
            "filters": {},
            "purpose": "Direct search for query",
            "depends_on": [],
        }])

    def _generate_plan_with_llm(
        self,
        query: str,
        context: Optional[str],
        available_topics: Optional[List[str]],
        available_participants: Optional[List[str]],
    ) -> QueryPlan:
        """Generate a query plan using the LLM."""
        system_prompt = """You are a query planning assistant for a personal memory/knowledge management system.
Your job is to break down complex queries into searchable steps.

The system stores conversation transcripts with metadata including:
- Timestamps (for temporal filtering)
- Participants (people in conversations)
- Topics (automatically extracted keywords)
- Custom tags
- Sentiment scores

For each query, create a plan with 1-5 steps. Each step should have:
- search_query: Text to search for (should be embedding-friendly - descriptive phrases)
- filters: Any metadata filters (topics, participants, date_range)
- purpose: What this step is trying to find
- depends_on: List of step indices (0-indexed) whose results this needs

Output ONLY valid JSON in this format:
{
  "steps": [
    {
      "search_query": "discussion about machine learning applications",
      "filters": {"topics": ["AI", "machine learning"]},
      "purpose": "Find conversations about ML",
      "depends_on": []
    }
  ]
}

Important:
- Keep search queries concise but descriptive
- Use filters to narrow results when the query mentions specific people, topics, or times
- For temporal queries, include date_range in filters with "start" and "end" ISO dates
- Most queries need only 1-2 steps
- Only use multiple steps for truly complex queries that need sequential refinement"""

        user_prompt = f"Query: {query}\n"

        if context:
            user_prompt += f"\nContext: {context}\n"

        if available_topics:
            user_prompt += f"\nKnown topics in database: {', '.join(available_topics[:20])}\n"

        if available_participants:
            user_prompt += f"\nKnown participants: {', '.join(available_participants[:20])}\n"

        user_prompt += "\nCreate a query plan:"

        response = self._client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        # Parse the response
        response_text = response.content[0].text.strip()

        # Extract JSON from response
        try:
            # Try to find JSON in the response
            json_match = response_text
            if "```json" in response_text:
                json_match = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                json_match = response_text.split("```")[1].split("```")[0]

            plan_data = json.loads(json_match)
            steps = plan_data.get("steps", [])

            if not steps:
                return self._create_simple_plan(query)

            return QueryPlan(steps)

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM plan response: {e}")
            return self._create_simple_plan(query)

    def interpret_query(
        self,
        query: str,
    ) -> Dict[str, Any]:
        """
        Interpret a natural language query to extract search parameters.

        Args:
            query: Natural language query

        Returns:
            Dictionary with interpreted search parameters
        """
        if not self.is_available:
            return {"search_text": query, "filters": {}}

        try:
            system_prompt = """You are a query interpreter for a personal memory system.
Extract search parameters from natural language queries.

Output JSON with:
- search_text: The main search text (descriptive, for semantic search)
- temporal: Any time references (e.g., "last month", "2024", "between Jan and March")
- participants: Any mentioned people
- topics: Any mentioned topics/subjects
- sentiment: If positive/negative sentiment is specified

Example:
Query: "What did I discuss with John about marketing last week?"
Output: {
  "search_text": "discussion about marketing strategies",
  "temporal": "last week",
  "participants": ["John"],
  "topics": ["marketing"],
  "sentiment": null
}

Output ONLY valid JSON."""

            response = self._client.messages.create(
                model=self.model,
                max_tokens=512,
                system=system_prompt,
                messages=[{"role": "user", "content": f"Query: {query}"}],
            )

            response_text = response.content[0].text.strip()

            # Parse JSON
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            return json.loads(response_text)

        except Exception as e:
            logger.warning(f"Query interpretation failed: {e}")
            return {"search_text": query, "filters": {}}

    def generate_search_queries(
        self,
        query: str,
        num_queries: int = 3,
    ) -> List[str]:
        """
        Generate multiple search query variations for better recall.

        Args:
            query: Original query
            num_queries: Number of variations to generate

        Returns:
            List of search query variations
        """
        if not self.is_available:
            return [query]

        try:
            system_prompt = f"""Generate {num_queries} different search query variations for semantic search.
Each variation should capture different aspects or phrasings of the information need.
Make queries descriptive and suitable for embedding-based search.

Output as a JSON array of strings, nothing else.
Example: ["query 1", "query 2", "query 3"]"""

            response = self._client.messages.create(
                model=self.model,
                max_tokens=256,
                system=system_prompt,
                messages=[{"role": "user", "content": f"Original query: {query}"}],
            )

            response_text = response.content[0].text.strip()

            # Parse JSON array
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            queries = json.loads(response_text)

            if isinstance(queries, list):
                return queries[:num_queries]

            return [query]

        except Exception as e:
            logger.warning(f"Query generation failed: {e}")
            return [query]

    def refine_query(
        self,
        original_query: str,
        initial_results_summary: str,
        feedback: Optional[str] = None,
    ) -> str:
        """
        Refine a query based on initial results.

        Args:
            original_query: The original query
            initial_results_summary: Summary of initial results
            feedback: Optional user feedback

        Returns:
            Refined search query
        """
        if not self.is_available:
            return original_query

        try:
            system_prompt = """You are helping refine a search query for better results.
Based on the original query and initial results, suggest a refined search query.

Output ONLY the refined query text, nothing else."""

            user_content = f"""Original query: {original_query}

Initial results summary: {initial_results_summary}
"""

            if feedback:
                user_content += f"\nUser feedback: {feedback}"

            user_content += "\n\nSuggest a refined query:"

            response = self._client.messages.create(
                model=self.model,
                max_tokens=128,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}],
            )

            return response.content[0].text.strip()

        except Exception as e:
            logger.warning(f"Query refinement failed: {e}")
            return original_query


# Global planner instance
_planner: Optional[AgenticPlanner] = None


def get_agentic_planner(
    api_key: Optional[str] = None,
    model: str = "claude-sonnet-4-20250514",
) -> AgenticPlanner:
    """
    Get the global agentic planner instance.

    Args:
        api_key: Anthropic API key
        model: Model to use

    Returns:
        AgenticPlanner instance
    """
    global _planner
    if _planner is None:
        _planner = AgenticPlanner(api_key, model)
    return _planner


def plan_query(
    query: str,
    api_key: Optional[str] = None,
) -> QueryPlan:
    """
    Convenience function to plan a query.

    Args:
        query: Natural language query
        api_key: Optional API key

    Returns:
        QueryPlan
    """
    planner = get_agentic_planner(api_key)
    return planner.plan_query(query)
