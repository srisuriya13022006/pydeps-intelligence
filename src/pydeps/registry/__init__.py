"""Package mapping engine for translating import names to PyPI distributions."""

from pydeps.registry.mapping_cache import MappingCache
from pydeps.registry.mapping_database import CURATED_IMPORT_MAPPINGS, MappingDatabase
from pydeps.registry.mapping_overrides import MappingOverrides
from pydeps.registry.mapping_provider import (
    DatabaseMappingProvider,
    DirectHeuristicMappingProvider,
    InstalledEnvironmentMappingProvider,
    MappingProvider,
    OverrideMappingProvider,
)
from pydeps.registry.package_mapper import PackageMapper

__all__ = [
    "CURATED_IMPORT_MAPPINGS",
    "DatabaseMappingProvider",
    "DirectHeuristicMappingProvider",
    "InstalledEnvironmentMappingProvider",
    "MappingCache",
    "MappingDatabase",
    "MappingOverrides",
    "MappingProvider",
    "OverrideMappingProvider",
    "PackageMapper",
]
