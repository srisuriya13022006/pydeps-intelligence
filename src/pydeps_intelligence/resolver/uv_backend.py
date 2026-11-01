"""Subprocess integration backend for the uv packaging and resolution tool."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]
from packaging.utils import canonicalize_name

from pydeps_intelligence.models.dependencies import (
    Dependency,
    DependencyType,
    ResolutionDiagnostic,
    ResolutionMode,
    ResolutionRequest,
    ResolutionResult,
    ResolutionStatus,
    ResolvedDependencyGraph,
    ResolvedPackage,
)
from pydeps_intelligence.models.project import TargetEnvironment
from pydeps_intelligence.resolver.conflict_analyzer import ConflictAnalyzer
from pydeps_intelligence.resolver.resolution_strategy import StrategyMapper
from pydeps_intelligence.resolver.resolution_workspace import ResolutionWorkspace


def sanitize_command_log(cmd: list[str]) -> str:
    """Mask index credentials in command arguments to prevent credential leakage."""
    sanitized: list[str] = []
    for arg in cmd:
        if "://" in arg and "@" in arg:
            clean = re.sub(r"://([^:]+):([^@]+)@", "://***:***@", arg)
            sanitized.append(clean)
        else:
            sanitized.append(arg)
    return " ".join(sanitized)


class UvBackend:
    """Manages subprocess execution of the uv dependency resolver."""

    DEFAULT_TIMEOUT_SECONDS = 60

    def __init__(self, uv_path: str | Path | None = None) -> None:
        self._custom_path = str(uv_path) if uv_path else None

    def find_uv(self) -> str | None:
        """Locate the uv binary on the system PATH or configured path."""
        if self._custom_path:
            return self._custom_path if shutil.which(self._custom_path) else None
        return shutil.which("uv")

    def get_version(self) -> str | None:
        """Query and return the uv version string (e.g. '0.4.18'), or None if unavailable."""
        binary = self.find_uv()
        if not binary:
            return None
        try:
            res = subprocess.run(
                [binary, "--version"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
                shell=False,
            )
            if res.returncode == 0:
                match = re.search(r"uv\s+([0-9]+\.[0-9]+\.[0-9]+[a-zA-Z0-9\.\-]*)", res.stdout)
                return match.group(1) if match else res.stdout.strip()
        except Exception:
            return None
        return None

    def is_available(self) -> bool:
        """Check whether uv is installed and runnable."""
        return self.find_uv() is not None

    def parse_uv_lock(
        self,
        lock_content: str,
        direct_names: set[str],
    ) -> ResolvedDependencyGraph:
        """Parse native uv.lock TOML content into a typed ResolvedDependencyGraph."""
        data = tomllib.loads(lock_content)
        packages_list = data.get("package", [])

        packages_map: dict[str, ResolvedPackage] = {}
        edges: dict[str, list[str]] = {}
        all_required_by: dict[str, list[str]] = {}

        # First pass: index packages and dependency lists
        for pkg in packages_list:
            raw_name = pkg.get("name", "")
            if not raw_name:
                continue
            name = canonicalize_name(raw_name)
            version = str(pkg.get("version", ""))

            dep_entries = pkg.get("dependencies", [])
            child_names: list[str] = []
            for d in dep_entries:
                c_name = d.get("name") if isinstance(d, dict) else str(d)
                if c_name:
                    canonical_child = canonicalize_name(c_name)
                    child_names.append(canonical_child)
                    all_required_by.setdefault(canonical_child, []).append(name)

            edges[name] = child_names

            # Extract hashes if present
            hashes: list[str] = []
            wheels = pkg.get("wheels", [])
            for w in wheels:
                h = w.get("hash")
                if h:
                    hashes.append(h)
            sdist = pkg.get("sdist", {})
            if isinstance(sdist, dict) and sdist.get("hash"):
                hashes.append(sdist["hash"])

            dep_type = DependencyType.DIRECT if name in direct_names else DependencyType.TRANSITIVE

            packages_map[name] = ResolvedPackage(
                name=name,
                version=version,
                dependency_type=dep_type,
                hashes=hashes,
                dependencies=child_names,
                required_by=[],
            )

        # Second pass: fill required_by
        for name, pkg_obj in list(packages_map.items()):
            parents = all_required_by.get(name, [])
            packages_map[name] = pkg_obj.model_copy(update={"required_by": sorted(set(parents))})

        roots = [name for name in packages_map if name in direct_names]
        if not roots:
            roots = list(packages_map.keys())

        transitive_count = sum(
            1 for p in packages_map.values() if p.dependency_type == DependencyType.TRANSITIVE
        )
        direct_count = len(packages_map) - transitive_count

        return ResolvedDependencyGraph(
            packages=packages_map,
            roots=roots,
            edges=edges,
            direct_count=direct_count,
            transitive_count=transitive_count,
        )

    def resolve_universal(
        self,
        request: ResolutionRequest,
        workspace: ResolutionWorkspace,
    ) -> ResolutionResult:
        """Execute universal resolution using 'uv lock' in an isolated workspace."""
        binary = self.find_uv()
        if not binary:
            return ResolutionResult(
                success=False,
                status=ResolutionStatus.FAILURE,
                mode=ResolutionMode.UNIVERSAL,
                strategy=request.strategy,
                backend="uv",
                conflicts=["uv executable is not installed or not found on system PATH."],
                diagnostics=[
                    ResolutionDiagnostic(
                        message="uv is not installed. Install uv or use --backend pip.",
                        level="error",
                        source="uv_backend",
                    )
                ],
            )

        # Generate synthetic pyproject.toml
        workspace.create_synthetic_pyproject_toml(
            dependencies=request.direct_dependencies,
            requires_python=">=3.8",
        )

        # Build command array
        cmd = [binary, "lock", "--no-build"]
        strategy_flags = StrategyMapper.get_uv_flags(
            strategy=request.strategy,
            allow_prereleases=request.allow_prereleases,
            upgrade=request.upgrade,
            upgrade_packages=request.upgrade_packages,
        )
        cmd.extend(strategy_flags)

        if request.offline:
            cmd.append("--offline")

        log_cmd = sanitize_command_log(cmd)

        try:
            proc = subprocess.run(
                cmd,
                cwd=workspace.path,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.DEFAULT_TIMEOUT_SECONDS,
                shell=False,
            )
        except subprocess.TimeoutExpired:
            return ResolutionResult(
                success=False,
                status=ResolutionStatus.FAILURE,
                mode=ResolutionMode.UNIVERSAL,
                strategy=request.strategy,
                backend="uv",
                conflicts=[f"Resolution timed out after {self.DEFAULT_TIMEOUT_SECONDS}s."],
                diagnostics=[
                    ResolutionDiagnostic(
                        message=f"Command '{log_cmd}' timed out.",
                        level="error",
                        source="uv_backend",
                    )
                ],
            )

        if proc.returncode != 0:
            conflicts = ConflictAnalyzer.analyze_uv_error(proc.stderr, proc.stdout)
            conflict_msgs = [c.suggested_investigation or c.original_diagnostics for c in conflicts]
            return ResolutionResult(
                success=False,
                status=ResolutionStatus.CONFLICT,
                mode=ResolutionMode.UNIVERSAL,
                strategy=request.strategy,
                backend="uv",
                conflicts=conflict_msgs,
                structured_conflicts=conflicts,
                diagnostics=[
                    ResolutionDiagnostic(
                        message=proc.stderr.strip() or proc.stdout.strip(),
                        level="error",
                        source="uv_backend",
                    )
                ],
            )

        # Read resulting uv.lock
        lockfile = workspace.path / "uv.lock"
        if not lockfile.exists():
            return ResolutionResult(
                success=False,
                status=ResolutionStatus.FAILURE,
                mode=ResolutionMode.UNIVERSAL,
                backend="uv",
                conflicts=["uv lock succeeded but uv.lock file was not generated."],
            )

        lock_content = lockfile.read_text(encoding="utf-8")
        direct_names = {canonicalize_name(d.name) for d in request.direct_dependencies}
        graph = self.parse_uv_lock(lock_content, direct_names=direct_names)

        # Export requirements.txt via uv export
        reqs_txt: str | None = None
        export_proc = subprocess.run(
            [binary, "export", "--format", "requirements.txt", "--no-hashes"],
            cwd=workspace.path,
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
            shell=False,
        )
        if export_proc.returncode == 0:
            reqs_txt = export_proc.stdout

        resolved_deps: list[Dependency] = [
            Dependency(
                name=pkg.name,
                version_specifier=f"=={pkg.version}",
                dependency_type=pkg.dependency_type,
            )
            for pkg in graph.packages.values()
        ]

        return ResolutionResult(
            success=True,
            status=ResolutionStatus.SUCCESS,
            mode=ResolutionMode.UNIVERSAL,
            strategy=request.strategy,
            backend="uv",
            resolved_dependencies=resolved_deps,
            graph=graph,
            lockfile_content=lock_content,
            requirements_txt=reqs_txt,
        )

    def resolve_per_target(
        self,
        request: ResolutionRequest,
        target: TargetEnvironment,
        workspace: ResolutionWorkspace,
    ) -> ResolutionResult:
        """Resolve dependencies for a specific target environment using 'uv pip compile'."""
        binary = self.find_uv()
        if not binary:
            return ResolutionResult(
                success=False,
                status=ResolutionStatus.FAILURE,
                mode=ResolutionMode.PER_TARGET,
                backend="uv",
                conflicts=["uv executable is not found on PATH."],
            )

        # Write requirements.in file
        req_in = workspace.create_requirements_in(
            request.direct_dependencies, filename="requirements.in"
        )
        req_out = workspace.path / "requirements.txt"

        cmd = [
            binary,
            "pip",
            "compile",
            str(req_in),
            "--output-file",
            str(req_out),
            "--python-version",
            target.python_version,
            "--no-build",
        ]

        # Map OS to platform flag
        os_val = target.operating_system.value
        if os_val == "windows":
            cmd.extend(["--platform", "windows"])
        elif os_val == "linux":
            cmd.extend(["--platform", "linux"])
        elif os_val == "macos":
            cmd.extend(["--platform", "macos"])

        strategy_flags = StrategyMapper.get_uv_flags(
            strategy=request.strategy,
            allow_prereleases=request.allow_prereleases,
            upgrade=request.upgrade,
            upgrade_packages=request.upgrade_packages,
        )
        cmd.extend(strategy_flags)

        if request.offline:
            cmd.append("--offline")

        try:
            proc = subprocess.run(
                cmd,
                cwd=workspace.path,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.DEFAULT_TIMEOUT_SECONDS,
                shell=False,
            )
        except subprocess.TimeoutExpired:
            return ResolutionResult(
                success=False,
                status=ResolutionStatus.FAILURE,
                mode=ResolutionMode.PER_TARGET,
                backend="uv",
                conflicts=[f"Resolution timed out for target {target.platform_tag}"],
            )

        if proc.returncode != 0:
            conflicts = ConflictAnalyzer.analyze_uv_error(
                proc.stderr, proc.stdout, target_environment=target.platform_tag
            )
            conflict_msgs = [c.suggested_investigation or c.original_diagnostics for c in conflicts]
            return ResolutionResult(
                success=False,
                status=ResolutionStatus.CONFLICT,
                mode=ResolutionMode.PER_TARGET,
                backend="uv",
                conflicts=conflict_msgs,
                structured_conflicts=conflicts,
            )

        # Read output requirements.txt
        req_content = req_out.read_text(encoding="utf-8") if req_out.exists() else ""
        resolved_deps: list[Dependency] = []
        direct_names = {canonicalize_name(d.name) for d in request.direct_dependencies}
        packages_map: dict[str, ResolvedPackage] = {}

        for line in req_content.splitlines():
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue
            clean_line = line_str.split("#")[0].strip()
            if not clean_line:
                continue
            marker_str = None
            if ";" in clean_line:
                base_part, marker_str = clean_line.split(";", 1)
                base_part = base_part.strip()
                marker_str = marker_str.strip()
            else:
                base_part = clean_line

            if "==" in base_part:
                parts = base_part.split("==", 1)
                p_name = canonicalize_name(parts[0].strip())
                p_ver = parts[1].strip()
                dep_type = (
                    DependencyType.DIRECT if p_name in direct_names else DependencyType.TRANSITIVE
                )
                resolved_deps.append(
                    Dependency(
                        name=p_name,
                        version_specifier=f"=={p_ver}",
                        environment_marker=marker_str,
                        dependency_type=dep_type,
                    )
                )
                packages_map[p_name] = ResolvedPackage(
                    name=p_name,
                    version=p_ver,
                    dependency_type=dep_type,
                    environment_marker=marker_str,
                )

        graph = ResolvedDependencyGraph(
            packages=packages_map,
            roots=[n for n in packages_map if n in direct_names],
            edges={},
            direct_count=len([n for n in packages_map if n in direct_names]),
            transitive_count=len(packages_map)
            - len([n for n in packages_map if n in direct_names]),
        )

        return ResolutionResult(
            success=True,
            status=ResolutionStatus.SUCCESS,
            mode=ResolutionMode.PER_TARGET,
            backend="uv",
            resolved_dependencies=resolved_deps,
            graph=graph,
            requirements_txt=req_content,
        )
