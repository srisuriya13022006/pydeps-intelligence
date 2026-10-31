"""Integration tests for DockerRunner security controls and container execution."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from pydeps.models.project import Architecture, OperatingSystem, TargetEnvironment
from pydeps.models.validation import NetworkPolicy
from pydeps.validation.runners.docker_runner import DockerRunner


def test_docker_runner_hardened_run_arguments(tmp_path: Path) -> None:
    """Docker command must include strict container hardening flags."""
    runner = DockerRunner(
        memory_limit="512m",
        cpu_limit="0.5",
        pids_limit=50,
    )

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

    # 1. No new privileges
    assert "--security-opt=no-new-privileges" in args
    # 2. Drop all capabilities
    assert "--cap-drop=ALL" in args
    # 3. PIDs limit
    assert "--pids-limit" in args
    assert "50" in args
    # 4. Memory limit
    assert "--memory" in args
    assert "512m" in args
    # 5. CPU limit
    assert "--cpus" in args
    assert "0.5" in args
    # 6. Isolated tmpfs
    assert "--tmpfs" in args
    assert "/tmp:rw,noexec,nosuid,size=512m" in args
    # 7. Network disabled
    assert "--network" in args
    assert "none" in args
    # 8. Read-only source mount
    clean_path = str(tmp_path.resolve()).replace("\\", "/")
    assert f"{clean_path}:/workspace:ro" in " ".join(args)
    # 9. Never mount docker socket or host root
    assert "/var/run/docker.sock" not in " ".join(args)
    # 10. No privileged flag
    assert "--privileged" not in args


def test_docker_runner_missing_executable() -> None:
    """When docker is not installed, runner reports is_available=False."""
    runner = DockerRunner(docker_executable="nonexistent_docker_bin_xyz")
    with patch("shutil.which", return_value=None):
        avail, reason = runner.is_docker_available()
        assert not avail
        assert "not found on PATH" in (reason or "")


def test_docker_runner_daemon_failure() -> None:
    """When docker daemon is not responding, runner reports clear error."""
    runner = DockerRunner()
    with patch("shutil.which", return_value="/usr/bin/docker"), patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1, stderr="Cannot connect to the Docker daemon", stdout=""
        )
        avail, reason = runner.is_docker_available()
        assert not avail
        assert "daemon is not responding" in (reason or "")
