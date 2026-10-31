"""Unit tests for InterpreterDiscovery and environment inspection."""

from __future__ import annotations

import sys
from pathlib import Path

from pydeps.models.project import (
    Architecture,
    OperatingSystem,
    TargetEnvironment,
)
from pydeps.validation.interpreter_discovery import InterpreterDiscovery


def test_discover_current_running_interpreter() -> None:
    """Discovery engine must always discover the current executing Python environment."""
    discovery = InterpreterDiscovery()
    all_interps = discovery.discover_all()
    assert len(all_interps) >= 1

    current_path = Path(sys.executable).resolve()
    executables = [i.executable.resolve() for i in all_interps]
    assert current_path in executables

    current_info = next(i for i in all_interps if i.executable.resolve() == current_path)
    assert current_info.major == sys.version_info.major
    assert current_info.minor == sys.version_info.minor
    assert current_info.series == f"{sys.version_info.major}.{sys.version_info.minor}"


def test_match_target_interpreter_success() -> None:
    """Target matching must return interpreter if OS, architecture, version and impl match."""
    current_major = sys.version_info.major
    current_minor = sys.version_info.minor
    current_ver = f"{current_major}.{current_minor}"

    discovery = InterpreterDiscovery()
    host_interp = next(
        i
        for i in discovery.discover_all()
        if i.executable.resolve() == Path(sys.executable).resolve()
    )

    target = TargetEnvironment(
        python_version=current_ver,
        operating_system=host_interp.operating_system,
        architecture=host_interp.architecture,
        implementation=host_interp.implementation,
    )

    matched = discovery.find_matching_interpreter(target)
    assert matched is not None
    assert matched.series == current_ver


def test_match_target_interpreter_missing_version() -> None:
    """Target matching returns None when requesting an uninstalled Python version."""
    discovery = InterpreterDiscovery()
    target = TargetEnvironment(
        python_version="3.99",
        operating_system=OperatingSystem.WINDOWS,
        architecture=Architecture.X86_64,
    )
    matched = discovery.find_matching_interpreter(target)
    assert matched is None


def test_inspect_nonexistent_file() -> None:
    """Inspect returns None when given a path that does not exist."""
    discovery = InterpreterDiscovery()
    assert discovery.inspect_interpreter(Path("/nonexistent/python")) is None
