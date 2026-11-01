"""Unit tests for EnvironmentManager lifecycle and cleanup behavior."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from pydeps_intelligence.models.project import Architecture, OperatingSystem, TargetEnvironment
from pydeps_intelligence.models.validation import EnvironmentInfo
from pydeps_intelligence.validation.environment_manager import EnvironmentManager
from pydeps_intelligence.validation.runners.base import ExecutionRunner


def test_environment_manager_lifecycle(tmp_path: Path) -> None:
    """EnvironmentManager tracks disposable environments and cleans up upon exit."""
    mock_runner = MagicMock(spec=ExecutionRunner)
    mock_runner.can_execute.return_value = (True, None)

    env_path = tmp_path / "venv_test"
    env_path.mkdir(parents=True, exist_ok=True)

    dummy_info = EnvironmentInfo(
        environment_path=env_path,
        python_executable=env_path / "python",
        python_version="3.11.0",
        operating_system=OperatingSystem.WINDOWS,
        architecture=Architecture.X86_64,
        is_disposable=True,
    )
    mock_runner.create_environment.return_value = dummy_info
    mock_runner.cleanup_environment.return_value = True

    target = TargetEnvironment(
        python_version="3.11",
        operating_system=OperatingSystem.WINDOWS,
        architecture=Architecture.X86_64,
    )

    with EnvironmentManager(base_scratch_dir=tmp_path) as mgr:
        info = mgr.create_disposable_environment(mock_runner, target=target, keep=False)
        assert info.environment_path == env_path
        assert not info.is_cleaned_up

    # Assert cleanup was called upon context exit
    mock_runner.cleanup_environment.assert_called_once_with(dummy_info)


def test_environment_manager_keep_flag(tmp_path: Path) -> None:
    """EnvironmentManager preserves environments when keep=True."""
    mock_runner = MagicMock(spec=ExecutionRunner)
    mock_runner.can_execute.return_value = (True, None)

    env_path = tmp_path / "venv_kept"
    env_path.mkdir(parents=True, exist_ok=True)

    dummy_info = EnvironmentInfo(
        environment_path=env_path,
        python_executable=env_path / "python",
        python_version="3.11.0",
        operating_system=OperatingSystem.WINDOWS,
        architecture=Architecture.X86_64,
        is_disposable=False,
    )
    mock_runner.create_environment.return_value = dummy_info

    target = TargetEnvironment(
        python_version="3.11",
        operating_system=OperatingSystem.WINDOWS,
        architecture=Architecture.X86_64,
    )

    with EnvironmentManager(base_scratch_dir=tmp_path) as mgr:
        info = mgr.create_disposable_environment(mock_runner, target=target, keep=True)
        assert not info.is_disposable

    # Cleanup should NOT be called for non-disposable environments
    mock_runner.cleanup_environment.assert_not_called()
