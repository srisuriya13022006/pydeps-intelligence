"""Unit tests for MetadataCache."""

from __future__ import annotations

from pathlib import Path

from pydeps.metadata.metadata_cache import MetadataCache
from pydeps.metadata.metadata_models import PackageRelease


def _create_sample_release(name: str = "sample", version: str = "1.0.0") -> PackageRelease:
    return PackageRelease(
        distribution_name=name,
        version=version,
        requires_python=">=3.8",
        requires_dist=[],
        provides_extra=[],
        release_files=[],
    )


def test_metadata_cache_in_memory() -> None:
    """Test in-memory cache storage and retrieval."""
    cache = MetadataCache(ttl_seconds=3600)
    rel = _create_sample_release("requests", "2.31.0")

    cache.set("requests", rel)
    retrieved = cache.get("requests", "2.31.0")
    assert retrieved is not None
    assert retrieved.distribution_name == "requests"
    assert retrieved.version == "2.31.0"

    # Different version
    assert cache.get("requests", "1.0.0") is None


def test_metadata_cache_disk_persistence(tmp_path: Path) -> None:
    """Test persistent caching to disk and re-loading in a new instance."""
    cache_dir = tmp_path / "cache"
    cache1 = MetadataCache(cache_dir=cache_dir)
    rel = _create_sample_release("click", "8.1.7")

    cache1.set("click", rel)

    # Instantiate second cache instance pointing to same directory
    cache2 = MetadataCache(cache_dir=cache_dir)
    retrieved = cache2.get("click", "8.1.7")
    assert retrieved is not None
    assert retrieved.distribution_name == "click"


def test_metadata_cache_ttl_expiration() -> None:
    """Test that entries older than TTL expire unless offline mode is enabled."""
    cache = MetadataCache(ttl_seconds=1)  # 1 second TTL
    rel = _create_sample_release("fastapi", "0.100.0")

    cache.set("fastapi", rel)
    assert cache.get("fastapi", "0.100.0") is not None

    # Artificially expire the cache entry
    key = cache._make_key("fastapi", "0.100.0")
    old_time, entry = cache._memory[key]
    cache._memory[key] = (old_time - 100.0, entry)

    # In online mode, should be expired
    assert cache.get("fastapi", "0.100.0") is None

    # In offline mode, should return even when expired
    cache.offline = True
    assert cache.get("fastapi", "0.100.0") is not None


def test_metadata_cache_invalidation_and_clear(tmp_path: Path) -> None:
    """Test invalidating specific packages and clearing the entire cache."""
    cache = MetadataCache(cache_dir=tmp_path)
    rel1 = _create_sample_release("pkg-a", "1.0.0")
    rel2 = _create_sample_release("pkg-b", "2.0.0")

    cache.set("pkg-a", rel1)
    cache.set("pkg-b", rel2)

    cache.invalidate("pkg-a")
    assert cache.get("pkg-a", "1.0.0") is None
    assert cache.get("pkg-b", "2.0.0") is not None

    cache.clear()
    assert cache.get("pkg-b", "2.0.0") is None
