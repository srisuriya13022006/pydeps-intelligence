"""High-level unified API facade for PyDeps."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from pydeps.analyzer.analyzer import ImportAnalyzer
from pydeps.compatibility.compatibility_matrix import MatrixBuilder
from pydeps.compatibility.platform_profiles import TargetPlatformProfile
from pydeps.config import resolve_project_config
from pydeps.metadata.metadata_cache import MetadataCache
from pydeps.metadata.metadata_models import MetadataResult, PackageRelease
from pydeps.metadata.metadata_provider import MetadataProvider
from pydeps.models.analysis import ImportAnalysisResult
from pydeps.models.compatibility import CompatibilityMatrix
from pydeps.models.dependencies import ResolutionMode, ResolutionResult, ResolutionStrategy
from pydeps.models.imports import ImportRecord
from pydeps.models.mapping import PackageReport
from pydeps.models.project import ProjectConfig, TargetEnvironment
from pydeps.models.structure import ProjectStructure
from pydeps.models.validation import ExecutionPolicy, NetworkPolicy, ValidationReport
from pydeps.registry.package_mapper import PackageMapper
from pydeps.scanner.scanner import ProjectScanner


class PyDeps:
    """Unified engine coordinator for scanning, import analysis, package mapping, and metadata."""

    def __init__(
        self,
        project_path: Path | str = ".",
        config: ProjectConfig | None = None,
        offline: bool = False,
        cache_dir: Path | str | None = None,
        overrides: Mapping[str, str | list[str]] | None = None,
    ) -> None:
        self.project_path = Path(project_path)
        self.config = config or resolve_project_config(self.project_path)
        self.offline = offline

        self.cache_dir = (
            Path(cache_dir)
            if cache_dir
            else self.project_path / self.config.output_directory / "cache"
        )
        self.metadata_cache = MetadataCache(cache_dir=self.cache_dir, offline=offline)
        self.scanner = ProjectScanner(config=self.config)
        self.analyzer = ImportAnalyzer()
        self.mapper = PackageMapper(overrides=overrides)
        self.metadata_provider = MetadataProvider(cache=self.metadata_cache, offline=offline)

    def scan(self) -> ProjectStructure:
        """Scan project directory and discover source files, notebooks, and metadata."""
        return self.scanner.scan(self.project_path)

    def analyze(self, python_version: str = "3.11") -> ImportAnalysisResult:
        """Scan the project and perform static AST import extraction and classification."""
        structure = self.scan()
        return self.analyzer.analyze_project(structure, target_python_version=python_version)

    def resolve_packages(
        self,
        analysis: ImportAnalysisResult | None = None,
        overrides: Mapping[str, str | list[str]] | None = None,
    ) -> PackageReport:
        """Map discovered external candidate imports to PyPI distribution names."""
        if analysis is None:
            analysis = self.analyze()

        mapper = self.mapper
        if overrides:
            mapper = PackageMapper(overrides=overrides)

        return mapper.map_analysis(analysis)

    def fetch_metadata(
        self,
        package_report: PackageReport | None = None,
        offline: bool | None = None,
    ) -> dict[str, MetadataResult]:
        """Retrieve PyPI release metadata for resolved distribution packages.

        Never queries PyPI for standard library or local project packages.
        """
        if package_report is None:
            package_report = self.resolve_packages()

        is_offline = self.offline if offline is None else offline

        # Only query distributions resolved from external imports
        target_dists = package_report.selected_distributions
        return self.metadata_provider.get_batch_metadata(target_dists, offline=is_offline)

    def _build_default_targets(self) -> list[TargetEnvironment]:
        """Construct default target environments from project configuration."""
        targets: list[TargetEnvironment] = []
        for py in self.config.target_python_versions:
            for os_val in self.config.target_operating_systems:
                for arch in self.config.target_architectures:
                    for impl in self.config.target_implementations:
                        targets.append(
                            TargetEnvironment(
                                python_version=py,
                                operating_system=os_val,
                                architecture=arch,
                                implementation=impl,
                            )
                        )
        return targets

    def check_compatibility(
        self,
        metadata: dict[str, MetadataResult | PackageRelease]
        | Sequence[PackageRelease]
        | None = None,
        targets: Sequence[TargetEnvironment] | TargetEnvironment | None = None,
        profiles: dict[str, TargetPlatformProfile] | Sequence[TargetPlatformProfile] | None = None,
        extra: str | None = None,
    ) -> CompatibilityMatrix:
        """Evaluate package releases against target environments producing a CompatibilityMatrix."""
        if metadata is None:
            metadata = self.fetch_metadata()

        target_list: list[TargetEnvironment] = []
        if targets is None:
            target_list = self._build_default_targets()
        elif isinstance(targets, TargetEnvironment):
            target_list = [targets]
        else:
            target_list = list(targets)

        builder = MatrixBuilder()
        return builder.evaluate_matrix(
            releases=metadata,
            targets=target_list,
            profiles=profiles,
            extra=extra,
        )

    def resolve_dependencies(
        self,
        package_report: PackageReport | None = None,
        analysis: ImportAnalysisResult | None = None,
        metadata: dict[str, MetadataResult | PackageRelease]
        | Sequence[PackageRelease]
        | None = None,
        mode: ResolutionMode | str = ResolutionMode.UNIVERSAL,
        strategy: ResolutionStrategy | str = ResolutionStrategy.LATEST_COMPATIBLE,
        backend: str = "uv",
        targets: Sequence[TargetEnvironment] | None = None,
        extras: list[str] | None = None,
        include_dev: bool = False,
        include_optional: bool = False,
        offline: bool | None = None,
        allow_prereleases: bool = False,
        output_dir: Path | str | None = None,
        upgrade: bool = False,
        upgrade_packages: list[str] | None = None,
    ) -> ResolutionResult:
        """Resolve dependencies and return a strongly typed ResolutionResult."""
        if package_report is None:
            if analysis is None:
                analysis = self.analyze()
            package_report = self.resolve_packages(analysis)

        is_offline = self.offline if offline is None else offline
        target_list: list[TargetEnvironment] = []
        if targets is None:
            target_list = self._build_default_targets()
        else:
            target_list = list(targets)

        from pydeps.resolver.resolution_orchestrator import ResolutionOrchestrator

        orchestrator = ResolutionOrchestrator()
        return orchestrator.orchestrate(
            project_path=self.project_path,
            package_report=package_report,
            analysis=analysis,
            mode=mode,
            strategy=strategy,
            backend=backend,
            targets=target_list,
            extras=extras,
            include_dev=include_dev,
            include_optional=include_optional,
            offline=is_offline,
            allow_prereleases=allow_prereleases,
            output_dir=output_dir,
            upgrade=upgrade,
            upgrade_packages=upgrade_packages,
        )

    def validate(
        self,
        resolution_result: ResolutionResult | None = None,
        runner: str = "local",
        level: str = "install",
        target: TargetEnvironment | None = None,
        network: NetworkPolicy | str = NetworkPolicy.DISABLED,
        execution_policy: ExecutionPolicy | str | None = None,
        timeout: int = 300,
        memory_limit: str | None = None,
        cpu_limit: str | None = None,
        allow_local_execution: bool = False,
        allow_project_code: bool = False,
        project_test_command: list[str] | None = None,
        dry_run: bool = False,
        keep_environment: bool = False,
        output_dir: Path | str | None = None,
        discovered_imports: list[ImportRecord] | None = None,
    ) -> ValidationReport:
        """Validate resolved dependencies inside an isolated execution environment."""
        from pydeps.models.validation import (
            ExecutionPolicy,
            NetworkPolicy,
            ValidationRequest,
        )
        from pydeps.validation.validation_orchestrator import ValidationOrchestrator

        if resolution_result is None:
            resolution_result = self.resolve_dependencies()

        # Determine target environment
        target_env = target
        if target_env is None:
            if resolution_result.target:
                target_env = resolution_result.target
            elif runner == "local":
                import sys

                from pydeps.validation.runners.local_runner import LocalRunner

                host_os = LocalRunner._detect_host_os()
                host_arch = LocalRunner._detect_host_arch()
                py_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
                target_env = TargetEnvironment(
                    python_version=py_ver,
                    operating_system=host_os,
                    architecture=host_arch,
                )
            else:
                default_targets = self._build_default_targets()
                target_env = default_targets[0] if default_targets else TargetEnvironment()

        # Normalize policies
        net_policy = NetworkPolicy(network) if isinstance(network, str) else network
        if execution_policy is None:
            exec_policy = (
                ExecutionPolicy.TRUSTED_LOCAL
                if allow_local_execution
                else ExecutionPolicy.STATIC_ONLY
            )
        else:
            exec_policy = (
                ExecutionPolicy(execution_policy)
                if isinstance(execution_policy, str)
                else execution_policy
            )

        test_cmd = project_test_command or ["pytest"]

        request = ValidationRequest(
            project_path=self.project_path,
            target_environment=target_env,
            runner_type=runner,
            level=level,
            execution_policy=exec_policy,
            network_policy=net_policy,
            allow_local_execution=allow_local_execution,
            allow_project_code=allow_project_code,
            project_test_command=test_cmd,
            timeout_seconds=timeout,
            memory_limit=memory_limit,
            cpu_limit=cpu_limit,
            dry_run=dry_run,
            keep_environment=keep_environment,
            output_directory=Path(output_dir) if output_dir else None,
        )

        orchestrator = ValidationOrchestrator()
        return orchestrator.validate(
            request=request,
            resolution_result=resolution_result,
            discovered_imports=discovered_imports,
        )
