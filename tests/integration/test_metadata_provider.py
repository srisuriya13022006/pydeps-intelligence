"""Integration tests for MetadataProvider with mocked PyPI network responses and caching."""

from __future__ import annotations

import httpx
import pytest

from pydeps_intelligence.metadata.metadata_cache import MetadataCache
from pydeps_intelligence.metadata.metadata_provider import MetadataProvider
from pydeps_intelligence.metadata.pypi_client import PyPIClient


@pytest.fixture
def fake_pypi_project_data() -> dict:
    return {
        "info": {
            "name": "sample-pkg",
            "version": "1.2.0",
            "summary": "Sample package for testing.",
            "requires_python": ">=3.9",
            "requires_dist": [
                "requests>=2.28.0",
                "pytest; extra == 'test'",
            ],
            "yanked": False,
            "yanked_reason": None,
        },
        "releases": {
            "1.2.0": [
                {
                    "filename": "sample_pkg-1.2.0-py3-none-any.whl",
                    "packagetype": "bdist_wheel",
                    "python_version": "py3",
                    "digests": {"sha256": "abc1234567890abcdef"},
                    "yanked": False,
                }
            ]
        },
        "urls": [],
    }


def test_provider_network_fetch_and_caching(fake_pypi_project_data: dict) -> None:
    """Test MetadataProvider queries PyPI on cache miss and serves from cache subsequently."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json=fake_pypi_project_data)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = PyPIClient(client=http_client)
        cache = MetadataCache()
        provider = MetadataProvider(client=client, cache=cache)

        # 1. First fetch: network
        res1 = provider.get_metadata("sample-pkg")
        assert res1.success is True
        assert res1.source == "network"
        assert res1.package_name == "sample-pkg"
        assert res1.version == "1.2.0"
        assert res1.metadata is not None
        assert len(res1.metadata.requires_dist) == 2
        assert len(calls) == 1

        # 2. Second fetch: cache hit (no new network call)
        res2 = provider.get_metadata("sample-pkg")
        assert res2.success is True
        assert res2.source == "cache"
        assert res2.version == "1.2.0"
        assert len(calls) == 1


def test_provider_offline_mode(tmp_path, fake_pypi_project_data: dict) -> None:
    """Test MetadataProvider honors offline mode during cache miss and cache hit."""
    cache_file = tmp_path / "metadata_cache.json"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=fake_pypi_project_data)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = PyPIClient(client=http_client)

        # 1. Populate cache in online mode
        cache = MetadataCache(cache_file=cache_file)
        online_provider = MetadataProvider(client=client, cache=cache, offline=False)
        res_online = online_provider.get_metadata("sample-pkg")
        assert res_online.success is True

        # 2. In offline mode with a new provider pointing to the same cache
        offline_cache = MetadataCache(cache_file=cache_file, offline=True)
        offline_provider = MetadataProvider(client=client, cache=offline_cache, offline=True)

        # Cache hit in offline mode succeeds
        res_hit = offline_provider.get_metadata("sample-pkg")
        assert res_hit.success is True
        assert res_hit.source == "cache"

        # Cache miss in offline mode fails gracefully without network attempt
        res_miss = offline_provider.get_metadata("non-cached-package")
        assert res_miss.success is False
        assert res_miss.source == "offline_cache_miss"
        assert "offline mode is enabled" in res_miss.diagnostics[0]


def test_provider_404_not_found() -> None:
    """Test handling of 404 Not Found from PyPI."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = PyPIClient(client=http_client)
        provider = MetadataProvider(client=client)

        res = provider.get_metadata("does-not-exist-xyz123")
        assert res.success is False
        assert res.source == "network_404"
        assert res.metadata is None
        assert any("not found" in d.lower() for d in res.diagnostics)


def test_provider_invalid_package_name() -> None:
    """Test rejection of invalid distribution package names without network calls."""
    provider = MetadataProvider()
    res = provider.get_metadata("../suspicious/name")
    assert res.success is False
    assert res.source == "error"
    assert "Invalid distribution package name" in res.diagnostics[0]


def test_provider_batch_metadata(fake_pypi_project_data: dict) -> None:
    """Test batch querying of multiple distribution names."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=fake_pypi_project_data)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        client = PyPIClient(client=http_client)
        provider = MetadataProvider(client=client)

        results = provider.get_batch_metadata(["sample-pkg", "SAMPLE_PKG", "other-pkg"])
        # Should be deduplicated by canonical name
        assert "sample-pkg" in results
        assert results["sample-pkg"].success is True
