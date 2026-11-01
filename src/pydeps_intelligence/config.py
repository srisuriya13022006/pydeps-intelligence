"""Configuration loading and validation for PyDeps."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from pydeps_intelligence.exceptions import ConfigError
from pydeps_intelligence.models.project import ProjectConfig

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]


def get_default_config(project_path: Path | str = ".") -> ProjectConfig:
    """Return default configuration for a project path."""
    return ProjectConfig(project_path=Path(project_path))


def load_config_from_dict(data: dict[str, Any], project_path: Path | str = ".") -> ProjectConfig:
    """Instantiate and validate ProjectConfig from a raw dictionary."""
    cfg_data = dict(data)
    if "project_path" not in cfg_data:
        cfg_data["project_path"] = Path(project_path)
    try:
        return ProjectConfig(**cfg_data)
    except ValidationError as exc:
        raise ConfigError(f"Invalid PyDeps configuration: {exc}") from exc


def load_config_from_file(file_path: Path | str) -> ProjectConfig:
    """Load configuration from a TOML or JSON file.

    Supports standalone pydeps configuration files or pyproject.toml [tool.pydeps] tables.
    """
    path = Path(file_path)
    if not path.is_file():
        raise ConfigError(f"Configuration file not found: {path}")

    try:
        if path.suffix.lower() == ".json":
            with path.open("r", encoding="utf-8") as f:
                raw_data = json.load(f)
        elif path.suffix.lower() == ".toml":
            if tomllib is None:
                raise ConfigError(
                    "TOML parser unavailable. On Python 3.10, ensure 'tomli' is installed."
                )
            with path.open("rb") as f:
                raw_data = tomllib.load(f)
        else:
            msg = f"Unsupported configuration file format '{path.suffix}'. Use .toml or .json."
            raise ConfigError(msg)
    except Exception as exc:
        if isinstance(exc, ConfigError):
            raise
        raise ConfigError(f"Failed to parse configuration file {path}: {exc}") from exc

    # If loading pyproject.toml, look inside [tool.pydeps_intelligence] or fallback to [tool.pydeps]
    if path.name == "pyproject.toml":
        tool_table = raw_data.get("tool", {})
        raw_data = tool_table.get("pydeps_intelligence", tool_table.get("pydeps", {}))

    project_root = path.parent
    return load_config_from_dict(raw_data, project_path=project_root)


def resolve_project_config(
    project_path: Path | str = ".",
    config_file: Path | str | None = None,
) -> ProjectConfig:
    """Resolve project configuration from an explicit file, standard files, or defaults."""
    target_path = Path(project_path)

    if config_file is not None:
        return load_config_from_file(config_file)

    # Search for standard config files in project root
    for candidate_name in (
        "pydeps-intel.toml",
        "pydeps_intelligence.toml",
        "pydeps.toml",
        "pyproject.toml",
        "pydeps-intel.json",
        "pydeps_intelligence.json",
        "pydeps.json",
    ):
        candidate = target_path / candidate_name
        if candidate.is_file():
            try:
                cfg = load_config_from_file(candidate)
                # If pyproject.toml had no [tool.pydeps], fallback to default with project_path
                return cfg
            except ConfigError:
                # If pyproject.toml doesn't have [tool.pydeps], we can still fall back to default
                if candidate_name == "pyproject.toml":
                    continue
                raise

    return get_default_config(target_path)
