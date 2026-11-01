"""End-to-end integration tests for PyDeps resolution workflow."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from pydeps_intelligence.facade import PyDeps
from pydeps_intelligence.models.dependencies import ResolutionMode, ResolutionStatus
from pydeps_intelligence.models.project import Architecture, OperatingSystem, TargetEnvironment

MOCK_FLASK_UV_LOCK = """version = 1
requires-python = ">=3.9"

[[package]]
name = "flask"
version = "3.0.2"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "werkzeug" },
]

[[package]]
name = "werkzeug"
version = "3.0.1"
source = { registry = "https://pypi.org/simple" }
dependencies = []
"""


def test_e2e_flask_project(tmp_path: Path) -> None:
    """Test resolution on a simple Flask project structure."""
    src_dir = tmp_path / "src" / "my_flask_app"
    src_dir.mkdir(parents=True)
    (src_dir / "app.py").write_text("import flask\napp = flask.Flask(__name__)\n", encoding="utf-8")

    engine = PyDeps(project_path=tmp_path)

    with patch("pydeps_intelligence.resolver.uv_backend.UvBackend.find_uv", return_value="uv"):

        def mock_run(cmd, cwd=None, *args, **kwargs):
            mock = MagicMock()
            mock.returncode = 0
            if "export" in cmd:
                mock.stdout = "flask==3.0.2\nwerkzeug==3.0.1\n"
            else:
                # Create uv.lock in cwd
                if cwd:
                    (Path(cwd) / "uv.lock").write_text(MOCK_FLASK_UV_LOCK, encoding="utf-8")
                mock.stdout = "Resolved in 10ms"
            return mock

        with patch("subprocess.run", side_effect=mock_run):
            res = engine.resolve_dependencies(mode="universal")
            assert res.success is True
            assert res.status == ResolutionStatus.SUCCESS
            assert "flask" in [d.name for d in res.resolved_dependencies]
            assert "werkzeug" in [d.name for d in res.resolved_dependencies]


def test_e2e_test_only_imports(tmp_path: Path) -> None:
    """Test that test-only imports are excluded from runtime resolution by default."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("import requests\n", encoding="utf-8")

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_main.py").write_text("import pytest\n", encoding="utf-8")

    engine = PyDeps(project_path=tmp_path)

    with patch("pydeps_intelligence.resolver.uv_backend.UvBackend.find_uv", return_value="uv"):

        def mock_run(cmd, cwd=None, *args, **kwargs):
            mock = MagicMock()
            mock.returncode = 0
            if "export" in cmd:
                mock.stdout = "requests==2.31.0\n"
            else:
                if cwd:
                    lock_content = """version = 1
requires-python = ">=3.9"

[[package]]
name = "requests"
version = "2.31.0"
source = { registry = "https://pypi.org/simple" }
dependencies = []
"""
                    (Path(cwd) / "uv.lock").write_text(lock_content, encoding="utf-8")
                mock.stdout = "Resolved"
            return mock

        with patch("subprocess.run", side_effect=mock_run):
            # Default: include_dev=False
            res = engine.resolve_dependencies(include_dev=False)
            assert res.success is True
            resolved = [d.name for d in res.resolved_dependencies]
            assert "requests" in resolved
            assert "pytest" not in resolved


def test_e2e_conflicting_constraints(tmp_path: Path) -> None:
    """Test resolution diagnostic reporting when conflicting constraints are present."""
    (tmp_path / "requirements.txt").write_text(
        "urllib3 >= 2.0.0\nurllib3 < 1.26.0\n", encoding="utf-8"
    )
    (tmp_path / "app.py").write_text("import urllib3\n", encoding="utf-8")

    engine = PyDeps(project_path=tmp_path)

    with patch("pydeps_intelligence.resolver.uv_backend.UvBackend.find_uv", return_value="uv"):
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stderr = (
            "error: Failed to resolve requirements\n"
            "Because root depends on urllib3>=2.0.0 and urllib3<1.26.0,\n"
            "requirements cannot be used.\n"
        )
        mock_proc.stdout = ""

        with patch("subprocess.run", return_value=mock_proc):
            res = engine.resolve_dependencies()
            assert res.success is False
            assert res.status == ResolutionStatus.CONFLICT
            assert len(res.structured_conflicts) > 0


def test_e2e_per_target_windows_linux(tmp_path: Path) -> None:
    """Test resolving separately for Windows and Linux target environments."""
    (tmp_path / "app.py").write_text("import click\n", encoding="utf-8")

    target_win = TargetEnvironment(
        python_version="3.11",
        operating_system=OperatingSystem.WINDOWS,
        architecture=Architecture.X86_64,
    )
    target_linux = TargetEnvironment(
        python_version="3.11",
        operating_system=OperatingSystem.LINUX,
        architecture=Architecture.X86_64,
    )

    engine = PyDeps(project_path=tmp_path)

    with patch("pydeps_intelligence.resolver.uv_backend.UvBackend.find_uv", return_value="uv"):

        def mock_run(cmd, *args, **kwargs):
            # Inspect output path
            if "--output-file" in cmd:
                out_idx = cmd.index("--output-file") + 1
                out_file = Path(cmd[out_idx])
                if "windows" in cmd:
                    out_file.write_text("click==8.1.7\ncolorama==0.4.6\n", encoding="utf-8")
                else:
                    out_file.write_text("click==8.1.7\n", encoding="utf-8")
            mock = MagicMock()
            mock.returncode = 0
            return mock

        with patch("subprocess.run", side_effect=mock_run):
            res = engine.resolve_dependencies(
                mode=ResolutionMode.PER_TARGET,
                targets=[target_win, target_linux],
            )
            assert res.success is True
            assert len(res.per_target_results) == 2
            win_tag = target_win.platform_tag
            linux_tag = target_linux.platform_tag

            win_res = res.per_target_results[win_tag]
            linux_res = res.per_target_results[linux_tag]

            assert "colorama" in [d.name for d in win_res.resolved_dependencies]
            assert "colorama" not in [d.name for d in linux_res.resolved_dependencies]
