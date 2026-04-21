"""Custom exceptions for the noaa_coops package.

Lives in its own module so low-level helpers (`_http`, `_parsing`,
`_products`, `_metadata`, `api`) can raise / catch without creating
a circular import through `station.py`.
"""

from __future__ import annotations


class COOPSAPIError(Exception):
    """Raised when a NOAA CO-OPS API request returns an error."""

    def __init__(self, message: str) -> None:
        """Initialize COOPSAPIError.

        Args:
            message: The error message.
        """
        self.message = message
        super().__init__(self.message)
