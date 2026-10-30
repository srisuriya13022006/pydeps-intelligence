"""Models for representing discovered project file structures and metadata."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class ProjectStructure(BaseModel):
    """Discovered project layout, source files, notebooks, and metadata."""

    model_config = ConfigDict(extra="forbid")

    root_path: Path = Field(
        ...,
        description="Resolved absolute root directory of the project",
    )
    source_files: list[Path] = Field(
        default_factory=list,
        description="Discovered Python source files (.py), deterministically ordered",
    )
    notebook_files: list[Path] = Field(
        default_factory=list,
        description="Discovered Jupyter notebook files (.ipynb), deterministically ordered",
    )
    source_roots: list[Path] = Field(
        default_factory=list,
        description="Detected source root directories (e.g. 'src/' or project root)",
    )
    metadata_files: list[Path] = Field(
        default_factory=list,
        description="Detected project configuration or packaging files (pyproject.toml, etc.)",
    )
    local_modules: list[str] = Field(
        default_factory=list,
        description="Canonical module and top-level package names provided locally by the project",
    )
    diagnostics: list[str] = Field(
        default_factory=list,
        description="Informational diagnostics, warnings, or non-fatal scan errors encountered",
    )

    @property
    def total_source_files(self) -> int:
        """Return total count of Python source files found."""
        return len(self.source_files)

    @property
    def total_notebook_files(self) -> int:
        """Return total count of notebook files found."""
        return len(self.notebook_files)
