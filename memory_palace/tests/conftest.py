"""
Pytest configuration and fixtures for Memory Palace tests.
"""

import os
import pytest


def pytest_configure(config):
    """Configure pytest."""
    # Set test environment
    os.environ["MEMORY_PALACE_LOG_LEVEL"] = "WARNING"


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use default event loop policy."""
    import asyncio
    return asyncio.DefaultEventLoopPolicy()
