"""High-level orchestrator connecting project discovery and mapping to dependency resolution."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from pydeps.models.analysis import ImportAnalysisResult
from pydeps.models.dependencies import (
    Dependency,
    DependencyType,
    ResolutionMode,
    ResolutionRequest,
    ResolutionResult,
    ResolutionStrategy,
)
from pydeps.models.mapping import PackageReport
from pydeps.models.project import TargetEnvironment
from pydeps.resolver.constraint_collector import ConstraintCollector
from pydeps.resolver.dependency_classifier import DependencyClassifier
from pydeps.resolver.dependency_resolver import DependencyResolver


class ResolutionOrchestrator:
    """Orchestrates end-to-end dependency resolution from discovered imports and constraints."""

    def __init__(
        self,
        resolver: DependencyResolver | None = None,
        classifier: DependencyClassifier | None = None,
    ) -> None:
        self.resolver = resolver or DependencyResolver()
        self.classifier = classifier or DependencyClassifier()

    def orchestrate(
        self,
        project_path: Path | str,
        package_report: PackageReport,
        analysis: ImportAnalysisResult | None = None,
        mode: ResolutionMode | str = ResolutionMode.UNIVERSAL,
        strategy: ResolutionStrategy | str = ResolutionStrategy.LATEST_COMPATIBLE,
        backend: str = "uv",
        targets: Sequence[TargetEnvironment] | None = None,
        extras: list[str] | None = None,
        include_dev: bool = False,
        include_optional: bool = False,
        offline: bool = False,
        allow_prereleases: bool = False,
        output_dir: Path | str | None = None,
        upgrade: bool = False,
        upgrade_packages: list[str] | None = None,
    ) -> ResolutionResult:
        """Collect constraints, classify imports, build candidates, and run resolution."""
        path = Path(project_path)

        # 1. Collect static declarations and existing constraints from project
        collector = ConstraintCollector(path)
        collected = collector.collect_all_constraints()
        project_constraints: dict[str, Dependency] = collected["by_name"]

        # Extract version specifier map for classifier
        constraint_specifiers: dict[str, str] = {
            name: dep.version_specifier
            for name, dep in project_constraints.items()
            if dep.version_specifier
        }

        # 2. Classify discovered imports into typed groups
        classified = self.classifier.classify(
            package_report=package_report,
            analysis=analysis,
            constraints=constraint_specifiers,
        )

        # 3. Assemble candidate direct dependencies
        # Candidates begin with runtime imports
        candidate_deps: dict[str, Dependency] = {d.name: d for d in classified["runtime"]}

        if include_dev:
            for d in classified["dev"]:
                candidate_deps[d.name] = d

        if include_optional:
            for d in classified["optional"]:
                candidate_deps[d.name] = d

        # Merge in explicit project declarations: project constraints take precedence
        for name, proj_dep in project_constraints.items():
            if name in candidate_deps:
                # Override unconstrained candidate with explicit project constraint
                candidate_deps[name] = proj_dep
            else:
                # If explicit project dependency was not imported, include if group matches
                if proj_dep.dependency_type == DependencyType.DIRECT:
                    candidate_deps[name] = proj_dep
                elif proj_dep.dependency_type == DependencyType.DEV and include_dev:
                    candidate_deps[name] = proj_dep
                elif proj_dep.dependency_type == DependencyType.OPTIONAL and include_optional:
                    candidate_deps[name] = proj_dep

        # Ensure mode and strategy are typed enums
        res_mode = ResolutionMode(mode) if isinstance(mode, str) else mode
        res_strategy = ResolutionStrategy(strategy) if isinstance(strategy, str) else strategy

        # 4. Construct ResolutionRequest
        request = ResolutionRequest(
            project_path=path,
            direct_dependencies=list(candidate_deps.values()),
            constraints=list(project_constraints.values()),
            mode=res_mode,
            strategy=res_strategy,
            backend=backend,
            targets=list(targets) if targets else [],
            extras=extras or [],
            include_dev=include_dev,
            include_optional=include_optional,
            offline=offline,
            allow_prereleases=allow_prereleases,
            output_dir=Path(output_dir) if output_dir else None,
            upgrade=upgrade,
            upgrade_packages=upgrade_packages or [],
        )

        # 5. Execute resolution
        result = self.resolver.resolve(request)

        # Append classification diagnostics to result diagnostics
        result.diagnostics.extend(classified["diagnostics"])
        result.diagnostics.extend(collected["diagnostics"])

        return result
