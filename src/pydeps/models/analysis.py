"""Aggregated import analysis models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from pydeps.models.imports import ImportRecord
from pydeps.models.report import AnalysisReport, ProjectInformation
from pydeps.models.structure import ProjectStructure


class ImportAnalysisResult(BaseModel):
    """Categorized import findings discovered across project source files."""

    model_config = ConfigDict(extra="forbid")

    structure: ProjectStructure = Field(
        ...,
        description="Underlying project structure analyzed",
    )
    target_python_version: str = Field(
        default="3.11",
        description="Target Python version used for standard library classification",
    )
    standard_library_imports: list[ImportRecord] = Field(
        default_factory=list,
        description="Imports resolved to Python standard library modules",
    )
    local_imports: list[ImportRecord] = Field(
        default_factory=list,
        description="Imports resolved to local project packages or modules",
    )
    external_candidate_imports: list[ImportRecord] = Field(
        default_factory=list,
        description="Imports corresponding to potential third-party PyPI distributions",
    )
    dynamic_imports: list[ImportRecord] = Field(
        default_factory=list,
        description="Statically identified dynamic imports (__import__, importlib)",
    )
    unresolved_imports: list[ImportRecord] = Field(
        default_factory=list,
        description="Imports that could not be verified or resolved deterministically",
    )
    type_checking_imports: list[ImportRecord] = Field(
        default_factory=list,
        description="Imports guarded inside TYPE_CHECKING conditions",
    )
    optional_imports: list[ImportRecord] = Field(
        default_factory=list,
        description="Imports guarded inside try/except ImportError or conditional blocks",
    )
    all_imports: list[ImportRecord] = Field(
        default_factory=list,
        description="Complete list of all unique import records discovered",
    )
    diagnostics: list[str] = Field(
        default_factory=list,
        description="Diagnostics, parsing caveats, or syntax warnings",
    )

    @property
    def unique_external_packages(self) -> set[str]:
        """Return unique top-level package names of external candidate imports."""
        return {
            rec.top_level_package or rec.module_name.split(".")[0]
            for rec in self.external_candidate_imports
            if rec.top_level_package or rec.module_name
        }

    @property
    def unique_standard_library_modules(self) -> set[str]:
        """Return unique top-level standard library module names."""
        return {
            rec.top_level_package or rec.module_name.split(".")[0]
            for rec in self.standard_library_imports
            if rec.top_level_package or rec.module_name
        }

    @property
    def unique_local_modules(self) -> set[str]:
        """Return unique local module/package names imported."""
        return {
            rec.top_level_package or rec.module_name.split(".")[0]
            for rec in self.local_imports
            if rec.top_level_package or rec.module_name
        }

    def to_analysis_report(self) -> AnalysisReport:
        """Convert findings into an AnalysisReport aggregate model."""
        return AnalysisReport(
            project_information=ProjectInformation(
                project_name=self.structure.root_path.name,
                project_path=self.structure.root_path,
                metadata={
                    "total_source_files": len(self.structure.source_files),
                    "total_notebook_files": len(self.structure.notebook_files),
                    "target_python_version": self.target_python_version,
                },
            ),
            discovered_imports=self.all_imports,
            mapped_dependencies=[],
            compatibility_results=[],
            resolution_results=None,
            validation_results=[],
            warnings=list(self.diagnostics),
        )

    def summary(self) -> dict[str, Any]:
        """Return high-level statistics summary of findings."""
        return {
            "root_path": str(self.structure.root_path),
            "source_files": len(self.structure.source_files),
            "notebook_files": len(self.structure.notebook_files),
            "total_import_statements": len(self.all_imports),
            "unique_external_packages": sorted(self.unique_external_packages),
            "unique_standard_library_modules": sorted(self.unique_standard_library_modules),
            "unique_local_modules": sorted(self.unique_local_modules),
            "dynamic_imports_count": len(self.dynamic_imports),
            "optional_imports_count": len(self.optional_imports),
            "type_checking_imports_count": len(self.type_checking_imports),
            "unresolved_imports_count": len(self.unresolved_imports),
            "diagnostics_count": len(self.diagnostics),
        }
