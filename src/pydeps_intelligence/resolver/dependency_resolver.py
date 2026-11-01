"""Core dependency resolution engine executing universal and per-target resolutions."""

from __future__ import annotations

from pydeps_intelligence.models.dependencies import (
    Dependency,
    ResolutionMode,
    ResolutionRequest,
    ResolutionResult,
    ResolutionStatus,
    ResolutionTarget,
)
from pydeps_intelligence.models.project import TargetEnvironment
from pydeps_intelligence.resolver.lockfile_exporter import LockfileExporter
from pydeps_intelligence.resolver.pip_backend import PipBackend
from pydeps_intelligence.resolver.resolution_workspace import ResolutionWorkspace
from pydeps_intelligence.resolver.uv_backend import UvBackend


class DependencyResolver:
    """Coordinates dependency resolution backends (uv and pip) in universal and per-target modes."""

    def __init__(
        self,
        uv_backend: UvBackend | None = None,
        pip_backend: PipBackend | None = None,
    ) -> None:
        self.uv = uv_backend or UvBackend()
        self.pip = pip_backend or PipBackend()

    def resolve(self, request: ResolutionRequest) -> ResolutionResult:
        """Execute resolution based on the given ResolutionRequest."""
        backend_name = request.backend.lower()

        # Route universal mode
        if request.mode == ResolutionMode.UNIVERSAL:
            if backend_name == "pip":
                # Pip does not support universal mode
                return self.pip.resolve(request, ResolutionWorkspace())

            with ResolutionWorkspace() as workspace:
                result = self.uv.resolve_universal(request, workspace)

        # Route per-target mode
        else:
            targets: list[TargetEnvironment] = [
                t for t in request.targets if isinstance(t, TargetEnvironment)
            ]
            if not targets:
                return ResolutionResult(
                    success=False,
                    status=ResolutionStatus.FAILURE,
                    mode=ResolutionMode.PER_TARGET,
                    backend=backend_name,
                    conflicts=["No target environments specified for per-target resolution."],
                )

            per_target_map: dict[str, ResolutionResult] = {}
            all_resolved_deps: list[Dependency] = []
            overall_success = True
            all_conflicts: list[str] = []

            for target in targets:
                tag = target.platform_tag
                with ResolutionWorkspace() as workspace:
                    if backend_name == "pip":
                        target_res = self.pip.resolve(request, workspace, target=target)
                    else:
                        target_res = self.uv.resolve_per_target(request, target, workspace)

                target_res.target = ResolutionTarget(
                    python_version=target.python_version,
                    operating_system=target.operating_system.value,
                    architecture=target.architecture.value,
                    implementation=target.implementation.value,
                    abi=None,
                    platform_tag=tag,
                )
                per_target_map[tag] = target_res

                if target_res.success:
                    all_resolved_deps.extend(target_res.resolved_dependencies)
                else:
                    overall_success = False
                    all_conflicts.extend(target_res.conflicts)

            # Deduplicate resolved dependencies across targets
            unique_deps: dict[str, Dependency] = {}
            for d in all_resolved_deps:
                unique_deps[f"{d.name}:{d.version_specifier}"] = d

            result = ResolutionResult(
                success=overall_success,
                status=ResolutionStatus.SUCCESS if overall_success else ResolutionStatus.CONFLICT,
                mode=ResolutionMode.PER_TARGET,
                strategy=request.strategy,
                backend=backend_name,
                resolved_dependencies=list(unique_deps.values()),
                conflicts=all_conflicts,
                per_target_results=per_target_map,
            )

        # Export outputs if requested
        if request.output_dir:
            created = LockfileExporter.export(
                result=result,
                output_dir=request.output_dir,
                overwrite=True,
            )
            result.output_files = created

        return result
