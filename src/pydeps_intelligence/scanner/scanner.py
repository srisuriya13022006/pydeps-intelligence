"""Project scanning and file discovery module."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from pathlib import Path

from pydeps_intelligence.models.project import DEFAULT_EXCLUDED_DIRECTORIES, ProjectConfig
from pydeps_intelligence.models.structure import ProjectStructure

KNOWN_METADATA_FILES = {
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "requirements-dev.txt",
    "Pipfile",
    "environment.yml",
    "tox.ini",
}


class ProjectScanner:
    """Recursively scans a Python project filesystem to discover source files and metadata."""

    def __init__(
        self,
        config: ProjectConfig | None = None,
        exclusions: Sequence[str] | None = None,
        follow_symlinks: bool = False,
    ) -> None:
        self.config = config
        if exclusions is not None:
            self.exclusions = set(exclusions)
        elif config is not None:
            self.exclusions = set(config.excluded_directories)
        else:
            self.exclusions = set(DEFAULT_EXCLUDED_DIRECTORIES)
        self.follow_symlinks = follow_symlinks

    def scan(self, project_path: Path | str = ".") -> ProjectStructure:
        """Scan target directory recursively and return structured project representation."""
        diagnostics: list[str] = []

        try:
            target = Path(project_path).resolve()
            if not target.exists():
                return ProjectStructure(
                    root_path=target,
                    source_files=[],
                    notebook_files=[],
                    source_roots=[],
                    metadata_files=[],
                    local_modules=[],
                    diagnostics=[f"Project directory does not exist: {target}"],
                )
        except (PermissionError, OSError) as exc:
            return ProjectStructure(
                root_path=Path(project_path),
                source_files=[],
                notebook_files=[],
                source_roots=[],
                metadata_files=[],
                local_modules=[],
                diagnostics=[f"Permission or OS error accessing path {project_path}: {exc}"],
            )

        if not target.is_dir():
            # If target is a single file, treat parent as root and target as sole source file
            is_py = target.suffix.lower() == ".py"
            is_ipynb = target.suffix.lower() == ".ipynb"
            return ProjectStructure(
                root_path=target.parent,
                source_files=[target] if is_py else [],
                notebook_files=[target] if is_ipynb else [],
                source_roots=[target.parent],
                metadata_files=[],
                local_modules=[target.stem] if is_py else [],
                diagnostics=[],
            )

        source_files: list[Path] = []
        notebook_files: list[Path] = []
        metadata_files: list[Path] = []
        visited_inodes: set[tuple[int, int]] = set()

        # Handle root permission / existence check
        try:
            target_stat = target.stat()
            visited_inodes.add((target_stat.st_dev, target_stat.st_ino))
        except (PermissionError, OSError) as exc:
            return ProjectStructure(
                root_path=target,
                source_files=[],
                notebook_files=[],
                source_roots=[],
                metadata_files=[],
                local_modules=[],
                diagnostics=[f"Permission or OS error accessing root {target}: {exc}"],
            )

        for root, dirs, files in os.walk(
            target,
            topdown=True,
            followlinks=self.follow_symlinks,
            onerror=lambda err: diagnostics.append(f"Directory access error: {err}"),
        ):
            root_path = Path(root)

            # Filter out excluded directories in-place to prevent traversing them
            dirs[:] = [
                d
                for d in dirs
                if d not in self.exclusions
                and not d.endswith(".egg-info")
                and not d.endswith(".dist-info")
                and not any(d.startswith(ex) for ex in self.exclusions if ex.startswith("."))
            ]

            # Cycle detection for symlinks
            if self.follow_symlinks:
                try:
                    stat = root_path.stat()
                    key = (stat.st_dev, stat.st_ino)
                    if key in visited_inodes and root_path != target:
                        dirs.clear()
                        continue
                    visited_inodes.add(key)
                except (PermissionError, OSError):
                    dirs.clear()
                    continue

            for file in files:
                file_path = root_path / file
                file_lower = file.lower()

                # Project metadata discovery
                if file in KNOWN_METADATA_FILES or file_lower.endswith(".txt"):
                    metadata_files.append(file_path)

                # Python source files (.py)
                if file_lower.endswith(".py"):
                    source_files.append(file_path)

                # Jupyter notebook files (.ipynb)
                elif file_lower.endswith(".ipynb"):
                    notebook_files.append(file_path)

        # Ensure deterministic file ordering
        source_files.sort(key=lambda p: p.as_posix())
        notebook_files.sort(key=lambda p: p.as_posix())
        metadata_files.sort(key=lambda p: p.as_posix())

        source_roots = self._detect_source_roots(target, source_files)
        local_modules = self._detect_local_modules(target, source_roots, source_files)

        return ProjectStructure(
            root_path=target,
            source_files=source_files,
            notebook_files=notebook_files,
            source_roots=source_roots,
            metadata_files=metadata_files,
            local_modules=sorted(set(local_modules)),
            diagnostics=diagnostics,
        )

    def _detect_source_roots(self, root_path: Path, source_files: list[Path]) -> list[Path]:
        """Identify source roots such as 'src/' or project root."""
        roots: list[Path] = []
        src_dir = root_path / "src"
        if src_dir.is_dir():
            roots.append(src_dir)

        # If any source files live outside src/ directly under root, include project root
        roots.append(root_path)
        return roots

    def _detect_local_modules(
        self,
        project_root: Path,
        source_roots: list[Path],
        source_files: list[Path],
    ) -> list[str]:
        """Detect top-level module and package names defined locally within the project."""
        modules: set[str] = set()

        for sf in source_files:
            try:
                rel = sf.relative_to(project_root)
            except ValueError:
                continue

            parts = rel.parts
            if not parts:
                continue

            # If under src/
            if parts[0] == "src" and len(parts) > 1:
                pkg_name = parts[1]
                if pkg_name.endswith(".py"):
                    modules.add(pkg_name[:-3])
                else:
                    modules.add(pkg_name)
            else:
                top = parts[0]
                if top.endswith(".py"):
                    modules.add(top[:-3])
                else:
                    modules.add(top)

        return sorted(modules)

    @staticmethod
    def extract_notebook_code(notebook_path: Path | str) -> str:
        """Parse code cells from a Jupyter notebook JSON without executing any cells."""
        path = Path(notebook_path)
        try:
            with path.open("r", encoding="utf-8") as f:
                nb_data = json.load(f)
        except Exception as exc:
            return f"# Failed to read notebook {path}: {exc}\n"

        cells = nb_data.get("cells", [])
        code_snippets: list[str] = []

        for idx, cell in enumerate(cells, start=1):
            if cell.get("cell_type") == "code":
                source = cell.get("source", [])
                if isinstance(source, list):
                    cell_text = "".join(source)
                elif isinstance(source, str):
                    cell_text = source
                else:
                    cell_text = ""
                # Strip IPython magic commands (e.g. %matplotlib, !pip) to prevent AST syntax errors
                clean_lines: list[str] = []
                for line in cell_text.splitlines():
                    stripped = line.strip()
                    if stripped.startswith("%") or stripped.startswith("!"):
                        clean_lines.append(f"# [ipython-magic] {line}")
                    else:
                        clean_lines.append(line)
                code_snippets.append(f"# [Cell {idx}]\n" + "\n".join(clean_lines) + "\n")

        return "\n".join(code_snippets)
