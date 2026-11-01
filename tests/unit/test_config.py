"""Unit tests for configuration loading and validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from pydeps_intelligence.config import (
    get_default_config,
    load_config_from_dict,
    load_config_from_file,
    resolve_project_config,
)
from pydeps_intelligence.exceptions import ConfigError
from pydeps_intelligence.models.project import (
    Architecture,
    OperatingSystem,
    ProjectConfig,
    PythonImplementation,
)


def test_default_config() -> None:
    """Test default ProjectConfig values."""
    config = get_default_config()
    assert config.project_path == Path(".")
    assert "3.11" in config.target_python_versions
    assert OperatingSystem.LINUX in config.target_operating_systems
    assert OperatingSystem.WINDOWS in config.target_operating_systems
    assert OperatingSystem.MACOS in config.target_operating_systems
    assert Architecture.X86_64 in config.target_architectures
    assert PythonImplementation.CPYTHON in config.target_implementations
    assert config.validate_runtime is False
    assert config.output_directory == Path(".pydeps")
    assert ".git" in config.excluded_directories
    assert ".venv" in config.excluded_directories


def test_custom_project_path() -> None:
    """Test default config with custom path."""
    custom_path = Path("/my/test/project")
    config = get_default_config(custom_path)
    assert config.project_path == custom_path


def test_load_config_from_valid_dict() -> None:
    """Test loading configuration from a dictionary."""
    data = {
        "target_python_versions": ["3.9", "3.10", "3.11"],
        "target_operating_systems": ["linux", "windows"],
        "target_architectures": ["x86_64", "arm64"],
        "target_implementations": ["cpython"],
        "validate_runtime": True,
        "output_directory": "custom_output",
        "excluded_directories": ["custom_dir"],
    }
    config = load_config_from_dict(data)
    assert config.target_python_versions == ["3.9", "3.10", "3.11"]
    assert config.target_operating_systems == [OperatingSystem.LINUX, OperatingSystem.WINDOWS]
    assert config.target_architectures == [Architecture.X86_64, Architecture.ARM64]
    assert config.validate_runtime is True
    assert config.output_directory == Path("custom_output")
    assert config.excluded_directories == ["custom_dir"]


def test_invalid_target_python_version_in_config() -> None:
    """Test validation failure on invalid Python version string."""
    with pytest.raises(ConfigError) as exc_info:
        load_config_from_dict({"target_python_versions": ["invalid-version"]})
    assert "Invalid target Python version" in str(exc_info.value)


def test_empty_target_python_versions_in_config() -> None:
    """Test validation failure when python version list is empty."""
    with pytest.raises(ConfigError) as exc_info:
        load_config_from_dict({"target_python_versions": []})
    assert "target_python_versions must contain at least one version" in str(exc_info.value)


def test_empty_target_os_in_config() -> None:
    """Test validation failure when operating system list is empty."""
    with pytest.raises(ValidationError):
        ProjectConfig(target_operating_systems=[])


def test_empty_target_architectures_in_config() -> None:
    """Test validation failure when architecture list is empty."""
    with pytest.raises(ValidationError):
        ProjectConfig(target_architectures=[])


def test_load_config_from_json_file(tmp_path: Path) -> None:
    """Test loading configuration from a JSON file."""
    config_file = tmp_path / "pydeps_intelligence.json"
    data = {
        "target_python_versions": ["3.11", "3.12"],
        "target_operating_systems": ["linux"],
        "validate_runtime": True,
    }
    config_file.write_text(json.dumps(data), encoding="utf-8")

    config = load_config_from_file(config_file)
    assert config.target_python_versions == ["3.11", "3.12"]
    assert config.target_operating_systems == [OperatingSystem.LINUX]
    assert config.validate_runtime is True
    assert config.project_path == tmp_path


def test_load_config_from_pyproject_toml(tmp_path: Path) -> None:
    """Test loading configuration from pyproject.toml [tool.pydeps]."""
    pyproject_file = tmp_path / "pyproject.toml"
    content = """
    [tool.pydeps]
    target_python_versions = ["3.10", "3.12"]
    validate_runtime = true
    output_directory = "reports"
    """
    pyproject_file.write_text(content, encoding="utf-8")

    config = load_config_from_file(pyproject_file)
    assert config.target_python_versions == ["3.10", "3.12"]
    assert config.validate_runtime is True
    assert config.output_directory == Path("reports")
    assert config.project_path == tmp_path


def test_load_config_file_not_found() -> None:
    """Test error when configuration file does not exist."""
    with pytest.raises(ConfigError) as exc_info:
        load_config_from_file(Path("non_existent_config.toml"))
    assert "Configuration file not found" in str(exc_info.value)


def test_load_config_unsupported_format(tmp_path: Path) -> None:
    """Test error when configuration file format is unsupported."""
    bad_file = tmp_path / "config.yaml"
    bad_file.write_text("target_python_versions: [3.10]", encoding="utf-8")

    with pytest.raises(ConfigError) as exc_info:
        load_config_from_file(bad_file)
    assert "Unsupported configuration file format" in str(exc_info.value)


def test_resolve_project_config_defaults(tmp_path: Path) -> None:
    """Test resolve_project_config when no config file exists."""
    config = resolve_project_config(project_path=tmp_path)
    assert config.project_path == tmp_path
    assert "3.11" in config.target_python_versions


def test_resolve_project_config_with_pydeps_toml(tmp_path: Path) -> None:
    """Test resolve_project_config auto-discovering pydeps.toml."""
    config_file = tmp_path / "pydeps_intelligence.toml"
    config_file.write_text('target_python_versions = ["3.12"]\n', encoding="utf-8")

    config = resolve_project_config(project_path=tmp_path)
    assert config.target_python_versions == ["3.12"]
    assert config.project_path == tmp_path
