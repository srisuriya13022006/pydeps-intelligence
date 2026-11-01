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
from pydeps.reporting.report_schema import DiagnosticReport
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

    def analyze(
        self,
        structure_or_python_version: ProjectStructure | str | None = None,
        python_version: str = "3.11",
    ) -> ImportAnalysisResult:
        """Scan the project and perform static AST import extraction and classification."""
        if isinstance(structure_or_python_version, ProjectStructure):
            structure = structure_or_python_version
            target_py = python_version
        elif isinstance(structure_or_python_version, str):
            structure = self.scan()
            target_py = structure_or_python_version
        else:
            structure = self.scan()
            target_py = python_version
        return self.analyzer.analyze_project(structure, target_python_version=target_py)

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

    def diagnose(
        self,
        targets: Sequence[TargetEnvironment] | TargetEnvironment | None = None,
        mode: ResolutionMode | str = ResolutionMode.UNIVERSAL,
        strategy: ResolutionStrategy | str = ResolutionStrategy.LATEST_COMPATIBLE,
        backend: str = "uv",
        offline: bool | None = None,
        run_validation: bool = False,
        validation_runner: str = "local",
        validation_level: str = "install",
        allow_local_execution: bool = False,
        allow_project_code: bool = False,
        output_dir: Path | str | None = None,
        export_html: bool = True,
        cli_command: str | None = None,
    ) -> DiagnosticReport:
        """Run the end-to-end unified diagnosis pipeline and produce a versioned DiagnosticReport."""
        import time

        from pydeps.reporting.html_renderer import HtmlRenderer
        from pydeps.reporting.json_renderer import JsonRenderer
        from pydeps.reporting.report_builder import ReportBuilder
        from pydeps.reporting.report_schema import StageStatus

        is_offline = self.offline if offline is None else offline
        durations: dict[str, float] = {}
        statuses: dict[str, StageStatus] = {}
        diagnostics: dict[str, list[str]] = {}

        target_list: list[TargetEnvironment] = []
        if targets is None:
            target_list = self._build_default_targets()
        elif isinstance(targets, TargetEnvironment):
            target_list = [targets]
        else:
            target_list = list(targets)

        # Stage 1: Scan
        t0 = time.perf_counter()
        structure: ProjectStructure | None = None
        try:
            structure = self.scan()
            statuses["scan"] = StageStatus.PASSED
        except Exception as exc:
            statuses["scan"] = StageStatus.FAILED
            diagnostics.setdefault("scan", []).append(f"Scanning failed: {exc}")
        finally:
            durations["scan"] = time.perf_counter() - t0

        # Stage 2: Imports
        t0 = time.perf_counter()
        analysis: ImportAnalysisResult | None = None
        if structure:
            try:
                analysis = self.analyze(structure)
                statuses["imports"] = StageStatus.PASSED
            except Exception as exc:
                statuses["imports"] = StageStatus.FAILED
                diagnostics.setdefault("imports", []).append(f"Import analysis failed: {exc}")
            finally:
                durations["imports"] = time.perf_counter() - t0
        else:
            statuses["imports"] = StageStatus.SKIPPED

        # Stage 3: Package Mapping
        t0 = time.perf_counter()
        package_report: PackageReport | None = None
        if analysis:
            try:
                package_report = self.resolve_packages(analysis)
                if package_report.ambiguous_imports:
                    statuses["mapping"] = StageStatus.PARTIAL
                    diagnostics.setdefault("mapping", []).append(
                        f"Identified {len(package_report.ambiguous_imports)} ambiguous import mappings."
                    )
                else:
                    statuses["mapping"] = StageStatus.PASSED
            except Exception as exc:
                statuses["mapping"] = StageStatus.FAILED
                diagnostics.setdefault("mapping", []).append(f"Package mapping failed: {exc}")
            finally:
                durations["mapping"] = time.perf_counter() - t0
        else:
            statuses["mapping"] = StageStatus.SKIPPED

        # Stage 4: Metadata Retrieval
        t0 = time.perf_counter()
        metadata: dict[str, MetadataResult] | None = None
        if package_report and package_report.selected_distributions:
            try:
                metadata = self.fetch_metadata(package_report, offline=is_offline)
                statuses["metadata"] = StageStatus.PASSED
            except Exception as exc:
                statuses["metadata"] = StageStatus.FAILED
                diagnostics.setdefault("metadata", []).append(f"Metadata retrieval failed: {exc}")
            finally:
                durations["metadata"] = time.perf_counter() - t0
        else:
            statuses["metadata"] = StageStatus.SKIPPED

        # Stage 5: Compatibility Evaluation
        t0 = time.perf_counter()
        compat_matrix: CompatibilityMatrix | None = None
        if metadata:
            try:
                compat_matrix = self.check_compatibility(metadata=metadata, targets=target_list)
                statuses["compatibility"] = StageStatus.PASSED
            except Exception as exc:
                statuses["compatibility"] = StageStatus.FAILED
                diagnostics.setdefault("compatibility", []).append(
                    f"Compatibility evaluation failed: {exc}"
                )
            finally:
                durations["compatibility"] = time.perf_counter() - t0
        else:
            statuses["compatibility"] = StageStatus.SKIPPED

        # Stage 6: Dependency Resolution
        t0 = time.perf_counter()
        resolution_result: ResolutionResult | None = None
        strat_val = strategy.replace("_", "-") if isinstance(strategy, str) else strategy
        mode_val = mode.replace("_", "-") if isinstance(mode, str) else mode
        has_manifests = (
            (self.project_path / "pyproject.toml").is_file()
            or (self.project_path / "requirements.txt").is_file()
            or (self.project_path / "setup.py").is_file()
        )
        if package_report and (package_report.selected_distributions or has_manifests):
            try:
                resolution_result = self.resolve_dependencies(
                    package_report=package_report,
                    analysis=analysis,
                    metadata=metadata,
                    mode=mode_val,
                    strategy=strat_val,
                    backend=backend,
                    targets=target_list,
                    offline=is_offline,
                )
                if resolution_result.success:
                    statuses["resolution"] = StageStatus.PASSED
                else:
                    statuses["resolution"] = StageStatus.FAILED
                    if resolution_result.structured_conflicts:
                        for sc in resolution_result.structured_conflicts:
                            diagnostics.setdefault("resolution", []).append(
                                f"Conflict on '{sc.package_name}': {sc.description}"
                            )
                    elif resolution_result.conflicts:
                        for conf_str in resolution_result.conflicts:
                            diagnostics.setdefault("resolution", []).append(str(conf_str))
            except Exception as exc:
                statuses["resolution"] = StageStatus.FAILED
                diagnostics.setdefault("resolution", []).append(
                    f"Dependency resolution failed: {exc}"
                )
            finally:
                durations["resolution"] = time.perf_counter() - t0
        elif package_report:
            statuses["resolution"] = StageStatus.PASSED
            resolution_result = ResolutionResult(
                success=True,
                mode=mode_val,
                strategy=strat_val,
                backend=backend,
            )
            durations["resolution"] = 0.0
        else:
            statuses["resolution"] = StageStatus.SKIPPED

        # Stage 7: Runtime Validation (Optional)
        t0 = time.perf_counter()
        validation_report: ValidationReport | None = None
        if run_validation and resolution_result and resolution_result.success:
            try:
                validation_report = self.validate(
                    resolution_result=resolution_result,
                    runner=validation_runner,
                    level=validation_level,
                    allow_local_execution=allow_local_execution,
                    allow_project_code=allow_project_code,
                    discovered_imports=analysis.imports if analysis else None,
                )
                from pydeps.models.validation import ValidationStatus

                if validation_report.status == ValidationStatus.PASSED:
                    statuses["validation"] = StageStatus.PASSED
                elif validation_report.status == ValidationStatus.BLOCKED_BY_POLICY:
                    statuses["validation"] = StageStatus.BLOCKED_BY_POLICY
                else:
                    statuses["validation"] = StageStatus.FAILED
            except Exception as exc:
                statuses["validation"] = StageStatus.FAILED
                diagnostics.setdefault("validation", []).append(f"Runtime validation failed: {exc}")
            finally:
                durations["validation"] = time.perf_counter() - t0
        else:
            statuses["validation"] = StageStatus.SKIPPED

        # Build comprehensive report
        builder = ReportBuilder()
        report = builder.build_report(
            project_path=self.project_path,
            config=self.config,
            structure=structure,
            analysis=analysis,
            package_report=package_report,
            metadata=metadata,
            compatibility_matrix=compat_matrix,
            resolution_result=resolution_result,
            validation_report=validation_report,
            stage_durations=durations,
            stage_statuses=statuses,
            stage_diagnostics=diagnostics,
            cli_command=cli_command,
            offline=is_offline,
        )

        # Artifact export
        if output_dir:
            out_path = Path(output_dir)
            JsonRenderer.export_artifacts(report, out_path)
            if export_html:
                HtmlRenderer.export_html(report, out_path / "index.html")

        return report
