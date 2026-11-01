"""Builder for unified DiagnosticReport from pipeline stage artifacts."""

from __future__ import annotations

import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydeps_intelligence._version import __version__
from pydeps_intelligence.metadata.metadata_models import PackageRelease
from pydeps_intelligence.models.analysis import ImportAnalysisResult
from pydeps_intelligence.models.compatibility import CompatibilityMatrix, CompatibilityStatus
from pydeps_intelligence.models.dependencies import ResolutionResult
from pydeps_intelligence.models.mapping import PackageReport
from pydeps_intelligence.models.project import ProjectConfig, TargetEnvironment
from pydeps_intelligence.models.structure import ProjectStructure
from pydeps_intelligence.models.validation import ValidationReport, ValidationStatus
from pydeps_intelligence.reporting.report_schema import (
    CompatibilitySection,
    DependencyHealthStatus,
    DiagnosticReport,
    ExecutionEnvironmentInfo,
    PackageIntelligenceSection,
    ProjectInfo,
    ProvenanceInfo,
    RecommendationItem,
    RecommendationSeverity,
    ResolutionSection,
    SourceAnalysisSection,
    StageResultSummary,
    StageStatus,
    ValidationSection,
)


class ReportBuilder:
    """Builds a complete, strongly-typed DiagnosticReport from pipeline outputs."""

    def build_report(
        self,
        project_path: Path | str,
        config: ProjectConfig | None = None,
        structure: ProjectStructure | None = None,
        analysis: ImportAnalysisResult | None = None,
        package_report: PackageReport | None = None,
        metadata: dict[str, Any] | None = None,
        compatibility_matrix: CompatibilityMatrix | None = None,
        resolution_result: ResolutionResult | None = None,
        validation_report: ValidationReport | None = None,
        stage_durations: dict[str, float] | None = None,
        stage_statuses: dict[str, StageStatus] | None = None,
        stage_diagnostics: dict[str, list[str]] | None = None,
        cli_command: str | None = None,
        offline: bool = False,
    ) -> DiagnosticReport:
        """Construct the unified diagnostic report."""
        proj_path = Path(project_path).resolve()
        durations = stage_durations or {}
        statuses = stage_statuses or {}
        diag_map = stage_diagnostics or {}

        # 1. Project Information
        proj_name = proj_path.name
        file_count = len(structure.source_files) if structure else 0
        test_file_count = (
            sum(
                1
                for p in structure.source_files
                if p.name.startswith("test_")
                or p.name.endswith("_test.py")
                or "tests" in [part.lower() for part in p.parts]
            )
            if structure
            else 0
        )
        total_loc = 0
        if structure:
            for p in structure.source_files:
                try:
                    if p.is_file():
                        total_loc += sum(1 for _ in p.open("rb"))
                except (OSError, UnicodeDecodeError):
                    pass

        project_info = ProjectInfo(
            name=proj_name,
            path=str(proj_path),
            analysis_timestamp=datetime.now(timezone.utc),
            file_count=file_count,
            test_file_count=test_file_count,
            lines_of_code=total_loc,
        )

        # 2. Execution Environment Info
        exec_info = ExecutionEnvironmentInfo(
            operating_system=platform.system().lower(),
            architecture=platform.machine().lower(),
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            python_implementation=platform.python_implementation(),
            offline_mode=offline,
        )

        # 3. Target Environments
        targets: list[TargetEnvironment] = []
        if compatibility_matrix and compatibility_matrix.targets:
            targets = list(compatibility_matrix.targets)
        elif config:
            for py in config.target_python_versions:
                for o in config.target_operating_systems:
                    for a in config.target_architectures:
                        for i in config.target_implementations:
                            targets.append(
                                TargetEnvironment(
                                    python_version=py,
                                    operating_system=o,
                                    architecture=a,
                                    implementation=i,
                                )
                            )

        # 4. Source Analysis Section
        source_section = SourceAnalysisSection()
        if analysis:
            files: list[Any] = []
            if hasattr(analysis, "analyzed_files"):
                files = analysis.analyzed_files
            elif hasattr(analysis, "structure") and analysis.structure:
                files = getattr(analysis.structure, "source_files", [])
            elif structure:
                files = getattr(structure, "source_files", [])

            source_section.total_files = len(files)
            source_section.scanned_files = [str(f) for f in files]

            all_imps = getattr(analysis, "all_imports", [])
            source_section.total_imports = (
                len(all_imps) if all_imps else getattr(analysis, "total_imports", 0)
            )

            def _extract_names(items: list[Any]) -> list[str]:
                res: set[str] = set()
                for it in items:
                    if hasattr(it, "module_name"):
                        res.add(it.module_name)
                    elif hasattr(it, "import_name"):
                        res.add(it.import_name)
                    elif isinstance(it, str):
                        res.add(it)
                return sorted(res)

            source_section.standard_library = _extract_names(
                getattr(analysis, "standard_library_imports", [])
            )
            source_section.local_imports = _extract_names(getattr(analysis, "local_imports", []))

            ext_candidates = getattr(analysis, "external_candidate_imports", None)
            if ext_candidates is None:
                ext_candidates = getattr(analysis, "external_candidates", [])
            source_section.external_candidates = _extract_names(ext_candidates)

            dyn_list = []
            for d in getattr(analysis, "dynamic_imports", []):
                if hasattr(d, "module_name"):
                    dyn_list.append(
                        {
                            "module": d.module_name,
                            "file": str(getattr(d, "source_file", "")),
                            "line": getattr(d, "line_number", 0),
                        }
                    )
                elif isinstance(d, dict):
                    dyn_list.append(d)
            source_section.dynamic_imports = dyn_list

            syn_errors = getattr(analysis, "syntax_errors", None)
            if syn_errors is None:
                syn_errors = [
                    d for d in getattr(analysis, "diagnostics", []) if "syntax" in d.lower()
                ]
            source_section.syntax_errors = [str(s) for s in syn_errors]

        # 5. Package Intelligence Section
        pkg_section = PackageIntelligenceSection()
        if package_report:
            pkg_section.mappings = {
                m.import_name: m.selected_distribution
                for m in package_report.mappings
                if m.selected_distribution
            }
            pkg_section.confidence_levels = {
                m.import_name: m.confidence.value for m in package_report.mappings
            }
            pkg_section.ambiguous_mappings = {
                m.import_name: list(m.candidate_distributions)
                for m in package_report.ambiguous_imports
            }
            pkg_section.unresolved_candidates = sorted(package_report.unresolved_imports)
        if metadata:
            pkg_section.metadata_summary = {}
            for pkg, res in metadata.items():
                rel = getattr(res, "metadata", None)
                if rel is None and isinstance(res, PackageRelease):
                    rel = res
                ver = getattr(res, "version", None) or (rel.version if rel else "unknown")
                req_py = rel.requires_python if rel else None
                artifacts = getattr(rel, "release_files", None) or getattr(rel, "artifacts", [])
                src = getattr(res, "source", None)
                if hasattr(src, "value"):
                    src = src.value
                elif not src:
                    src = getattr(rel, "metadata_source", "cache") if rel else "cache"
                pkg_section.metadata_summary[pkg] = {
                    "version": str(ver),
                    "requires_python": req_py,
                    "wheels_count": len(artifacts),
                    "source": str(src),
                }

        # 6. Compatibility Section
        compat_section = CompatibilitySection()
        if compatibility_matrix:
            compat_section.evaluated_targets = [
                {
                    "id": t.platform_tag,
                    "python_version": t.python_version,
                    "operating_system": t.operating_system.value,
                    "architecture": t.architecture.value,
                    "implementation": t.implementation.value,
                }
                for t in compatibility_matrix.targets
            ]
            compat_section.evaluated_packages = sorted(compatibility_matrix.packages)

            matrix_data: dict[str, dict[str, dict[str, Any]]] = {}
            comp_cnt = 0
            incomp_cnt = 0
            unver_cnt = 0

            for t_id, pkg_map in compatibility_matrix.matrix.items():
                matrix_data[t_id] = {}
                for pkg_name, res in pkg_map.items():
                    matrix_data[t_id][pkg_name] = {
                        "status": res.status.value,
                        "reason": res.reason,
                        "python_compatible": getattr(res, "python_constraint_compatible", None),
                        "wheel_candidates": getattr(res, "wheel_candidates", []),
                    }
                    if res.status == CompatibilityStatus.COMPATIBLE:
                        comp_cnt += 1
                    elif res.status == CompatibilityStatus.INCOMPATIBLE:
                        incomp_cnt += 1
                    else:
                        unver_cnt += 1

            compat_section.matrix = matrix_data
            compat_section.compatible_count = comp_cnt
            compat_section.incompatible_count = incomp_cnt
            compat_section.unverified_count = unver_cnt

        # 7. Resolution Section
        res_section = ResolutionSection()
        if resolution_result:
            res_section.success = resolution_result.success
            res_section.mode = (
                resolution_result.mode.value
                if hasattr(resolution_result.mode, "value")
                else str(resolution_result.mode)
            )
            res_section.strategy = (
                resolution_result.strategy.value
                if hasattr(resolution_result.strategy, "value")
                else str(resolution_result.strategy)
            )
            direct_pkgs: list[str] = []
            transitive_pkgs: list[str] = []
            pinned_map: dict[str, str] = {}
            from pydeps_intelligence.models.dependencies import DependencyType

            if resolution_result.graph:
                direct_pkgs = list(resolution_result.graph.roots)
                for pkg_name, pkg_obj in resolution_result.graph.packages.items():
                    pinned_map[pkg_name] = pkg_obj.version
                    if pkg_obj.dependency_type == DependencyType.TRANSITIVE:
                        transitive_pkgs.append(pkg_name)
                    elif pkg_name not in direct_pkgs:
                        direct_pkgs.append(pkg_name)
            elif resolution_result.resolved_dependencies:
                for dep in resolution_result.resolved_dependencies:
                    pinned_map[dep.name] = dep.version_specifier or "*"
                    if dep.dependency_type == DependencyType.TRANSITIVE:
                        transitive_pkgs.append(dep.name)
                    else:
                        direct_pkgs.append(dep.name)

            res_section.direct_packages = sorted(direct_pkgs)
            res_section.transitive_packages = sorted(transitive_pkgs)
            res_section.pinned_versions = pinned_map

            if resolution_result.structured_conflicts:
                res_section.conflicts = [
                    {
                        "package": c.package_name,
                        "description": ", ".join(c.conflicting_requirements)
                        or c.original_diagnostics,
                        "required_by": list(c.source_packages),
                        "conflicting_versions": list(c.conflicting_requirements),
                    }
                    for c in resolution_result.structured_conflicts
                ]
            elif resolution_result.conflicts:
                res_section.conflicts = [
                    {
                        "package": "conflict",
                        "description": str(c),
                        "required_by": [],
                        "conflicting_versions": [],
                    }
                    for c in resolution_result.conflicts
                ]
            if resolution_result.graph and hasattr(resolution_result.graph, "edges"):
                res_section.dependency_graph = {
                    node: list(edges) for node, edges in resolution_result.graph.edges.items()
                }

        # 8. Validation Section
        val_section = ValidationSection()
        if validation_report:
            val_section.executed = True
            val_section.status = (
                StageStatus.PASSED
                if validation_report.status == ValidationStatus.PASSED
                else StageStatus(validation_report.status.value)
                if validation_report.status.value in StageStatus._value2member_map_
                else StageStatus.FAILED
            )
            val_section.runner_type = validation_report.runner_type
            val_section.isolation_level = validation_report.isolation_level
            val_section.execution_policy = (
                validation_report.execution_policy.value
                if hasattr(validation_report.execution_policy, "value")
                else str(validation_report.execution_policy)
            )
            val_section.installed_packages = dict(validation_report.installed_packages)
            val_section.stages = {
                k: {
                    "stage": v.stage.value if hasattr(v.stage, "value") else str(v.stage),
                    "status": v.status.value if hasattr(v.status, "value") else str(v.status),
                    "exit_code": v.exit_code,
                    "duration": v.duration_seconds,
                }
                for k, v in validation_report.stages.items()
            }
            # Collect import tests
            import_stage = validation_report.stages.get("import_test")
            if import_stage and import_stage.import_results:
                val_section.import_results = [
                    {
                        "module": r.module_name,
                        "distribution": r.distribution_name,
                        "status": r.status.value,
                        "duration": r.duration_seconds,
                        "error": r.error_traceback,
                    }
                    for r in import_stage.import_results
                ]
            # Collect project test results
            proj_stage = validation_report.stages.get("project_test")
            if proj_stage and proj_stage.project_test_result:
                r = proj_stage.project_test_result
                val_section.project_test_results = {
                    "status": r.status.value,
                    "command": r.command,
                    "exit_code": r.exit_code,
                    "duration": r.duration_seconds,
                }
            val_section.diagnostics = list(validation_report.diagnostics)

        # 9. Recommendations Engine
        recommendations = self._generate_recommendations(
            analysis=analysis,
            package_report=package_report,
            compatibility_matrix=compatibility_matrix,
            resolution_result=resolution_result,
            validation_report=validation_report,
        )

        # 10. Stage Summaries
        stage_names = [
            "scan",
            "imports",
            "mapping",
            "metadata",
            "compatibility",
            "resolution",
            "validation",
        ]
        stage_results: dict[str, StageResultSummary] = {}
        all_diagnostics: list[str] = []

        for name in stage_names:
            status = statuses.get(name, StageStatus.SKIPPED)
            dur = durations.get(name, 0.0)
            diags = diag_map.get(name, [])
            all_diagnostics.extend(diags)

            stage_results[name] = StageResultSummary(
                stage_name=name,
                status=status,
                duration_seconds=dur,
                diagnostics=diags,
            )

        # Determine 1: pipeline_status (did the diagnostic workflow stages execute cleanly?)
        pipeline_status = StageStatus.PASSED
        if any(s.status == StageStatus.FAILED for s in stage_results.values()):
            pipeline_status = StageStatus.FAILED
        elif any(s.status == StageStatus.BLOCKED_BY_POLICY for s in stage_results.values()):
            pipeline_status = StageStatus.BLOCKED_BY_POLICY
        elif any(s.status == StageStatus.PARTIAL for s in stage_results.values()):
            pipeline_status = StageStatus.PARTIAL

        # Determine 2: runtime_validation_status (exact outcome of runtime validation)
        runtime_validation_status = val_section.status

        # Determine 3: dependency_health_status (evidence-backed dependency status)
        has_resolution_conflicts = bool(res_section.conflicts) or (
            resolution_result is not None and not resolution_result.success
        )
        has_compat_failures = compat_section.incompatible_count > 0
        has_validation_failure = runtime_validation_status == StageStatus.FAILED

        has_unresolved_candidates = bool(pkg_section.unresolved_candidates)
        has_ambiguous_mappings = bool(pkg_section.ambiguous_mappings)
        has_unverified_compat = (
            compat_section.unverified_count > 0
            and compat_section.compatible_count == 0
            and bool(pkg_section.mappings)
        )

        if has_resolution_conflicts or has_compat_failures or has_validation_failure:
            dependency_health_status = DependencyHealthStatus.PROBLEMATIC
        elif has_unresolved_candidates or has_ambiguous_mappings or has_unverified_compat:
            dependency_health_status = DependencyHealthStatus.PARTIAL
        elif (
            source_section.total_files == 0
            and not pkg_section.mappings
            and not res_section.pinned_versions
        ):
            dependency_health_status = DependencyHealthStatus.UNKNOWN
        else:
            dependency_health_status = DependencyHealthStatus.HEALTHY

        # Determine overall_status (aligned with pipeline execution and dependency health)
        if (
            pipeline_status == StageStatus.FAILED
            or dependency_health_status == DependencyHealthStatus.PROBLEMATIC
        ):
            overall_status = StageStatus.FAILED
        elif pipeline_status == StageStatus.BLOCKED_BY_POLICY:
            overall_status = StageStatus.BLOCKED_BY_POLICY
        elif (
            pipeline_status == StageStatus.PARTIAL
            or dependency_health_status == DependencyHealthStatus.PARTIAL
        ):
            overall_status = StageStatus.PARTIAL
        else:
            overall_status = StageStatus.PASSED

        # 11. Provenance
        provenance = ProvenanceInfo(
            cli_command=cli_command,
            pydeps_version=__version__,
            schema_version="1.0.0",
        )

        return DiagnosticReport(
            schema_version="1.0.0",
            tool_version=__version__,
            pipeline_status=pipeline_status,
            dependency_health_status=dependency_health_status,
            runtime_validation_status=runtime_validation_status,
            overall_status=overall_status,
            project_information=project_info,
            execution_environment=exec_info,
            target_environments=targets,
            stage_results=stage_results,
            source_analysis=source_section,
            package_intelligence=pkg_section,
            compatibility=compat_section,
            resolution=res_section,
            validation=val_section,
            recommendations=recommendations,
            diagnostics=sorted(list(set(all_diagnostics))),
            provenance=provenance,
        )

    def _generate_recommendations(
        self,
        analysis: ImportAnalysisResult | None,
        package_report: PackageReport | None,
        compatibility_matrix: CompatibilityMatrix | None,
        resolution_result: ResolutionResult | None,
        validation_report: ValidationReport | None,
    ) -> list[RecommendationItem]:
        """Produce concrete, evidence-backed developer guidance."""
        items: list[RecommendationItem] = []

        # 1. Unresolved Candidates
        if package_report and package_report.unresolved_imports:
            items.append(
                RecommendationItem(
                    category="missing_dependency",
                    severity=RecommendationSeverity.WARNING,
                    title=f"Unresolved external import candidates ({len(package_report.unresolved_imports)})",
                    description=(
                        "Static AST analysis identified imports that do not correspond to standard library "
                        "modules, local project files, or known distribution packages."
                    ),
                    evidence=[
                        f"Unresolved candidate: '{c}'"
                        for c in sorted(package_report.unresolved_imports)
                    ],
                    actionable_remedy=(
                        "Configure an explicit mapping in pyproject.toml [tool.pydeps.mappings] "
                        "or ensure the providing package is declared."
                    ),
                )
            )

        # 2. Ambiguous Mappings
        if package_report and package_report.ambiguous_imports:
            evidence = []
            for m in package_report.ambiguous_imports:
                evidence.append(
                    f"Import '{m.import_name}' maps to multiple candidates: {list(m.candidate_distributions)}"
                )

            items.append(
                RecommendationItem(
                    category="ambiguity",
                    severity=RecommendationSeverity.WARNING,
                    title=f"Ambiguous import mappings ({len(package_report.ambiguous_imports)})",
                    description=(
                        "Several imports correspond to multiple competing distributions on PyPI. "
                        "To preserve reproducibility, PyDeps will never guess or silently select one."
                    ),
                    evidence=evidence,
                    actionable_remedy=(
                        "Specify the intended distribution explicitly via [tool.pydeps.mappings] in pyproject.toml."
                    ),
                )
            )

        # 3. Compatibility Incompatibilities
        if compatibility_matrix:
            incompat_evidence: list[str] = []
            for t_id, pkg_map in compatibility_matrix.matrix.items():
                for pkg_name, res in pkg_map.items():
                    if res.status == CompatibilityStatus.INCOMPATIBLE:
                        incompat_evidence.append(
                            f"Package '{pkg_name}' on target '{t_id}': {res.reason}"
                        )

            if incompat_evidence:
                items.append(
                    RecommendationItem(
                        category="compatibility",
                        severity=RecommendationSeverity.CRITICAL,
                        title=f"Platform compatibility failures detected ({len(incompat_evidence)})",
                        description=(
                            "One or more packages do not meet target platform requirements (e.g. Python version "
                            "specifier mismatch or missing compatible binary wheels)."
                        ),
                        evidence=incompat_evidence[:10],
                        actionable_remedy=(
                            "Adjust target environment constraints or upgrade packages to versions providing "
                            "binary wheel tags matching your target platforms."
                        ),
                    )
                )

        # 4. Resolution Conflicts
        if resolution_result and not resolution_result.success:
            if resolution_result.structured_conflicts:
                conflict_evidence = [
                    f"Conflict on '{c.package_name}': {', '.join(c.conflicting_requirements)} (required by {list(c.source_packages)})"
                    for c in resolution_result.structured_conflicts
                ]
            else:
                conflict_evidence = [f"Conflict: {c}" for c in resolution_result.conflicts]
            items.append(
                RecommendationItem(
                    category="conflict",
                    severity=RecommendationSeverity.CRITICAL,
                    title=f"Dependency resolution conflicts detected ({len(resolution_result.conflicts)})",
                    description=(
                        "The resolver encountered mutually exclusive version constraints that could not be satisfied."
                    ),
                    evidence=conflict_evidence,
                    actionable_remedy=(
                        "Loosen version constraints in pyproject.toml or requirements.txt, or evaluate "
                        "per-target resolution mode."
                    ),
                )
            )

        # 5. Validation Execution Policy
        if validation_report and validation_report.status == ValidationStatus.BLOCKED_BY_POLICY:
            items.append(
                RecommendationItem(
                    category="security",
                    severity=RecommendationSeverity.INFO,
                    title="Runtime validation blocked by trust policy",
                    description=(
                        "Execution was restricted under 'static_only' policy because explicit authorization "
                        "was not provided."
                    ),
                    evidence=list(validation_report.diagnostics),
                    actionable_remedy=(
                        "Run with '--allow-local-execution' if you explicitly trust the repository, "
                        "or use '--runner docker' for container isolation."
                    ),
                )
            )

        return items
