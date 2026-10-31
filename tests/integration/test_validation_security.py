"""Security regression tests verifying P5 isolation, trust policies, and credential protection."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from pydeps.models.project import Architecture, OperatingSystem, TargetEnvironment
from pydeps.models.validation import (
    EnvironmentInfo,
    ExecutionPolicy,
    NetworkPolicy,
    ValidationRequest,
    ValidationStatus,
)
from pydeps.validation.network_policy import NetworkPolicyController
from pydeps.validation.runners.docker_runner import DockerRunner
from pydeps.validation.runners.local_runner import LocalRunner
from pydeps.validation.validation_orchestrator import ValidationOrchestrator


def test_security_no_execution_without_explicit_authorization(tmp_path: Path) -> None:
    """Security rule: LocalRunner must never execute when allow_execution=False."""
    request = ValidationRequest(
        project_path=tmp_path,
        target_environment=TargetEnvironment(
            python_version="3.11",
            operating_system=OperatingSystem.WINDOWS,
            architecture=Architecture.X86_64,
        ),
        runner_type="local",
        execution_policy=ExecutionPolicy.STATIC_ONLY,
        allow_local_execution=False,
    )
    orchestrator = ValidationOrchestrator(scratch_dir=tmp_path)
    report = orchestrator.validate(request)
    assert report.status == ValidationStatus.BLOCKED_BY_POLICY
    assert report.cleanup_status == "not_created"


def test_security_no_project_tests_without_separate_authorization(tmp_path: Path) -> None:
    """Security rule: Project tests (L3) require separate allow_project_code=True."""
    request = ValidationRequest(
        project_path=tmp_path,
        target_environment=TargetEnvironment(
            python_version="3.11",
            operating_system=OperatingSystem.WINDOWS,
            architecture=Architecture.X86_64,
        ),
        runner_type="local",
        level="project-tests",
        allow_local_execution=True,
        allow_project_code=False,  # Denied!
    )
    orchestrator = ValidationOrchestrator(scratch_dir=tmp_path)

    # Mock runner
    runner = LocalRunner(allow_execution=True)
    runner.can_execute = MagicMock(return_value=(True, None))
    dummy_env = EnvironmentInfo(
        environment_path=tmp_path / "venv",
        python_executable=tmp_path / "venv" / "python",
        python_version="3.11",
        operating_system=OperatingSystem.WINDOWS,
        architecture=Architecture.X86_64,
    )
    runner.create_environment = MagicMock(return_value=dummy_env)
    runner.install_dependencies = MagicMock(return_value=(0, "ok", {}))
    runner.run_pip_check = MagicMock(return_value=(0, "ok"))
    runner.cleanup_environment = MagicMock(return_value=True)

    orchestrator._select_runner = MagicMock(return_value=runner)
    report = orchestrator.validate(request)

    assert "project_test" in report.stages
    assert report.stages["project_test"].status == ValidationStatus.BLOCKED_BY_POLICY


def test_security_no_host_secret_leakage(monkeypatch) -> None:
    """Security rule: Process environments must filter out host cloud and registry tokens."""
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "sensitive_aws_secret")
    monkeypatch.setenv("PYPI_API_TOKEN", "pypi-AgEIBAAAsecret123456789012345678901234567890")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_secrettoken1234567890abcdef1234567890")

    clean_env = NetworkPolicyController.get_safe_environment()
    assert "AWS_SECRET_ACCESS_KEY" not in clean_env
    assert "PYPI_API_TOKEN" not in clean_env
    assert "GITHUB_TOKEN" not in clean_env


def test_security_docker_hardened_controls(tmp_path: Path) -> None:
    """Security rule: Docker container execution must be hardened and read-only."""
    runner = DockerRunner(memory_limit="1g", cpu_limit="1.0", pids_limit=100)
    target = TargetEnvironment(
        python_version="3.11",
        operating_system=OperatingSystem.LINUX,
        architecture=Architecture.X86_64,
    )

    args = runner._build_hardened_run_args(
        target=target,
        network=NetworkPolicy.DISABLED,
        project_path=tmp_path,
        env_dir=tmp_path / "env",
    )

    args_str = " ".join(args)

    # 1. Read-only project mount
    assert ":ro" in args_str
    # 2. Dropped capabilities
    assert "--cap-drop=ALL" in args
    # 3. No new privileges
    assert "--security-opt=no-new-privileges" in args
    # 4. No Docker socket mount
    assert "/var/run/docker.sock" not in args_str
    # 5. No privileged mode
    assert "--privileged" not in args
    # 6. Network disabled
    assert "--network none" in args_str


def test_security_wheel_only_default_prevents_host_sdist_builds(tmp_path: Path) -> None:
    """Security rule: Package installation defaults to wheel-only to prevent
    executing untrusted build backends.
    """
    runner = LocalRunner(allow_execution=True)
    dummy_env = EnvironmentInfo(
        environment_path=tmp_path,
        python_executable=Path("python"),
        python_version="3.11",
        operating_system=OperatingSystem.WINDOWS,
        architecture=Architecture.X86_64,
    )

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Success", stderr="")
        runner.install_dependencies(
            dummy_env,
            packages=["requests==2.31.0"],
            allow_sdist=False,  # Default
        )
        # First call is pip install, second call is pip list
        first_call_cmd = mock_run.call_args_list[0][0][0]
        assert "--only-binary=:all:" in first_call_cmd
