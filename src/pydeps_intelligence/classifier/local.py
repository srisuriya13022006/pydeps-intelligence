"""Detection and resolution of project-local Python packages and modules."""

from __future__ import annotations

from pathlib import Path

from pydeps_intelligence.models.structure import ProjectStructure


class LocalModuleDetector:
    """Identifies and indexes local Python packages, modules, and relative import destinations."""

    def __init__(self, structure: ProjectStructure) -> None:
        self.structure = structure
        self.root_path = structure.root_path
        self._local_modules: set[str] = set()
        self._top_level_local: set[str] = set(structure.local_modules)
        self._file_to_module: dict[Path, str] = {}
        self._index_modules()

    def _index_modules(self) -> None:
        """Build dotted module names for all discovered source files."""
        for sf in self.structure.source_files:
            dotted = self._compute_dotted_name(sf)
            if dotted:
                self._file_to_module[sf.resolve()] = dotted
                parts = dotted.split(".")
                # Register all hierarchical prefixes: a, a.b, a.b.c
                for i in range(1, len(parts) + 1):
                    prefix = ".".join(parts[:i])
                    self._local_modules.add(prefix)
                self._top_level_local.add(parts[0])

    def _compute_dotted_name(self, source_file: Path) -> str | None:
        """Compute the dotted Python module path for a source file."""
        resolved = source_file.resolve()

        # Check against detected source roots (e.g. src/ or root)
        for sroot in self.structure.source_roots:
            try:
                rel = resolved.relative_to(sroot.resolve())
            except ValueError:
                continue

            parts = list(rel.parts)
            if not parts:
                continue

            # Strip extension from the leaf
            if parts[-1].endswith(".py"):
                parts[-1] = parts[-1][:-3]
            elif parts[-1].endswith(".ipynb"):
                parts[-1] = parts[-1][:-6]

            # If __init__, the package name is the parent folder
            if parts[-1] == "__init__":
                parts.pop()

            if parts:
                return ".".join(parts)

        # Fallback to relative from root_path
        try:
            rel = resolved.relative_to(self.root_path.resolve())
            parts = list(rel.parts)
            if parts:
                if parts[-1].endswith(".py"):
                    parts[-1] = parts[-1][:-3]
                if parts[-1] == "__init__":
                    parts.pop()
                return ".".join(parts)
        except ValueError:
            pass

        return None

    def get_module_for_file(self, source_file: Path) -> str | None:
        """Return the dotted module name corresponding to a source file."""
        return self._file_to_module.get(source_file.resolve())

    def resolve_relative_import(
        self,
        module_name: str | None,
        level: int,
        source_file: Path,
    ) -> str:
        """Resolve a relative import (level >= 1) against the importing source file's package."""
        current_mod = self.get_module_for_file(source_file)
        if not current_mod:
            # Fallback based on file location
            current_mod = self._compute_dotted_name(source_file) or ""

        parts = current_mod.split(".") if current_mod else []

        # If current file is not an __init__.py, its package is the parent (pop last element)
        is_init = source_file.name == "__init__.py"
        if not is_init and parts:
            pkg_parts = parts[:-1]
        else:
            pkg_parts = list(parts)

        # level=1 means current package (.): ascend 0 extra levels
        # level=2 means parent package (..): ascend 1 level
        ascend_levels = level - 1
        if ascend_levels > len(pkg_parts):
            # Attempted to ascend beyond project root
            base = ""
        elif ascend_levels > 0:
            base = ".".join(pkg_parts[:-ascend_levels])
        else:
            base = ".".join(pkg_parts)

        if module_name:
            return f"{base}.{module_name}" if base else module_name
        return base

    def is_local_module(self, module_name: str, source_file: Path | None = None) -> bool:
        """Determine whether an import name refers to a project-local module."""
        if not module_name:
            return False

        # If relative import
        if module_name.startswith("."):
            return True

        clean = module_name.strip()
        top_level = clean.split(".")[0]

        # Check exact matches or prefixes
        if clean in self._local_modules or top_level in self._top_level_local:
            return True

        # Check if adjacent to the current source file in the same directory
        if source_file is not None:
            parent_dir = source_file.parent
            direct_candidate = parent_dir / f"{top_level}.py"
            pkg_candidate = parent_dir / top_level / "__init__.py"
            if direct_candidate.is_file() or pkg_candidate.is_file():
                return True

        return False
