"""Unit tests for PyDeps domain data models."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from pydeps_intelligence.models.compatibility import CompatibilityResult, CompatibilityStatus
from pydeps_intelligence.models.dependencies import Dependency, DependencyType, ResolutionResult
from pydeps_intelligence.models.imports import (
    ImportRecord,
    ImportType,
    MappingSource,
    PackageMapping,
)
from pydeps_intelligence.models.project import (
    Architecture,
    OperatingSystem,
    PythonImplementation,
    TargetEnvironment,
)
from pydeps_intelligence.models.report import AnalysisReport, ProjectInformation
from pydeps_intelligence.models.validation import ValidationResult, ValidationStatus

# =========================================================================
# TargetEnvironment tests
# =========================================================================


def test_valid_target_environment() -> None:
    """Test creating valid TargetEnvironment instances across platforms."""
    env_linux = TargetEnvironment(
        python_version="3.11",
        operating_system=OperatingSystem.LINUX,
        architecture=Architecture.X86_64,
        implementation=PythonImplementation.CPYTHON,
    )
    assert env_linux.python_version == "3.11"
    assert env_linux.operating_system == OperatingSystem.LINUX
    assert env_linux.architecture == Architecture.X86_64
    assert env_linux.platform_tag == "linux-x86_64-cpython-py3.11"

    # Verify cross-platform target independence (macOS arm64, PyPy on any host)
    env_mac = TargetEnvironment(
        python_version="3.10.12",
        operating_system=OperatingSystem.MACOS,
        architecture=Architecture.ARM64,
        implementation=PythonImplementation.PYPY,
    )
    assert env_mac.operating_system == OperatingSystem.MACOS
    assert env_mac.architecture == Architecture.ARM64
    assert env_mac.implementation == PythonImplementation.PYPY


def test_target_environment_aliases() -> None:
    """Test OS and architecture aliases normalization."""
    env = TargetEnvironment(
        python_version="3.12",
        operating_system="darwin",  # type: ignore[arg-type]
        architecture="amd64",  # type: ignore[arg-type]
    )
    assert env.operating_system == OperatingSystem.MACOS
    assert env.architecture == Architecture.X86_64

    env_win = TargetEnvironment(
        python_version="3.9",
        operating_system="win32",  # type: ignore[arg-type]
        architecture="x64",  # type: ignore[arg-type]
    )
    assert env_win.operating_system == OperatingSystem.WINDOWS
    assert env_win.architecture == Architecture.X86_64


def test_invalid_target_environment_python_version() -> None:
    """Test that invalid python version strings are rejected."""
    with pytest.raises(ValidationError):
        TargetEnvironment(
            python_version="",
            operating_system=OperatingSystem.LINUX,
            architecture=Architecture.X86_64,
        )

    with pytest.raises(ValidationError):
        TargetEnvironment(
            python_version="not-a-version",
            operating_system=OperatingSystem.LINUX,
            architecture=Architecture.X86_64,
        )

    with pytest.raises(ValidationError):
        TargetEnvironment(
            python_version="99.0",  # Unsupported major version
            operating_system=OperatingSystem.LINUX,
            architecture=Architecture.X86_64,
        )


def test_invalid_operating_system() -> None:
    """Test rejection of unsupported operating system values."""
    with pytest.raises(ValidationError):
        TargetEnvironment(
            python_version="3.11",
            operating_system="solaris",  # type: ignore[arg-type]
            architecture=Architecture.X86_64,
        )


def test_invalid_architecture() -> None:
    """Test rejection of unsupported hardware architecture values."""
    with pytest.raises(ValidationError):
        TargetEnvironment(
            python_version="3.11",
            operating_system=OperatingSystem.LINUX,
            architecture="sparc",  # type: ignore[arg-type]
        )


# =========================================================================
# ImportRecord & PackageMapping tests
# =========================================================================


def test_valid_import_record() -> None:
    """Test creation and constraints of ImportRecord."""
    rec = ImportRecord(
        module_name="requests.auth",
        source_file=Path("src/app/client.py"),
        line_number=12,
        import_type=ImportType.THIRD_PARTY,
        confidence=0.95,
    )
    assert rec.module_name == "requests.auth"
    assert rec.line_number == 12
    assert rec.import_type == ImportType.THIRD_PARTY
    assert rec.confidence == 0.95


def test_invalid_import_record() -> None:
    """Test invalid field constraints on ImportRecord."""
    with pytest.raises(ValidationError):
        ImportRecord(
            module_name="",  # empty
            source_file=Path("app.py"),
            line_number=1,
        )

    with pytest.raises(ValidationError):
        ImportRecord(
            module_name="os",
            source_file=Path("app.py"),
            line_number=0,  # invalid line number < 1
        )

    with pytest.raises(ValidationError):
        ImportRecord(
            module_name="os",
            source_file=Path("app.py"),
            line_number=1,
            confidence=1.5,  # > 1.0
        )


def test_package_mapping() -> None:
    """Test PackageMapping model."""
    mapping = PackageMapping(
        import_name="yaml",
        distribution_name="PyYAML",
        mapping_source=MappingSource.KNOWN_MAPPING,
        confidence=1.0,
    )
    assert mapping.import_name == "yaml"
    assert mapping.distribution_name == "PyYAML"
    assert mapping.mapping_source == MappingSource.KNOWN_MAPPING


# =========================================================================
# Dependency & ResolutionResult tests
# =========================================================================


def test_dependency_normalization_and_pep508() -> None:
    """Test Dependency canonical name normalization and PEP 508 rendering."""
    dep = Dependency(
        name="Pydantic_Core",
        version_specifier=">= 2.14.0, < 3.0",
        extras={"fast", "zoneinfo"},
        environment_marker="python_version >= '3.10'",
        dependency_type=DependencyType.DIRECT,
    )
    # Canonical name per PEP 503/PEP 508 should be lower-cased with hyphens
    assert dep.name == "pydantic-core"
    expected = "pydantic-core[fast,zoneinfo] >= 2.14.0, < 3.0; python_version >= '3.10'"
    assert dep.to_pep508() == expected


def test_invalid_dependency_specifiers() -> None:
    """Test rejection of malformed version specifiers and markers."""
    with pytest.raises(ValidationError):
        Dependency(name="pytest", version_specifier="invalid==specifier!")

    with pytest.raises(ValidationError):
        Dependency(name="pytest", environment_marker="not a valid marker ???")


def test_resolution_result() -> None:
    """Test ResolutionResult model."""
    dep = Dependency(name="click", version_specifier="==8.1.7")
    res = ResolutionResult(
        success=True,
        resolved_dependencies=[dep],
        conflicts=[],
        unresolved_dependencies=[],
    )
    assert res.success is True
    assert len(res.resolved_dependencies) == 1
    assert res.resolved_dependencies[0].name == "click"


# =========================================================================
# CompatibilityResult & Tri-State tests
# =========================================================================


def test_compatibility_result_tri_state() -> None:
    """Test tri-state compatibility status (compatible, incompatible, unverified)."""
    env = TargetEnvironment(
        python_version="3.11",
        operating_system=OperatingSystem.LINUX,
        architecture=Architecture.X86_64,
    )

    comp = CompatibilityResult(
        package_name="numpy",
        package_version="1.26.0",
        target_environment=env,
        status=CompatibilityStatus.COMPATIBLE,
        reason="Matching CPython 3.11 manylinux wheel found",
        evidence=["numpy-1.26.0-cp311-cp311-manylinux_2_17_x86_64.whl"],
    )
    assert comp.status == CompatibilityStatus.COMPATIBLE
    assert comp.package_name == "numpy"

    incomp = CompatibilityResult(
        package_name="old-pkg",
        target_environment=env,
        status=CompatibilityStatus.INCOMPATIBLE,
        reason="Requires python < 3.0",
        evidence=["python_requires = '<3.0'"],
    )
    assert incomp.status == CompatibilityStatus.INCOMPATIBLE

    unver = CompatibilityResult(
        package_name="sdist-only-pkg",
        target_environment=env,
        status=CompatibilityStatus.UNVERIFIED,
        reason="Only sdist available without pre-built binary wheels",
    )
    assert unver.status == CompatibilityStatus.UNVERIFIED


# =========================================================================
# ValidationResult tests
# =========================================================================


def test_validation_result() -> None:
    """Test ValidationResult states and errors."""
    env = TargetEnvironment(
        python_version="3.12",
        operating_system=OperatingSystem.WINDOWS,
        architecture=Architecture.X86_64,
    )
    val = ValidationResult(
        target_environment=env,
        installation_status=ValidationStatus.SUCCESS,
        import_test_status=ValidationStatus.FAILED,
        test_status=ValidationStatus.SKIPPED,
        errors=["ImportError: DLL load failed while importing _custom_c_module"],
    )
    assert val.installation_status == ValidationStatus.SUCCESS
    assert val.import_test_status == ValidationStatus.FAILED
    assert len(val.errors) == 1


# =========================================================================
# AnalysisReport serialization & deserialization tests
# =========================================================================


def test_analysis_report_serialization_roundtrip() -> None:
    """Test full serialization and deserialization of AnalysisReport."""
    env = TargetEnvironment(
        python_version="3.11",
        operating_system=OperatingSystem.LINUX,
        architecture=Architecture.X86_64,
    )

    report = AnalysisReport(
        project_information=ProjectInformation(
            project_name="sample-project",
            project_path=Path("/tmp/sample"),
        ),
        discovered_imports=[
            ImportRecord(
                module_name="httpx",
                source_file=Path("/tmp/sample/main.py"),
                line_number=1,
                import_type=ImportType.THIRD_PARTY,
            )
        ],
        mapped_dependencies=[
            PackageMapping(
                import_name="httpx",
                distribution_name="httpx",
                mapping_source=MappingSource.DIRECT,
            )
        ],
        compatibility_results=[
            CompatibilityResult(
                package_name="httpx",
                package_version="0.25.0",
                target_environment=env,
                status=CompatibilityStatus.COMPATIBLE,
                reason="Universal wheel compatible with Python 3.11",
            )
        ],
        resolution_results=ResolutionResult(
            success=True,
            resolved_dependencies=[Dependency(name="httpx", version_specifier="==0.25.0")],
        ),
        validation_results=[
            ValidationResult(
                target_environment=env,
                installation_status=ValidationStatus.SUCCESS,
                import_test_status=ValidationStatus.SUCCESS,
                test_status=ValidationStatus.SUCCESS,
            )
        ],
        warnings=["Non-critical warning"],
    )

    # Dump to JSON and reload
    json_data = report.model_dump_json()
    reloaded = AnalysisReport.model_validate_json(json_data)

    assert reloaded.project_information.project_name == "sample-project"
    assert len(reloaded.discovered_imports) == 1
    assert reloaded.discovered_imports[0].module_name == "httpx"
    assert len(reloaded.mapped_dependencies) == 1
    assert len(reloaded.compatibility_results) == 1
    assert reloaded.compatibility_results[0].status == CompatibilityStatus.COMPATIBLE
    assert reloaded.resolution_results is not None
    assert reloaded.resolution_results.success is True
    assert len(reloaded.validation_results) == 1
    assert reloaded.warnings == ["Non-critical warning"]
