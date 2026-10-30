"""Integration tests for PipBackend fallback resolver."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from pydeps.models.dependencies import (
    Dependency,
    ResolutionMode,
    ResolutionRequest,
    ResolutionStatus,
)
from pydeps.models.project import Architecture, OperatingSystem, TargetEnvironment
from pydeps.resolver.pip_backend import PipBackend
from pydeps.resolver.resolution_workspace import ResolutionWorkspace

MOCK_PIP_REPORT = {
    "version": "0",
    "install": [
        {
            "metadata": {
                "name": "flask",
                "version": "3.0.0",
            },
            "is_direct": True,
            "download_info": {},
        },
        {
            "metadata": {
                "name": "werkzeug",
                "version": "3.0.1",
            },
            "is_direct": False,
            "download_info": {},
        },
    ],
}


def test_pip_backend_rejects_universal_mode() -> None:
    """Test that PipBackend rejects universal resolution requests with informative diagnostic."""
    backend = PipBackend()
    req = ResolutionRequest(
        project_path=Path("."),
        direct_dependencies=[Dependency(name="flask")],
        mode=ResolutionMode.UNIVERSAL,
    )
    with ResolutionWorkspace() as ws:
        res = backend.resolve(req, ws)
        assert res.success is False
        assert "universal resolution" in res.conflicts[0]


def test_pip_backend_successful_resolution() -> None:
    """Test successful single-target pip resolution with mocked dry-run report."""
    backend = PipBackend()
    target = TargetEnvironment(
        python_version="3.11",
        operating_system=OperatingSystem.LINUX,
        architecture=Architecture.X86_64,
    )
    req = ResolutionRequest(
        project_path=Path("."),
        direct_dependencies=[Dependency(name="flask", version_specifier=">=3.0.0")],
        mode=ResolutionMode.PER_TARGET,
        targets=[target],
    )

    with ResolutionWorkspace() as ws:

        def mock_run_side_effect(cmd, *args, **kwargs):
            # Write pip_report.json
            rep_idx = cmd.index("--report") + 1
            rep_file = Path(cmd[rep_idx])
            rep_file.write_text(json.dumps(MOCK_PIP_REPORT), encoding="utf-8")
            mock = MagicMock()
            mock.returncode = 0
            return mock

        with patch("subprocess.run", side_effect=mock_run_side_effect):
            res = backend.resolve(req, ws, target=target)
            assert res.success is True
            assert res.status == ResolutionStatus.SUCCESS
            assert res.graph is not None
            assert "flask" in res.graph.packages
            assert "werkzeug" in res.graph.packages
            assert res.requirements_txt is not None
            assert "flask==3.0.0" in res.requirements_txt


def test_pip_backend_conflict_reporting() -> None:
    """Test pip resolution conflict error reporting."""
    backend = PipBackend()
    req = ResolutionRequest(
        project_path=Path("."),
        direct_dependencies=[Dependency(name="pkg-a"), Dependency(name="pkg-b")],
        mode=ResolutionMode.PER_TARGET,
    )

    with ResolutionWorkspace() as ws:
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stderr = (
            "ERROR: Cannot install pkg-a and pkg-b because of conflicting constraints.\n"
        )
        mock_proc.stdout = ""

        with patch("subprocess.run", return_value=mock_proc):
            res = backend.resolve(req, ws)
            assert res.success is False
            assert res.status == ResolutionStatus.CONFLICT
            assert len(res.structured_conflicts) > 0


def test_pip_backend_target_flags() -> None:
    """Test that foreign target flags are passed correctly to pip."""
    backend = PipBackend()
    target = TargetEnvironment(
        python_version="3.12",
        operating_system=OperatingSystem.WINDOWS,
        architecture=Architecture.ARM64,
    )
    req = ResolutionRequest(
        project_path=Path("."),
        direct_dependencies=[Dependency(name="click")],
        mode=ResolutionMode.PER_TARGET,
        targets=[target],
    )

    with ResolutionWorkspace() as ws:
        captured_cmd: list[str] = []

        def mock_run_side_effect(cmd, *args, **kwargs):
            nonlocal captured_cmd
            captured_cmd = list(cmd)
            rep_idx = cmd.index("--report") + 1
            rep_file = Path(cmd[rep_idx])
            rep_file.write_text(json.dumps(MOCK_PIP_REPORT), encoding="utf-8")
            mock = MagicMock()
            mock.returncode = 0
            return mock

        with patch("subprocess.run", side_effect=mock_run_side_effect):
            backend.resolve(req, ws, target=target)
            assert "--python-version" in captured_cmd
            assert "3.12" in captured_cmd
            assert "--platform" in captured_cmd
            assert "win_arm64" in captured_cmd
            assert "--only-binary=:all:" in captured_cmd
