"""Integration tests for LocalRunner with isolated subprocess execution."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from pydeps.models.project import Architecture, OperatingSystem
from pydeps.models.validation import EnvironmentInfo, ValidationStatus
from pydeps.validation.runners.local_runner import LocalRunner


def test_local_runner_smoke_import_success(tmp_path: Path) -> None:
    """Import smoke test returns PASSED for an available module."""
    runner = LocalRunner(allow_execution=True)

    dummy_env = EnvironmentInfo(
        environment_path=tmp_path,
        python_executable=Path("python"),  # System python can import sys
        python_version="3.11",
        operating_system=OperatingSystem.WINDOWS,
        architecture=Architecture.X86_64,
    )

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        res = runner.run_import_smoke_test(dummy_env, module_name="sys")
        assert res.status == ValidationStatus.PASSED
        assert res.exit_code == 0


def test_local_runner_smoke_import_module_not_found(tmp_path: Path) -> None:
    """Import smoke test returns FAILED and diagnostic=module_not_found when missing."""
    runner = LocalRunner(allow_execution=True)

    dummy_env = EnvironmentInfo(
        environment_path=tmp_path,
        python_executable=Path("python"),
        python_version="3.11",
        operating_system=OperatingSystem.WINDOWS,
        architecture=Architecture.X86_64,
    )

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="ModuleNotFoundError: No module named 'nonexistent_package_12345'",
        )
        res = runner.run_import_smoke_test(dummy_env, module_name="nonexistent_package_12345")
        assert res.status == ValidationStatus.FAILED
        assert res.exit_code == 1
        assert res.diagnostic == "module_not_found"


def test_local_runner_pip_check_failure(tmp_path: Path) -> None:
    """pip check failure is captured and reported."""
    runner = LocalRunner(allow_execution=True)

    dummy_env = EnvironmentInfo(
        environment_path=tmp_path,
        python_executable=Path("python"),
        python_version="3.11",
        operating_system=OperatingSystem.WINDOWS,
        architecture=Architecture.X86_64,
    )

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="flask 3.0.0 has requirement werkzeug>=3.0.0, but you have werkzeug 2.0.0.",
            stderr="",
        )
        code, log = runner.run_pip_check(dummy_env)
        assert code == 1
        assert "flask 3.0.0 has requirement werkzeug" in log
