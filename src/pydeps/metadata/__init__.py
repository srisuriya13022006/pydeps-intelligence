"""PyPI metadata retrieval, parsing, and caching package."""

from pydeps.metadata.metadata_cache import MetadataCache
from pydeps.metadata.metadata_models import MetadataResult, PackageRelease, ReleaseArtifact
from pydeps.metadata.metadata_parser import (
    parse_pypi_release,
    parse_requirement_entry,
    parse_wheel_platform_tags,
)
from pydeps.metadata.metadata_provider import MetadataProvider
from pydeps.metadata.pypi_client import (
    PyPIClient,
    PyPIError,
    PyPINetworkError,
    PyPINotFoundError,
    PyPIRateLimitError,
)
from pydeps.metadata.release_metadata import (
    find_sdist_artifact,
    find_wheel_artifacts,
    get_all_platform_tags,
)

__all__ = [
    "MetadataCache",
    "MetadataProvider",
    "MetadataResult",
    "PackageRelease",
    "PyPIClient",
    "PyPIError",
    "PyPINetworkError",
    "PyPINotFoundError",
    "PyPIRateLimitError",
    "ReleaseArtifact",
    "find_sdist_artifact",
    "find_wheel_artifacts",
    "get_all_platform_tags",
    "parse_pypi_release",
    "parse_requirement_entry",
    "parse_wheel_platform_tags",
]
