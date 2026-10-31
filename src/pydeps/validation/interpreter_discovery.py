"""Discovery and inspection of host and configured Python interpreters."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

from pydeps.models.project import (
    Architecture,
    OperatingSystem,
    PythonImplementation,
    TargetEnvironment,
)


class DiscoveredInterpreter(NamedTuple):
    """Details of an inspected Python interpreter."""

    executable: Path
    version_str: str  # e.g. "3.11.9"
    major: int
    minor: int
    micro: int
    operating_system: OperatingSystem
    architecture: Architecture
    implementation: PythonImplementation

    @property
    def series(self) -> str:
        """Major.minor version string (e.g. '3.11')."""
        return f"{self.major}.{self.minor}"


class InterpreterDiscovery:
    """Discovers, queries, and matches Python interpreters on the host system."""

    def __init__(self, search_paths: list[Path | str] | None = None) -> None:
        self.search_paths = [Path(p) for p in (search_paths or [])]
        self._cache: list[DiscoveredInterpreter] | None = None

    def discover_all(self, force_refresh: bool = False) -> list[DiscoveredInterpreter]:
        """Discover all accessible Python interpreters on PATH and standard locations."""
        if self._cache is not None and not force_refresh:
            return self._cache

        candidates: set[Path] = set()

        # 1. Current running interpreter
        candidates.add(Path(sys.executable).resolve())

        # 2. Configured search paths
        for p in self.search_paths:
            if p.is_file() and os.access(p, os.X_OK):
                candidates.add(p.resolve())
            elif p.is_dir():
                for name in (
                    "python",
                    "python.exe",
                    "python3",
                    "python3.exe",
                    "pypy",
                    "pypy.exe",
                    "pypy3",
                    "pypy3.exe",
                ):
                    candidate_file = p / name
                    if candidate_file.is_file() and os.access(candidate_file, os.X_OK):
                        candidates.add(candidate_file.resolve())

        # 3. Look up from PATH
        common_binaries = [
            "python",
            "python3",
            "python3.10",
            "python3.11",
            "python3.12",
            "python3.13",
            "python3.14",
            "pypy3",
        ]
        if platform.system() == "Windows":
            common_binaries.extend(["py", "python.exe", "python3.exe", "pypy3.exe"])

        for b in common_binaries:
            found = shutil.which(b)
            if found:
                candidates.add(Path(found).resolve())

        # Windows py launcher check
        if platform.system() == "Windows" and shutil.which("py"):
            try:
                out = subprocess.check_output(
                    ["py", "-0p"], text=True, timeout=5, stderr=subprocess.DEVNULL
                )
                for line in out.splitlines():
                    # Format: -V:3.11 * C:\Python311\python.exe
                    parts = line.strip().split()
                    if len(parts) >= 3 and parts[-1].endswith(".exe"):
                        p = Path(parts[-1]).resolve()
                        if p.is_file():
                            candidates.add(p)
            except Exception:
                pass

        discovered: list[DiscoveredInterpreter] = []
        for cand in sorted(candidates):
            info = self.inspect_interpreter(cand)
            if info:
                discovered.append(info)

        self._cache = discovered
        return discovered

    def inspect_interpreter(self, executable: Path) -> DiscoveredInterpreter | None:
        """Query a Python executable to extract structured platform metadata."""
        if not executable.is_file():
            return None

        probe_code = (
            "import sys, platform; "
            "v = sys.version_info; "
            "print(f'{v.major}.{v.minor}.{v.micro}|' "
            "f'{platform.system().lower()}|' "
            "f'{platform.machine().lower()}|' "
            "f'{platform.python_implementation().lower()}|' "
            "f'{sys.executable}')"
        )
        try:
            res = subprocess.run(
                [str(executable), "-c", probe_code],
                capture_output=True,
                text=True,
                timeout=10,
                shell=False,
            )
            if res.returncode != 0:
                return None

            raw = res.stdout.strip()
            if not raw or "|" not in raw:
                return None

            parts = raw.split("|")
            if len(parts) < 5:
                return None

            version_str, os_str, arch_str, impl_str, real_exec = parts[:5]
            v_parts = [int(p) for p in version_str.split(".")]
            major, minor, micro = v_parts[0], v_parts[1], v_parts[2] if len(v_parts) > 2 else 0

            # Map OS
            mapped_os = self._map_os(os_str)
            # Map Architecture
            mapped_arch = self._map_arch(arch_str)
            # Map Implementation
            mapped_impl = (
                PythonImplementation.PYPY if "pypy" in impl_str else PythonImplementation.CPYTHON
            )

            return DiscoveredInterpreter(
                executable=Path(real_exec).resolve(),
                version_str=version_str,
                major=major,
                minor=minor,
                micro=micro,
                operating_system=mapped_os,
                architecture=mapped_arch,
                implementation=mapped_impl,
            )
        except Exception:
            return None

    def find_matching_interpreter(self, target: TargetEnvironment) -> DiscoveredInterpreter | None:
        """Find an interpreter that matches the requested target environment."""
        interpreters = self.discover_all()

        target_py_clean = target.python_version.lstrip("v").strip()
        target_os = target.operating_system
        target_arch = target.architecture
        target_impl = target.implementation

        for interp in interpreters:
            # Check OS
            if interp.operating_system != target_os:
                continue
            # Check architecture
            if interp.architecture != target_arch:
                continue
            # Check implementation
            if interp.implementation != target_impl:
                continue
            # Check Python version
            if target_py_clean == interp.series or target_py_clean == interp.version_str:
                return interp
            if interp.version_str.startswith(target_py_clean):
                return interp

        return None

    @staticmethod
    def _map_os(raw_os: str) -> OperatingSystem:
        clean = raw_os.lower()
        if "windows" in clean or clean == "win32" or clean == "nt":
            return OperatingSystem.WINDOWS
        if "linux" in clean:
            return OperatingSystem.LINUX
        if "darwin" in clean or "mac" in clean:
            return OperatingSystem.MACOS
        return OperatingSystem.LINUX

    @staticmethod
    def _map_arch(raw_arch: str) -> Architecture:
        clean = raw_arch.lower()
        if clean in ("amd64", "x86_64", "x64"):
            return Architecture.X86_64
        if clean in ("arm64", "aarch64"):
            return Architecture.ARM64
        if clean in ("x86", "i386", "i686"):
            return Architecture.X86
        return Architecture.X86_64
