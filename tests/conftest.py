"""Shared pytest configuration.

Provides the `vcr_config` fixture consumed by `pytest-recording`. Tests
marked with `@pytest.mark.vcr` automatically record their HTTP
interactions to `tests/cassettes/<test_module>/<test_name>.yaml` on
first run (with `--record-mode=new_episodes`) and replay from that file
on subsequent runs.

Re-recording:
    # Record new interactions, keep existing ones
    uv run pytest --record-mode=new_episodes

    # Re-record everything from scratch (picks up any NOAA API drift)
    uv run pytest --record-mode=rewrite
"""

from __future__ import annotations

import pytest


@pytest.fixture
def vcr_config() -> dict:
    """Cassette recording/replay configuration applied to every @pytest.mark.vcr test."""
    return {
        # Scrub anything secret-shaped from request headers before persisting
        # to the cassette file. NOAA's public API is unauthenticated, but
        # filtering is cheap insurance.
        "filter_headers": [
            "authorization",
            "cookie",
            "x-api-key",
            "user-agent",
        ],
        # Response headers can vary per call (Date, X-Request-Id, ETag) and
        # would otherwise force a re-record on every NOAA server restart.
        "filter_response_headers": [
            "date",
            "server",
            "set-cookie",
            "x-request-id",
            "etag",
        ],
        # "once": record if no cassette; replay if cassette exists; never
        # hit the network when the cassette is present.
        "record_mode": "once",
        # Decompress gzipped responses in the cassette so they're readable.
        "decode_compressed_response": True,
    }
