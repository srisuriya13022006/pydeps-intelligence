"""Models for Python source imports and package distribution mappings."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ImportType(str, Enum):
    """Categorization of an extracted import statement."""

    STANDARD_LIBRARY = "standard_library"
    THIRD_PARTY = "third_party"
    FIRST_PARTY = "first_party"
    CONDITIONAL = "conditional"
    TYPE_CHECKING = "type_checking"
    UNKNOWN = "unknown"


class MappingSource(str, Enum):
    """Source or method used to resolve an import name to a PyPI distribution name."""

    DIRECT = "direct"
    STDLIB = "stdlib"
    KNOWN_MAPPING = "known_mapping"
    METADATA = "metadata"
    HEURISTIC = "heuristic"


class ImportRecord(BaseModel):
    """Represents a discovered Python import statement in the project source."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    module_name: str = Field(
        ...,
        description="Top-level or dotted module name imported (e.g., 'yaml', 'urllib.parse')",
    )
    source_file: Path = Field(
        ...,
        description="Path to the source file where the import was located",
    )
    line_number: int = Field(
        ...,
        ge=1,
        description="1-based line number of the import statement",
    )
    import_type: ImportType = Field(
        default=ImportType.UNKNOWN,
        description="Classification of the import",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0",
    )

    @field_validator("module_name")
    @classmethod
    def validate_module_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("module_name must not be empty")
        return trimmed


class PackageMapping(BaseModel):
    """Mapping between an imported module name and its PyPI distribution name."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    import_name: str = Field(
        ...,
        description="The imported module name (e.g., 'yaml', 'PIL', 'cv2')",
    )
    distribution_name: str = Field(
        ...,
        description="The canonical PyPI distribution name (e.g., 'PyYAML', 'pillow')",
    )
    mapping_source: MappingSource = Field(
        default=MappingSource.DIRECT,
        description="Mechanism used to deduce this mapping",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0",
    )

    @field_validator("import_name", "distribution_name")
    @classmethod
    def validate_names(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Name cannot be empty")
        return trimmed
