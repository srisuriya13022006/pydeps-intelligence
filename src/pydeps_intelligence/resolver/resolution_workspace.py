"""Isolated temporary workspace management for running dependency resolution."""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydeps_intelligence.models.dependencies import Dependency, DependencyType


class ResolutionWorkspace:
    """Manages an isolated, disposable filesystem workspace for running resolver commands.

    Prevents unintended modification of the user's actual project directory.
    """

    def __init__(
        self,
        base_dir: Path | str | None = None,
        prefix: str = "pydeps_resolver_",
    ) -> None:
        self.temp_dir: Path = Path(tempfile.mkdtemp(prefix=prefix, dir=base_dir))
        self._cleaned_up = False

    @property
    def path(self) -> Path:
        """Root path of the temporary resolution workspace."""
        return self.temp_dir

    def create_synthetic_pyproject_toml(
        self,
        dependencies: Sequence[Dependency],
        dev_dependencies: Sequence[Dependency] | None = None,
        requires_python: str = ">=3.8",
        project_name: str = "pydeps-synthetic-project",
        version: str = "0.1.0",
        extras_map: dict[str, list[str]] | None = None,
    ) -> Path:
        """Generate a valid PEP 621 pyproject.toml in the workspace."""
        pyproject_file = self.temp_dir / "pyproject.toml"

        dep_strings = [
            d.to_pep508() for d in dependencies if d.dependency_type != DependencyType.DEV
        ]
        dev_strings = (
            [d.to_pep508() for d in dev_dependencies]
            if dev_dependencies
            else [d.to_pep508() for d in dependencies if d.dependency_type == DependencyType.DEV]
        )

        lines: list[str] = [
            "[project]",
            f'name = "{project_name}"',
            f'version = "{version}"',
            f'requires-python = "{requires_python}"',
            "dependencies = [",
        ]

        for s in sorted(dep_strings):
            lines.append(f'    "{s}",')
        lines.append("]")
        lines.append("")

        if dev_strings or extras_map:
            lines.append("[project.optional-dependencies]")
            if dev_strings:
                lines.append("dev = [")
                for s in sorted(dev_strings):
                    lines.append(f'    "{s}",')
                lines.append("]")
            if extras_map:
                for extra_name, extra_deps in sorted(extras_map.items()):
                    if extra_name == "dev" and dev_strings:
                        continue
                    lines.append(f"{extra_name} = [")
                    for s in sorted(extra_deps):
                        lines.append(f'    "{s}",')
                    lines.append("]")
            lines.append("")

            # PEP 735 dependency groups
            if dev_strings:
                lines.append("[dependency-groups]")
                lines.append("dev = [")
                for s in sorted(dev_strings):
                    lines.append(f'    "{s}",')
                lines.append("]")
                lines.append("")

        content = "\n".join(lines)
        with open(pyproject_file, "w", encoding="utf-8") as f:
            f.write(content)

        return pyproject_file

    def create_requirements_in(
        self, dependencies: Sequence[Dependency], filename: str = "requirements.in"
    ) -> Path:
        """Write dependencies to a requirements.in or requirements.txt file in the workspace."""
        req_file = self.temp_dir / filename
        lines = [d.to_pep508() for d in dependencies]
        with open(req_file, "w", encoding="utf-8") as f:
            f.write("\n".join(sorted(lines)) + "\n")
        return req_file

    def copy_existing_file(self, src: Path, dest_name: str | None = None) -> Path | None:
        """Copy a file from the user's project into the resolution workspace."""
        if not src.exists():
            return None
        target = self.temp_dir / (dest_name or src.name)
        shutil.copy2(src, target)
        return target

    def cleanup(self) -> None:
        """Remove the temporary directory and all contents."""
        if not self._cleaned_up and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            self._cleaned_up = True

    def __enter__(self) -> ResolutionWorkspace:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.cleanup()
