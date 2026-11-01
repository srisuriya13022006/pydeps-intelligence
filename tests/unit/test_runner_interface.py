"""Unit tests for ExecutionRunner protocols, capabilities, and target rejection."""

from __future__ import annotations

import platform

from pydeps_intelligence.models.project import (
    Architecture,
    OperatingSystem,
    TargetEnvironment,
)
from pydeps_intelligence.validation.interpreter_discovery import (
    DiscoveredInterpreter,
    InterpreterDiscovery,
)
from pydeps_intelligence.validation.runners.docker_runner import DockerRunner
from pydeps_intelligence.validation.runners.local_runner import LocalRunner
from pydeps_intelligence.validation.runners.remote_runner import RemoteRunner


class FakeInterpreterDiscovery(InterpreterDiscovery):
    """Mock interpreter discovery providing deterministic environments."""

    def __init__(self, interpreters: list[DiscoveredInterpreter] | None = None) -> None:
        super().__init__()
        self._fake_interpreters = interpreters or []

    def discover_all(self, force_refresh: bool = False) -> list[DiscoveredInterpreter]:
        return self._fake_interpreters

    def find_matching_interpreter(self, target: TargetEnvironment) -> DiscoveredInterpreter | None:
        for interp in self._fake_interpreters:
            if (
                interp.operating_system == target.operating_system
                and interp.architecture == target.architecture
                and interp.implementation == target.implementation
                and interp.series == target.python_version
            ):
                return interp
        return None


def test_local_runner_rejects_foreign_os() -> None:
    """Local runner must strictly reject targets with foreign operating systems."""
    host_os = OperatingSystem.WINDOWS if platform.system() == "Windows" else OperatingSystem.LINUX
    foreign_os = (
        OperatingSystem.MACOS if host_os != OperatingSystem.MACOS else OperatingSystem.LINUX
    )

    runner = LocalRunner()
    target = TargetEnvironment(
        python_version="3.11",
        operating_system=foreign_os,
        architecture=Architecture.X86_64,
    )

    can_run, reason = runner.can_execute(target)
    assert not can_run
    assert reason is not None
    assert f"Target OS '{foreign_os.value}' cannot be executed" in reason


def test_local_runner_rejects_foreign_architecture() -> None:
    """Local runner must reject incompatible foreign CPU architectures."""
    host_os = OperatingSystem.WINDOWS if platform.system() == "Windows" else OperatingSystem.LINUX
    host_arch = (
        Architecture.X86_64
        if platform.machine().lower() in ("amd64", "x86_64")
        else Architecture.ARM64
    )
    foreign_arch = Architecture.ARM64 if host_arch == Architecture.X86_64 else Architecture.X86_64

    runner = LocalRunner()
    target = TargetEnvironment(
        python_version="3.11",
        operating_system=host_os,
        architecture=foreign_arch,
    )

    can_run, reason = runner.can_execute(target)
    assert not can_run
    assert reason is not None
    assert f"Target architecture '{foreign_arch.value}' cannot be executed" in reason


def test_docker_runner_rejects_non_linux_targets() -> None:
    """Docker runner only executes Linux containers and must never claim
    Windows/macOS validation.
    """
    runner = DockerRunner()

    windows_target = TargetEnvironment(
        python_version="3.11",
        operating_system=OperatingSystem.WINDOWS,
        architecture=Architecture.X86_64,
    )
    can_run_win, reason_win = runner.can_execute(windows_target)
    assert not can_run_win
    assert reason_win is not None
    assert "Docker runner only supports Linux" in reason_win

    macos_target = TargetEnvironment(
        python_version="3.11",
        operating_system=OperatingSystem.MACOS,
        architecture=Architecture.ARM64,
    )
    can_run_mac, reason_mac = runner.can_execute(macos_target)
    assert not can_run_mac
    assert reason_mac is not None
    assert "Docker runner only supports Linux" in reason_mac


def test_remote_runner_unconfigured_behavior() -> None:
    """Remote runner without real configured credentials reports unavailable status."""
    runner = RemoteRunner()
    caps = runner.get_capabilities()
    assert not caps.is_available
    assert caps.unavailable_reason is not None
    assert "Remote runner provider is not configured" in caps.unavailable_reason

    target = TargetEnvironment(
        python_version="3.11",
        operating_system=OperatingSystem.LINUX,
        architecture=Architecture.X86_64,
    )
    can_run, reason = runner.can_execute(target)
    assert not can_run
    assert "Remote runner provider is not configured" in (reason or "")
