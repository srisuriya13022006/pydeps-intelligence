"""Integration tests for PyPIClient using mocked HTTP transports."""

from __future__ import annotations

import httpx
import pytest

from pydeps.metadata.pypi_client import (
    PyPIClient,
    PyPIError,
    PyPINetworkError,
    PyPINotFoundError,
    PyPIRateLimitError,
)


def test_client_get_project_metadata_200() -> None:
    """Test successful 200 OK project retrieval from PyPI JSON endpoint."""
    fake_payload = {
        "info": {
            "name": "requests",
            "version": "2.31.0",
            "summary": "Python HTTP for Humans.",
        },
        "releases": {"2.31.0": []},
        "urls": [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/pypi/requests/json"
        assert "PyDeps/" in request.headers["User-Agent"]
        return httpx.Response(200, json=fake_payload)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = PyPIClient(client=http_client)
        data = client.get_project_metadata("requests")
        assert data["info"]["name"] == "requests"
        assert data["info"]["version"] == "2.31.0"


def test_client_get_version_metadata_200() -> None:
    """Test successful 200 OK version-specific release retrieval."""
    fake_payload = {
        "info": {
            "name": "requests",
            "version": "2.28.0",
        },
        "urls": [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/pypi/requests/2.28.0/json"
        return httpx.Response(200, json=fake_payload)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = PyPIClient(client=http_client)
        data = client.get_release_metadata("requests", "2.28.0")
        assert data["info"]["version"] == "2.28.0"


def test_client_http_404_raises_not_found() -> None:
    """Test that HTTP 404 raises PyPINotFoundError immediately without retrying."""
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = PyPIClient(client=http_client)
        with pytest.raises(PyPINotFoundError):
            client.get_project_metadata("non-existent-pkg-12345")
        # 404 should never be retried
        assert attempts == 1


def test_client_http_429_rate_limiting_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that HTTP 429 triggers bounded retries before raising PyPIRateLimitError."""
    # Prevent test slowdown during backoff sleep
    monkeypatch.setattr("time.sleep", lambda _: None)

    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(429)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = PyPIClient(client=http_client)
        with pytest.raises(PyPIRateLimitError):
            client.get_project_metadata("busy-package")
        # Bounded retries: 3 attempts
        assert attempts == 3


def test_client_http_500_server_error_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that HTTP 5xx triggers bounded retries before raising PyPINetworkError."""
    monkeypatch.setattr("time.sleep", lambda _: None)

    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(502)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = PyPIClient(client=http_client)
        with pytest.raises(PyPINetworkError):
            client.get_project_metadata("failing-package")
        assert attempts == 3


def test_client_malformed_json_response() -> None:
    """Test that malformed JSON response raises PyPIError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"invalid { json")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = PyPIClient(client=http_client)
        with pytest.raises(PyPIError) as exc_info:
            client.get_project_metadata("bad-json-pkg")
        assert "Malformed JSON" in str(exc_info.value)


def test_client_invalid_package_name_validation() -> None:
    """Test that invalid package names are rejected prior to sending requests."""
    client = PyPIClient()
    with pytest.raises(PyPIError) as exc_info:
        client.get_project_metadata("invalid/name/../../path")
    assert "Invalid distribution package name" in str(exc_info.value)
