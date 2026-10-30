"""Package mapping and resolution models."""

from __future__ import annotations

from enum import Enum
from typing import Any

from packaging.utils import canonicalize_name
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from pydeps.models.analysis import ImportAnalysisResult
from pydeps.models.imports import MappingSource


class ConfidenceLevel(str, Enum):
    """Categorical confidence score for an import-to-distribution mapping."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNRESOLVED = "unresolved"


class PackageMappingResult(BaseModel):
    """Result of mapping a Python import name to candidate distribution packages."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    import_name: str = Field(
        ...,
        description="The imported module or namespace name",
    )
    candidate_distributions: list[str] = Field(
        default_factory=list,
        description="Candidate PyPI distribution names providing this import",
    )
    selected_distribution: str | None = Field(
        default=None,
        description="The selected canonical distribution name, if resolved unambiguously",
    )
    mapping_source: MappingSource = Field(
        default=MappingSource.HEURISTIC,
        description="The primary source or heuristic used for this mapping",
    )
    confidence: ConfidenceLevel = Field(
        default=ConfidenceLevel.LOW,
        description="Categorical confidence in this mapping determination",
    )
    confidence_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Numeric confidence score between 0.0 and 1.0",
    )
    is_ambiguous: bool = Field(
        default=False,
        description="Whether multiple distinct distributions provide this import",
    )
    explanation: str | None = Field(
        default=None,
        description="Human-readable explanation of the mapping decision",
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Evidence references (e.g. database match, installed metadata, override)",
    )
    diagnostic: str | None = Field(
        default=None,
        description="Diagnostics or warnings (e.g. why a mapping could not be resolved)",
    )

    @field_validator("candidate_distributions")
    @classmethod
    def normalize_candidates(cls, v: list[str]) -> list[str]:
        # Return unique canonicalized names while preserving order
        seen: set[str] = set()
        normalized: list[str] = []
        for name in v:
            clean = canonicalize_name(name.strip())
            if clean and clean not in seen:
                seen.add(clean)
                normalized.append(clean)
        return normalized

    @field_validator("selected_distribution")
    @classmethod
    def normalize_selected(cls, v: str | None) -> str | None:
        if v is None:
            return None
        clean = canonicalize_name(v.strip())
        return clean or None


class PackageReport(BaseModel):
    """Report connecting discovered source imports to resolved distribution packages."""

    model_config = ConfigDict(extra="forbid")

    analysis: ImportAnalysisResult = Field(
        ...,
        description="Underlying source code import analysis findings",
    )
    mappings: list[PackageMappingResult] = Field(
        default_factory=list,
        description="Mapping results for all candidate external imports",
    )
    unresolved_imports: list[str] = Field(
        default_factory=list,
        description="Import names that could not be mapped to any known distribution",
    )
    ambiguous_imports: list[PackageMappingResult] = Field(
        default_factory=list,
        description="Imports associated with multiple competing distributions",
    )
    diagnostics: list[str] = Field(
        default_factory=list,
        description="Diagnostic messages and mapping warnings",
    )

    @computed_field
    @property
    def selected_distributions(self) -> list[str]:
        """Return unique sorted canonical distribution names resolved from imports."""
        dists: set[str] = set()
        for m in self.mappings:
            if m.selected_distribution:
                dists.add(m.selected_distribution)
        return sorted(dists)

    def summary(self) -> dict[str, Any]:
        """Return summary statistics of mapping findings."""
        return {
            "total_candidate_imports": len(self.mappings),
            "resolved_distributions_count": len(self.selected_distributions),
            "selected_distributions": self.selected_distributions,
            "ambiguous_count": len(self.ambiguous_imports),
            "unresolved_count": len(self.unresolved_imports),
            "diagnostics_count": len(self.diagnostics),
        }
