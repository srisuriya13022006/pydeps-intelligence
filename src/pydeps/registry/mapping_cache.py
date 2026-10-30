"""In-memory and persistent caching for package mappings."""

from __future__ import annotations

import json
from pathlib import Path

from pydeps.models.mapping import PackageMappingResult


class MappingCache:
    """Thread-safe in-memory and local disk cache for import-to-distribution mappings."""

    def __init__(self, cache_dir: Path | str | None = None) -> None:
        self._memory: dict[str, PackageMappingResult] = {}
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

    def _cache_file(self) -> Path | None:
        if self.cache_dir:
            return self.cache_dir / "mapping_cache_v1.json"
        return None

    def _load_from_disk(self) -> None:
        file = self._cache_file()
        if file and file.is_file():
            try:
                with file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                for k, v in data.items():
                    self._memory[k] = PackageMappingResult.model_validate(v)
            except Exception:
                pass

    def _save_to_disk(self) -> None:
        file = self._cache_file()
        if file:
            try:
                data = {k: v.model_dump(mode="json") for k, v in self._memory.items()}
                with file.open("w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            except Exception:
                pass

    def get(self, import_name: str) -> PackageMappingResult | None:
        """Retrieve a cached mapping result."""
        return self._memory.get(import_name.strip().lower())

    def set(self, import_name: str, result: PackageMappingResult) -> None:
        """Store a mapping result into the cache."""
        key = import_name.strip().lower()
        self._memory[key] = result
        self._save_to_disk()

    def clear(self) -> None:
        """Clear all cached entries in memory and on disk."""
        self._memory.clear()
        file = self._cache_file()
        if file and file.is_file():
            try:
                file.unlink()
            except OSError:
                pass
