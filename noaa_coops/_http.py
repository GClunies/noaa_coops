"""HTTP session + retry policy for NOAA CO-OPS API calls.

Defines a module-level ``requests.Session`` with an ``HTTPAdapter`` that
retries transient failures (429 + 5xx) with exponential backoff. Every
call site in the package uses this session so connection pooling and
retry behavior are uniform.

Not thread-safe: a ``requests.Session`` is a shared mutable object.
Callers in multi-threaded contexts should construct their own
``requests.Session`` per thread if they plan to share a ``Station``
across workers.
"""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 30.0)
"""Default (connect, read) timeout tuple for NOAA API calls, in seconds.

The connect timeout is tight enough to fail fast on dead hosts; the read
timeout accommodates NOAA's ``mdapi`` and SOAP ``DataInventory`` endpoints
which can take tens of seconds on cold starts.
"""

_DEFAULT_RETRY = Retry(
    total=3,
    backoff_factor=0.5,
    # Cap total backoff at 30s so a degraded NOAA endpoint can't stall a
    # multi-block fetch indefinitely.
    backoff_max=30,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=frozenset(["GET"]),
    respect_retry_after_header=True,
    raise_on_status=False,
)


def _build_session() -> requests.Session:
    """Construct the module-level session. Factored out so tests can rebuild it."""
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=_DEFAULT_RETRY)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


_SESSION: requests.Session = _build_session()
"""Module-level HTTP session used by every request in this package."""
