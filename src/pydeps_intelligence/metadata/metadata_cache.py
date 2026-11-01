"""In-memory and persistent disk caching for PyPI metadata."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from packaging.utils import canonicalize_name

from pydeps_intelligence.metadata.metadata_models import PackageRelease

DEFAULT_CACHE_TTL_SECONDS = 86400  # 24 hours
SCHEMA_VERSION = "pydeps_metadata_v1"


class MetadataCache:
    """Manages cached PyPI metadata records in memory and on filesystem."""

    def __init__(
        self,
        cache_dir: Path | str | None = None,
        cache_file: Path | str | None = None,
        ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
        offline: bool = False,
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self.offline = offline
        self._memory: dict[str, tuple[float, PackageRelease]] = {}

        if cache_file:
            self._custom_cache_file = Path(cache_file)
            self.cache_dir = self._custom_cache_file.parent
        else:
            self._custom_cache_file = None
            self.cache_dir = Path(cache_dir) if cache_dir else None

        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

    def _cache_file(self) -> Path | None:
        if self._custom_cache_file:
            return self._custom_cache_file
        if self.cache_dir:
            return self.cache_dir / f"{SCHEMA_VERSION}.json"
        return None

    def _make_key(self, package_name: str, version: str | None = None) -> str:
        clean_pkg = canonicalize_name(package_name.strip())
        clean_ver = version.strip() if version else "latest"
        return f"{clean_pkg}:{clean_ver}"

    def _load_from_disk(self) -> None:
        file = self._cache_file()
        if not file or not file.is_file():
            return

        try:
            with file.open("r", encoding="utf-8") as f:
                data = json.load(f)

            if data.get("schema_version") != SCHEMA_VERSION:
                return

            entries = data.get("entries", {})
            for key, val in entries.items():
                timestamp = val.get("timestamp", 0.0)
                record_data = val.get("payload")
                if record_data:
                    release = PackageRelease.model_validate(record_data)
                    self._memory[key] = (timestamp, release)
        except Exception:
            # Corrupted cache file is ignored
            pass

    def _save_to_disk(self) -> None:
        file = self._cache_file()
        if not file:
            return

        try:
            entries: dict[str, Any] = {}
            for key, (ts, release) in self._memory.items():
                entries[key] = {
                    "timestamp": ts,
                    "payload": release.model_dump(mode="json"),
                }
            payload = {
                "schema_version": SCHEMA_VERSION,
                "saved_at": time.time(),
                "entries": entries,
            }
            with file.open("w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception:
            pass

    def get(self, package_name: str, version: str | None = None) -> PackageRelease | None:
        """Retrieve cached metadata for package and version if valid and not expired."""
        key = self._make_key(package_name, version)
        entry = self._memory.get(key)
        if not entry and (version is None or version == "latest"):
            prefix = f"{canonicalize_name(package_name)}:"
            matching = [k for k in self._memory if k.startswith(prefix)]
            if matching:
                entry = self._memory[matching[-1]]

        if not entry:
            return None

        cached_time, release = entry
        age = time.time() - cached_time

        # In offline mode, return whatever is cached even if older than TTL
        if self.offline:
            return release

        if age <= self.ttl_seconds:
            return release

        return None

    def set(self, package_name: str, release: PackageRelease, version: str | None = None) -> None:
        """Cache a release metadata entry."""
        now = time.time()
        # Cache under specific release version
        exact_key = self._make_key(package_name, release.version)
        self._memory[exact_key] = (now, release)

        # If fetched as unversioned/latest, also cache under "latest"
        if not version or version == "latest":
            latest_key = self._make_key(package_name, None)
            self._memory[latest_key] = (now, release)

        self._save_to_disk()

    def invalidate(self, package_name: str) -> None:
        """Invalidate all cached records for a given package name."""
        prefix = f"{canonicalize_name(package_name)}:"
        keys_to_remove = [k for k in self._memory if k.startswith(prefix)]
        for k in keys_to_remove:
            self._memory.pop(k, None)
        self._save_to_disk()

    def clear(self) -> None:
        """Clear all in-memory and persistent cache entries."""
        self._memory.clear()
        file = self._cache_file()
        if file and file.is_file():
            try:
                file.unlink()
            except OSError:
                pass
