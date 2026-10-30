"""HTTP client for interacting with the PyPI JSON API."""

from __future__ import annotations

import re
import time
from typing import Any

import httpx
from packaging.utils import canonicalize_name

from pydeps._version import __version__
from pydeps.exceptions import PyDepsError

# PEP 508 valid distribution name pattern
PACKAGE_NAME_REGEX = re.compile(r"^([A-Za-z0-9]|[A-Za-z0-9][A-Za-z0-9._-]*[A-Za-z0-9])$")
DEFAULT_USER_AGENT = f"PyDeps/{__version__} (+https://github.com/your-org/PyDeps)"
DEFAULT_TIMEOUT_SECONDS = 10.0
MAX_RETRIES = 3
BACKOFF_FACTOR = 0.5


class PyPIError(PyDepsError):
    """Base exception for PyPI client interactions."""


class PyPINotFoundError(PyPIError):
    """Raised when a package or release does not exist on PyPI (HTTP 404)."""


class PyPIRateLimitError(PyPIError):
    """Raised when PyPI rate limits requests (HTTP 429)."""


class PyPINetworkError(PyPIError):
    """Raised when network transport or connection fails."""


class PyPIClient:
    """Synchronous HTTP client for querying PyPI project and release endpoints."""

    def __init__(
        self,
        base_url: str = "https://pypi.org/pypi",
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        user_agent: str = DEFAULT_USER_AGENT,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.user_agent = user_agent
        self._external_client = client is not None
        self._client = client or httpx.Client(
            timeout=timeout,
            headers={"User-Agent": user_agent, "Accept": "application/json"},
            follow_redirects=True,
        )

    def close(self) -> None:
        """Close the underlying HTTP client session if owned."""
        if not self._external_client:
            self._client.close()

    def __enter__(self) -> PyPIClient:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def _validate_package_name(self, package_name: str) -> str:
        clean = package_name.strip()
        if not PACKAGE_NAME_REGEX.match(clean):
            raise PyPIError(f"Invalid distribution package name: '{package_name}'")
        return canonicalize_name(clean)

    def _request_with_retry(self, url: str) -> dict[str, Any]:
        """Execute HTTP GET with bounded exponential backoff for transient failures."""
        attempts = 0
        last_exc: Exception | None = None

        while attempts < MAX_RETRIES:
            attempts += 1
            try:
                response = self._client.get(
                    url,
                    headers={"User-Agent": self.user_agent, "Accept": "application/json"},
                )

                if response.status_code == 200:
                    try:
                        return response.json()
                    except Exception as json_err:
                        msg = f"Malformed JSON from PyPI at {url}: {json_err}"
                        raise PyPIError(msg) from json_err

                if response.status_code == 404:
                    raise PyPINotFoundError(f"Package or release not found on PyPI: {url}")

                if response.status_code == 429:
                    if attempts == MAX_RETRIES:
                        raise PyPIRateLimitError(f"PyPI rate limit exceeded (HTTP 429) at {url}")
                    sleep_time = BACKOFF_FACTOR * (2 ** (attempts - 1))
                    time.sleep(sleep_time)
                    continue

                if response.status_code >= 500:
                    if attempts == MAX_RETRIES:
                        raise PyPINetworkError(
                            f"PyPI server error (HTTP {response.status_code}) at {url}"
                        )
                    sleep_time = BACKOFF_FACTOR * (2 ** (attempts - 1))
                    time.sleep(sleep_time)
                    continue

                # Other HTTP client errors (400, 403, etc.)
                raise PyPIError(f"Unexpected HTTP {response.status_code} response from {url}")

            except (httpx.TimeoutException, httpx.NetworkError) as net_err:
                last_exc = net_err
                if attempts == MAX_RETRIES:
                    msg = f"Network error contacting PyPI at {url}: {net_err}"
                    raise PyPINetworkError(msg) from net_err
                sleep_time = BACKOFF_FACTOR * (2 ** (attempts - 1))
                time.sleep(sleep_time)

        raise PyPINetworkError(f"Failed to query {url} after {MAX_RETRIES} attempts: {last_exc}")

    def get_project_metadata(self, package_name: str) -> dict[str, Any]:
        """Fetch latest project metadata from /pypi/{package}/json."""
        canonical_name = self._validate_package_name(package_name)
        url = f"{self.base_url}/{canonical_name}/json"
        return self._request_with_retry(url)

    def get_release_metadata(self, package_name: str, version: str) -> dict[str, Any]:
        """Fetch version-specific metadata from /pypi/{package}/{version}/json."""
        canonical_name = self._validate_package_name(package_name)
        clean_version = version.strip()
        if not clean_version:
            return self.get_project_metadata(canonical_name)
        url = f"{self.base_url}/{canonical_name}/{clean_version}/json"
        return self._request_with_retry(url)
