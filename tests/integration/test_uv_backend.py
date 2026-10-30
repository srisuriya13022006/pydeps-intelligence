"""Integration tests for UvBackend using mocked subprocess executions."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from pydeps.models.dependencies import (
    Dependency,
    DependencyType,
    ResolutionMode,
    ResolutionRequest,
    ResolutionStatus,
    ResolutionStrategy,
)
from pydeps.models.project import Architecture, OperatingSystem, TargetEnvironment
from pydeps.resolver.resolution_workspace import ResolutionWorkspace
from pydeps.resolver.uv_backend import UvBackend

MOCK_UV_LOCK_CONTENT = """version = 1
requires-python = ">=3.9"

[[package]]
name = "flask"
version = "3.0.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "werkzeug" },
    { name = "jinja2" },
]

[[package]]
name = "werkzeug"
version = "3.0.1"
source = { registry = "https://pypi.org/simple" }
dependencies = []

[[package]]
name = "jinja2"
version = "3.1.2"
source = { registry = "https://pypi.org/simple" }
dependencies = []
"""


def test_uv_backend_availability_and_version() -> None:
    """Test detecting uv binary and parsing version string."""
    backend = UvBackend(uv_path="/usr/bin/uv")

    with patch("shutil.which", return_value="/usr/bin/uv"):
        assert backend.is_available() is True

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "uv 0.4.18 (c123456 2024-10-01)\n"

        with patch("subprocess.run", return_value=mock_proc):
            ver = backend.get_version()
            assert ver == "0.4.18"


def test_uv_backend_unavailable() -> None:
    """Test resolution response when uv is not installed on PATH."""
    backend = UvBackend(uv_path="nonexistent_uv")

    with patch("shutil.which", return_value=None):
        req = ResolutionRequest(
            project_path=Path("."),
            direct_dependencies=[Dependency(name="flask")],
            mode=ResolutionMode.UNIVERSAL,
        )
        with ResolutionWorkspace() as ws:
            res = backend.resolve_universal(req, ws)
            assert res.success is False
            assert res.status == ResolutionStatus.FAILURE
            assert any("not installed" in c for c in res.conflicts)


def test_uv_backend_successful_universal_resolution(tmp_path: Path) -> None:
    """Test successful universal resolution with mocked uv lock and export."""
    backend = UvBackend()

    req = ResolutionRequest(
        project_path=tmp_path,
        direct_dependencies=[Dependency(name="flask", version_specifier=">=3.0.0")],
        mode=ResolutionMode.UNIVERSAL,
        strategy=ResolutionStrategy.LATEST_COMPATIBLE,
    )

    with patch.object(backend, "find_uv", return_value="uv"):
        with ResolutionWorkspace() as ws:
            # Pre-populate uv.lock in workspace as if uv ran
            (ws.path / "uv.lock").write_text(MOCK_UV_LOCK_CONTENT, encoding="utf-8")

            def mock_run_side_effect(cmd, *args, **kwargs):
                mock = MagicMock()
                mock.returncode = 0
                if "export" in cmd:
                    mock.stdout = "flask==3.0.0\nwerkzeug==3.0.1\njinja2==3.1.2\n"
                else:
                    mock.stdout = "Resolved 3 packages in 12ms\n"
                return mock

            with patch("subprocess.run", side_effect=mock_run_side_effect):
                res = backend.resolve_universal(req, ws)
                assert res.success is True
                assert res.status == ResolutionStatus.SUCCESS
                assert res.graph is not None
                assert "flask" in res.graph.packages
                assert "werkzeug" in res.graph.packages
                assert "jinja2" in res.graph.packages
                assert res.graph.packages["flask"].dependency_type == DependencyType.DIRECT
                assert res.graph.packages["werkzeug"].dependency_type == DependencyType.TRANSITIVE
                assert res.graph.direct_count == 1
                assert res.graph.transitive_count == 2
                assert res.requirements_txt is not None
                assert "flask==3.0.0" in res.requirements_txt


def test_uv_backend_successful_per_target_resolution(tmp_path: Path) -> None:
    """Test successful per-target resolution with mocked uv pip compile."""
    backend = UvBackend()
    target = TargetEnvironment(
        python_version="3.11",
        operating_system=OperatingSystem.WINDOWS,
        architecture=Architecture.X86_64,
    )

    req = ResolutionRequest(
        project_path=tmp_path,
        direct_dependencies=[Dependency(name="click", version_specifier=">=8.0.0")],
        mode=ResolutionMode.PER_TARGET,
        targets=[target],
    )

    with patch.object(backend, "find_uv", return_value="uv"):
        with ResolutionWorkspace() as ws:

            def mock_run_side_effect(cmd, *args, **kwargs):
                # Write requirements.txt to simulated output location
                out_idx = cmd.index("--output-file") + 1
                out_file = Path(cmd[out_idx])
                out_file.write_text(
                    "click==8.1.7\ncolorama==0.4.6; sys_platform == 'win32'\n",
                    encoding="utf-8",
                )
                mock = MagicMock()
                mock.returncode = 0
                return mock

            with patch("subprocess.run", side_effect=mock_run_side_effect):
                res = backend.resolve_per_target(req, target=target, workspace=ws)
                assert res.success is True
                assert res.status == ResolutionStatus.SUCCESS
                resolved_names = [d.name for d in res.resolved_dependencies]
                assert "click" in resolved_names
                assert "colorama" in resolved_names


def test_uv_backend_conflict_failure() -> None:
    """Test handling uv subprocess resolution conflict failure."""
    backend = UvBackend()
    req = ResolutionRequest(
        project_path=Path("."),
        direct_dependencies=[
            Dependency(name="pkg-a", version_specifier="==1.0.0"),
            Dependency(name="pkg-b", version_specifier="==2.0.0"),
        ],
        mode=ResolutionMode.UNIVERSAL,
    )

    with patch.object(backend, "find_uv", return_value="uv"):
        with ResolutionWorkspace() as ws:
            mock_proc = MagicMock()
            mock_proc.returncode = 1
            mock_proc.stderr = (
                "error: Failed to resolve requirements\n"
                "Because pkg-a==1.0.0 and pkg-b==2.0.0 require incompatible dependencies,\n"
                "requirements cannot be used.\n"
            )
            mock_proc.stdout = ""

            with patch("subprocess.run", return_value=mock_proc):
                res = backend.resolve_universal(req, ws)
                assert res.success is False
                assert res.status == ResolutionStatus.CONFLICT
                assert len(res.structured_conflicts) > 0


def test_uv_backend_timeout() -> None:
    """Test handling uv subprocess execution timeout."""
    backend = UvBackend()
    req = ResolutionRequest(
        project_path=Path("."),
        direct_dependencies=[Dependency(name="flask")],
        mode=ResolutionMode.UNIVERSAL,
    )

    with patch.object(backend, "find_uv", return_value="uv"):
        with ResolutionWorkspace() as ws:
            with patch(
                "subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd=["uv", "lock"], timeout=60),
            ):
                res = backend.resolve_universal(req, ws)
                assert res.success is False
                assert res.status == ResolutionStatus.FAILURE
                assert any("timed out" in c for c in res.conflicts)
