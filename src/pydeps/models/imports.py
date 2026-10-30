"""Models for Python source imports and package distribution mappings."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ImportType(str, Enum):
    """Categorization of an extracted import statement."""

    STANDARD_LIBRARY = "standard_library"
    THIRD_PARTY = "third_party"
    FIRST_PARTY = "first_party"
    CONDITIONAL = "conditional"
    TYPE_CHECKING = "type_checking"
    UNKNOWN = "unknown"


class ImportContext(str, Enum):
    """Syntactic or runtime context where the import was discovered."""

    TOP_LEVEL = "top_level"
    FUNCTION = "function"
    CLASS = "class"
    CONDITIONAL = "conditional"
    TYPE_CHECKING = "type_checking"
    TRY_EXCEPT = "try_except"


class MappingSource(str, Enum):
    """Source or method used to resolve an import name to a PyPI distribution name."""

    DIRECT = "direct"
    STDLIB = "stdlib"
    KNOWN_MAPPING = "known_mapping"
    METADATA = "metadata"
    HEURISTIC = "heuristic"
    OVERRIDE = "override"


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
    top_level_package: str | None = Field(
        default=None,
        description="Extracted top-level package or root module name",
    )
    import_context: ImportContext = Field(
        default=ImportContext.TOP_LEVEL,
        description="Context in which the import statement appeared",
    )
    is_dynamic: bool = Field(
        default=False,
        description="Whether this import was invoked dynamically (__import__, importlib)",
    )
    diagnostic: str | None = Field(
        default=None,
        description="Diagnostic explanation (e.g. for dynamic or unresolvable imports)",
    )

    @field_validator("module_name")
    @classmethod
    def validate_module_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("module_name must not be empty")
        return trimmed

    @model_validator(mode="before")
    @classmethod
    def pre_populate_top_level(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("top_level_package"):
                mod = data.get("module_name", "")
                if isinstance(mod, str) and mod:
                    clean = mod.lstrip(".")
                    if clean:
                        data = dict(data)
                        data["top_level_package"] = clean.split(".")[0]
        return data


class PackageMapping(BaseModel):
    """Mapping between an imported module name and its PyPI distribution name."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    import_name: str = Field(
        ...,
        description="The imported module name (e.g., 'yaml', 'PIL')",
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
