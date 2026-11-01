"""User-defined mapping overrides management."""

from __future__ import annotations

from collections.abc import Mapping

from packaging.utils import canonicalize_name


class MappingOverrides:
    """Manages explicit user-specified mappings from import names to distributions."""

    def __init__(self, overrides: Mapping[str, str | list[str]] | None = None) -> None:
        self._overrides: dict[str, list[str]] = {}
        if overrides:
            self.update(overrides)

    def update(self, overrides: Mapping[str, str | list[str]]) -> None:
        """Update or insert overrides."""
        for imp, dist in overrides.items():
            key = imp.strip().lower()
            if isinstance(dist, str):
                self._overrides[key] = [canonicalize_name(dist.strip())]
            elif isinstance(dist, (list, tuple, set)):
                self._overrides[key] = [canonicalize_name(d.strip()) for d in dist if d.strip()]

    def get_override(self, import_name: str) -> list[str] | None:
        """Return user override candidate distributions for the import name, if any."""
        key = import_name.strip().lower()
        if key in self._overrides:
            return list(self._overrides[key])

        # Check dotted base
        parts = key.split(".")
        if len(parts) > 1 and parts[0] in self._overrides:
            return list(self._overrides[parts[0]])

        return None

    def has_override(self, import_name: str) -> bool:
        """Return True if an explicit override exists for the import name."""
        return self.get_override(import_name) is not None
