"""pytest conftest — project-wide fixtures and guards.

No-network guard
----------------
When LOCAL_DEV_MODE=true (the default) or ALLOW_NETWORK_CALLS=false, all
tests run with real socket connections blocked. Any test that accidentally
triggers a real HTTP call will fail immediately with a clear message rather
than hanging or incurring API costs.

Tests that legitimately need the network (evals, manual integration tests)
must be marked with @pytest.mark.integration and run with
ALLOW_NETWORK_CALLS=true in the environment.
"""

import os
import socket
from unittest.mock import patch

import pytest


def _is_network_blocked() -> bool:
    allow = os.getenv("ALLOW_NETWORK_CALLS", "false").lower()
    local = os.getenv("LOCAL_DEV_MODE", "true").lower()
    return allow != "true" or local == "true"


def _blocked_create_connection(*args, **kwargs):
    raise RuntimeError(
        "Network call attempted in local/test mode. "
        "Mark the test @pytest.mark.integration and set "
        "ALLOW_NETWORK_CALLS=true to run it, or mock the network call."
    )


@pytest.fixture(autouse=True)
def block_network_in_local_mode(request):
    """Auto-applied fixture that blocks socket connections in local mode.

    Tests marked @pytest.mark.integration are exempt.
    """
    if request.node.get_closest_marker("integration"):
        yield
        return

    if not _is_network_blocked():
        yield
        return

    with patch("socket.create_connection", side_effect=_blocked_create_connection):
        yield


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: mark test as requiring real network/API access (skipped in local mode)",
    )
