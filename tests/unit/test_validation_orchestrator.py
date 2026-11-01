"""Unit tests for ValidationOrchestrator policies, stages, and reports."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

from pydeps_intelligence.models.dependencies import (
    ResolutionMode,
    ResolutionResult,
    ResolutionStatus,
    ResolutionStrategy,
    ResolvedDependencyGraph,
    ResolvedPackage,
)
from pydeps_intelligence.models.project import Architecture, OperatingSystem, TargetEnvironment
from pydeps_intelligence.models.validation import (
    EnvironmentInfo,
    ExecutionPolicy,
    ValidationRequest,
    ValidationStatus,
)
from pydeps_intelligence.validation.runners.base import ExecutionRunner
from pydeps_intelligence.validation.runners.local_runner import LocalRunner
from pydeps_intelligence.validation.validation_orchestrator import ValidationOrchestrator


def test_orchestrator_blocks_local_execution_without_authorization(tmp_path: Path) -> None:
    """Orchestrator must block local execution with BLOCKED_BY_POLICY when untrusted."""
    target = TargetEnvironment(
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
        operating_system=LocalRunner._detect_host_os(),
        architecture=LocalRunner._detect_host_arch(),
    )
    request = ValidationRequest(
        project_path=tmp_path,
        target_environment=target,
        runner_type="local",
        execution_policy=ExecutionPolicy.STATIC_ONLY,
        allow_local_execution=False,
    )

    orchestrator = ValidationOrchestrator(scratch_dir=tmp_path)
    report = orchestrator.validate(request)

    assert report.status == ValidationStatus.BLOCKED_BY_POLICY
    assert any("STATIC_ONLY" in d for d in report.diagnostics)
    assert report.cleanup_status == "not_created"


def test_orchestrator_dry_run_simulation(tmp_path: Path) -> None:
    """Dry run produces a planned execution structure without running commands."""
    target = TargetEnvironment(
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
        operating_system=LocalRunner._detect_host_os(),
        architecture=LocalRunner._detect_host_arch(),
    )
    request = ValidationRequest(
        project_path=tmp_path,
        target_environment=target,
        runner_type="local",
        level="imports",
        dry_run=True,
    )

    graph = ResolvedDependencyGraph(
        roots=["requests"],
        packages={"requests": ResolvedPackage(name="requests", version="2.31.0")},
    )
    resolution = ResolutionResult(
        success=True,
        mode=ResolutionMode.UNIVERSAL,
        strategy=ResolutionStrategy.LATEST_COMPATIBLE,
        status=ResolutionStatus.SUCCESS,
        graph=graph,
    )

    orchestrator = ValidationOrchestrator(scratch_dir=tmp_path)
    report = orchestrator.validate(request, resolution_result=resolution)

    assert report.status == ValidationStatus.PASSED
    assert report.dry_run_plan is not None
    assert "requests==2.31.0" in report.dry_run_plan["packages_to_install"]
    assert report.dry_run_plan["import_smoke_tests_enabled"] is True


def test_orchestrator_project_tests_require_separate_authorization(tmp_path: Path) -> None:
    """L3 Project tests require allow_project_code=True, even if local execution is allowed."""
    target = TargetEnvironment(
        python_version="3.11",
        operating_system=OperatingSystem.WINDOWS,
        architecture=Architecture.X86_64,
    )
    request = ValidationRequest(
        project_path=tmp_path,
        target_environment=target,
        runner_type="local",
        level="project-tests",
        allow_local_execution=True,
        allow_project_code=False,  # NOT authorized
    )

    orchestrator = ValidationOrchestrator(scratch_dir=tmp_path)

    # Mock runner
    mock_runner = MagicMock(spec=ExecutionRunner)
    mock_runner.can_execute.return_value = (True, None)
    mock_runner.get_capabilities.return_value.isolation_level = "host_venv"

    env_dir = tmp_path / "venv_mock"
    env_dir.mkdir(parents=True, exist_ok=True)
    env_info = EnvironmentInfo(
        environment_path=env_dir,
        python_executable=env_dir / "python",
        python_version="3.11.0",
        operating_system=OperatingSystem.WINDOWS,
        architecture=Architecture.X86_64,
    )
    mock_runner.create_environment.return_value = env_info
    mock_runner.install_dependencies.return_value = (0, "Installed ok", {"requests": "2.31.0"})
    mock_runner.run_pip_check.return_value = (0, "pip check passed")
    mock_runner.cleanup_environment.return_value = True

    orchestrator._select_runner = MagicMock(return_value=mock_runner)

    report = orchestrator.validate(request)
    assert "project_test" in report.stages
    assert report.stages["project_test"].status == ValidationStatus.BLOCKED_BY_POLICY
    assert any("explicit authorization" in err for err in report.stages["project_test"].errors)
