"""Metadata provider coordinating network requests, caching, and parsing."""

from __future__ import annotations

from collections.abc import Sequence

from packaging.utils import canonicalize_name

from pydeps.metadata.metadata_cache import MetadataCache
from pydeps.metadata.metadata_models import MetadataResult
from pydeps.metadata.metadata_parser import parse_pypi_release
from pydeps.metadata.pypi_client import (
    PACKAGE_NAME_REGEX,
    PyPIClient,
    PyPIError,
    PyPINotFoundError,
)


class MetadataProvider:
    """Retrieves, caches, and parses package release metadata from PyPI or local cache."""

    def __init__(
        self,
        client: PyPIClient | None = None,
        cache: MetadataCache | None = None,
        offline: bool = False,
    ) -> None:
        self.client = client or PyPIClient()
        self.cache = cache or MetadataCache(offline=offline)
        self.offline = offline

    def get_metadata(
        self,
        package_name: str,
        version: str | None = None,
        offline: bool | None = None,
    ) -> MetadataResult:
        """Fetch release metadata for a package, checking cache first before network."""
        is_offline = self.offline if offline is None else offline
        clean_name = package_name.strip()

        if not PACKAGE_NAME_REGEX.match(clean_name):
            return MetadataResult(
                success=False,
                package_name=clean_name or "unknown",
                version=version,
                metadata=None,
                source="error",
                diagnostics=[f"Invalid distribution package name: '{clean_name}'"],
            )

        canonical_name = canonicalize_name(clean_name)

        # 1. Check cache
        cached_release = self.cache.get(canonical_name, version)
        if cached_release is not None:
            return MetadataResult(
                success=True,
                package_name=canonical_name,
                version=cached_release.version,
                metadata=cached_release,
                source="cache",
                diagnostics=[],
            )

        # 2. Check offline mode
        if is_offline:
            return MetadataResult(
                success=False,
                package_name=canonical_name,
                version=version,
                metadata=None,
                source="offline_cache_miss",
                diagnostics=[
                    f"Metadata for '{canonical_name}' not available in cache "
                    f"and offline mode is enabled."
                ],
            )

        # 3. Network fetch from PyPI
        try:
            if version:
                raw_data = self.client.get_release_metadata(canonical_name, version)
            else:
                raw_data = self.client.get_project_metadata(canonical_name)

            release, diags = parse_pypi_release(raw_data, version=version)

            # Store in cache
            self.cache.set(canonical_name, release, version=version)

            return MetadataResult(
                success=True,
                package_name=canonical_name,
                version=release.version,
                metadata=release,
                source="network",
                diagnostics=diags,
            )

        except PyPINotFoundError as not_found_err:
            return MetadataResult(
                success=False,
                package_name=canonical_name,
                version=version,
                metadata=None,
                source="network_404",
                diagnostics=[str(not_found_err)],
            )
        except PyPIError as pypi_err:
            return MetadataResult(
                success=False,
                package_name=canonical_name,
                version=version,
                metadata=None,
                source="network_error",
                diagnostics=[f"Failed to fetch metadata for '{canonical_name}': {pypi_err}"],
            )
        except Exception as exc:
            return MetadataResult(
                success=False,
                package_name=canonical_name,
                version=version,
                metadata=None,
                source="unexpected_error",
                diagnostics=[f"Unexpected error retrieving metadata for '{canonical_name}': {exc}"],
            )

    def get_batch_metadata(
        self,
        package_names: Sequence[str],
        offline: bool | None = None,
    ) -> dict[str, MetadataResult]:
        """Fetch metadata for multiple packages deterministically."""
        results: dict[str, MetadataResult] = {}
        unique_packages = sorted({canonicalize_name(p.strip()) for p in package_names if p.strip()})

        for pkg in unique_packages:
            results[pkg] = self.get_metadata(pkg, offline=offline)

        return results
