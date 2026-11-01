"""Fallback subprocess integration using python -m pip install --dry-run --report."""

from __future__ import annotations

import json
import subprocess
import sys

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


class PipBackend:
    """Limited fallback resolver using pip's dry-run report functionality."""

    DEFAULT_TIMEOUT_SECONDS = 90

    def __init__(self, python_executable: str | None = None) -> None:
        self.python_executable = python_executable or sys.executable

    def is_available(self) -> bool:
        """Verify that pip is available via python -m pip."""
        try:
            res = subprocess.run(
                [self.python_executable, "-m", "pip", "--version"],
                capture_output=True,
                check=False,
                timeout=10,
                shell=False,
            )
            return res.returncode == 0
        except Exception:
            return False

    def parse_pip_report(
        self,
        report_data: dict,
        direct_names: set[str],
    ) -> ResolvedDependencyGraph:
        """Parse pip install --report JSON into a ResolvedDependencyGraph."""
        packages_map: dict[str, ResolvedPackage] = {}
        install_list = report_data.get("install", [])

        for item in install_list:
            metadata = item.get("metadata", {})
            raw_name = metadata.get("name") or item.get("download_info", {}).get("info", {}).get(
                "name"
            )
            if not raw_name:
                continue

            name = canonicalize_name(raw_name)
            version = str(metadata.get("version", ""))
            dep_type = DependencyType.DIRECT if name in direct_names else DependencyType.TRANSITIVE

            # Extract hashes if available
            hashes: list[str] = []
            archive_info = item.get("download_info", {}).get("archive_info", {})
            if "hashes" in archive_info:
                hashes.extend(archive_info["hashes"].values())

            packages_map[name] = ResolvedPackage(
                name=name,
                version=version,
                dependency_type=dep_type,
                hashes=hashes,
                dependencies=[],
                required_by=[],
            )

        roots = [n for n in packages_map if n in direct_names]
        if not roots:
            roots = list(packages_map.keys())

        transitive_count = sum(
            1 for p in packages_map.values() if p.dependency_type == DependencyType.TRANSITIVE
        )
        direct_count = len(packages_map) - transitive_count

        return ResolvedDependencyGraph(
            packages=packages_map,
            roots=roots,
            edges={},
            direct_count=direct_count,
            transitive_count=transitive_count,
        )

    def resolve(
        self,
        request: ResolutionRequest,
        workspace: ResolutionWorkspace,
        target: TargetEnvironment | None = None,
    ) -> ResolutionResult:
        """Execute dependency resolution using pip install --dry-run --report."""
        # Check pip limitation: pip cannot perform universal multi-platform resolution
        if request.mode == ResolutionMode.UNIVERSAL:
            return ResolutionResult(
                success=False,
                status=ResolutionStatus.FAILURE,
                mode=ResolutionMode.UNIVERSAL,
                backend="pip",
                conflicts=["pip does not support multi-platform universal resolution."],
                diagnostics=[
                    ResolutionDiagnostic(
                        message=(
                            "pip's resolver is designed for single-target environments only. "
                            "For universal resolution across multiple platforms, use uv."
                        ),
                        level="error",
                        source="pip_backend",
                    )
                ],
            )

        report_file = workspace.path / "pip_report.json"
        req_in = workspace.create_requirements_in(
            request.direct_dependencies, filename="requirements.in"
        )

        cmd = [
            self.python_executable,
            "-m",
            "pip",
            "install",
            "--dry-run",
            "--ignore-installed",
            "--report",
            str(report_file),
            "--no-deps",  # Or normal resolution
            "-r",
            str(req_in),
        ]
        # Remove --no-deps to allow transitive resolution:
        cmd.remove("--no-deps")

        # Binary-only by default to avoid source compilation
        cmd.append("--only-binary=:all:")

        # Foreign target flags
        if target:
            cmd.extend(["--python-version", target.python_version])
            os_val = target.operating_system.value
            arch_val = target.architecture.value

            # Derive platform tag for pip if possible
            if os_val == "windows":
                if arch_val in ("x86_64", "amd64"):
                    cmd.extend(["--platform", "win_amd64"])
                elif arch_val == "arm64":
                    cmd.extend(["--platform", "win_arm64"])
            elif os_val == "linux":
                if arch_val in ("x86_64", "amd64"):
                    cmd.extend(["--platform", "manylinux2014_x86_64"])
                elif arch_val in ("aarch64", "arm64"):
                    cmd.extend(["--platform", "manylinux2014_aarch64"])
            elif os_val == "macos":
                if arch_val == "arm64":
                    cmd.extend(["--platform", "macosx_11_0_arm64"])
                else:
                    cmd.extend(["--platform", "macosx_10_9_x86_64"])

            impl = target.implementation.value
            cmd.extend(["--implementation", "cp" if impl == "cpython" else "pp"])

        strategy_flags = StrategyMapper.get_pip_flags(
            strategy=request.strategy,
            allow_prereleases=request.allow_prereleases,
            upgrade=request.upgrade,
        )
        cmd.extend(strategy_flags)

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
                mode=request.mode,
                backend="pip",
                conflicts=[f"pip resolution timed out after {self.DEFAULT_TIMEOUT_SECONDS}s."],
            )

        if proc.returncode != 0:
            target_tag = target.platform_tag if target else None
            conflicts = ConflictAnalyzer.analyze_pip_error(
                proc.stderr, proc.stdout, target_environment=target_tag
            )
            conflict_msgs = [c.suggested_investigation or c.original_diagnostics for c in conflicts]
            return ResolutionResult(
                success=False,
                status=ResolutionStatus.CONFLICT,
                mode=request.mode,
                backend="pip",
                conflicts=conflict_msgs,
                structured_conflicts=conflicts,
                diagnostics=[
                    ResolutionDiagnostic(
                        message=proc.stderr.strip() or proc.stdout.strip(),
                        level="error",
                        source="pip_backend",
                    )
                ],
            )

        if not report_file.exists():
            return ResolutionResult(
                success=False,
                status=ResolutionStatus.FAILURE,
                mode=request.mode,
                backend="pip",
                conflicts=["pip command succeeded but report JSON was not written."],
            )

        try:
            with open(report_file, encoding="utf-8") as f:
                report_data = json.load(f)
        except Exception as exc:
            return ResolutionResult(
                success=False,
                status=ResolutionStatus.FAILURE,
                mode=request.mode,
                backend="pip",
                conflicts=[f"Failed to read pip report JSON: {exc}"],
            )

        direct_names = {canonicalize_name(d.name) for d in request.direct_dependencies}
        graph = self.parse_pip_report(report_data, direct_names=direct_names)

        resolved_deps: list[Dependency] = [
            Dependency(
                name=pkg.name,
                version_specifier=f"=={pkg.version}",
                dependency_type=pkg.dependency_type,
            )
            for pkg in graph.packages.values()
        ]

        reqs_txt = "\n".join(
            sorted(
                f"{d.name}=={(d.version_specifier or '').removeprefix('==')}" for d in resolved_deps
            )
        )

        return ResolutionResult(
            success=True,
            status=ResolutionStatus.SUCCESS,
            mode=request.mode,
            backend="pip",
            resolved_dependencies=resolved_deps,
            graph=graph,
            requirements_txt=reqs_txt,
            diagnostics=[
                ResolutionDiagnostic(
                    message=(
                        "Resolution performed via pip fallback (single-target). "
                        "uv.lock not supported."
                    ),
                    level="info",
                    source="pip_backend",
                )
            ],
        )
