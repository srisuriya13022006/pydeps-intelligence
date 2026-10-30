"""Evidence providers for mapping imported module names to distributions."""

from __future__ import annotations

import importlib.metadata
from abc import ABC, abstractmethod
from collections.abc import Mapping

from packaging.utils import canonicalize_name

from pydeps.models.imports import MappingSource
from pydeps.registry.mapping_database import MappingDatabase
from pydeps.registry.mapping_overrides import MappingOverrides


class MappingProvider(ABC):
    """Abstract evidence provider for discovering distribution candidates for an import."""

    @property
    @abstractmethod
    def source(self) -> MappingSource:
        """The mapping source category for candidates resolved by this provider."""

    @abstractmethod
    def resolve_candidates(self, import_name: str) -> list[str]:
        """Return potential distribution names that provide the given import name."""


class OverrideMappingProvider(MappingProvider):
    """Resolves mappings using explicit user-defined configuration overrides."""

    def __init__(
        self,
        overrides: MappingOverrides | Mapping[str, str | list[str]] | None = None,
    ) -> None:
        if isinstance(overrides, MappingOverrides):
            self._overrides = overrides
        else:
            self._overrides = MappingOverrides(overrides)

    @property
    def source(self) -> MappingSource:
        return MappingSource.OVERRIDE

    def resolve_candidates(self, import_name: str) -> list[str]:
        candidates = self._overrides.get_override(import_name)
        return candidates or []


class DatabaseMappingProvider(MappingProvider):
    """Resolves mappings using the curated bundled distribution database."""

    def __init__(self, database: MappingDatabase | None = None) -> None:
        self._db = database or MappingDatabase()

    @property
    def source(self) -> MappingSource:
        return MappingSource.KNOWN_MAPPING

    def resolve_candidates(self, import_name: str) -> list[str]:
        return self._db.get_candidates(import_name)


class InstalledEnvironmentMappingProvider(MappingProvider):
    """Inspects the local running environment via importlib.metadata.packages_distributions().

    Treated as advisory evidence because target projects may target different environments.
    """

    def __init__(self) -> None:
        self._packages_distributions: dict[str, list[str]] | None = None

    @property
    def source(self) -> MappingSource:
        return MappingSource.METADATA

    def _get_distributions_map(self) -> dict[str, list[str]]:
        if self._packages_distributions is None:
            try:
                if hasattr(importlib.metadata, "packages_distributions"):
                    raw = importlib.metadata.packages_distributions()
                    self._packages_distributions = {
                        k.lower(): [canonicalize_name(d) for d in dists] for k, dists in raw.items()
                    }
                else:
                    self._packages_distributions = {}
            except Exception:
                self._packages_distributions = {}
        return self._packages_distributions

    def resolve_candidates(self, import_name: str) -> list[str]:
        pkg_map = self._get_distributions_map()
        clean = import_name.strip().lower()
        top_level = clean.split(".")[0]

        candidates = pkg_map.get(clean) or pkg_map.get(top_level)
        if candidates:
            return list(candidates)
        return []


class DirectHeuristicMappingProvider(MappingProvider):
    """Fallback heuristic assuming package distribution name matches top-level module name."""

    @property
    def source(self) -> MappingSource:
        return MappingSource.HEURISTIC

    def resolve_candidates(self, import_name: str) -> list[str]:
        clean = import_name.strip().lstrip(".")
        if not clean:
            return []
        top_level = clean.split(".")[0]
        # Canonical distribution name
        return [canonicalize_name(top_level)]
