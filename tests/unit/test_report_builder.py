"""Unit tests for ReportBuilder logic and evidence-backed recommendations."""

from __future__ import annotations

from pathlib import Path

from pydeps.models.analysis import ImportAnalysisResult
from pydeps.models.compatibility import (
    CompatibilityMatrix,
    CompatibilityResult,
    CompatibilityStatus,
)
from pydeps.models.dependencies import ResolutionConflict, ResolutionResult
from pydeps.models.mapping import ConfidenceLevel, PackageMappingResult, PackageReport
from pydeps.models.project import Architecture, OperatingSystem, TargetEnvironment
from pydeps.models.structure import ProjectStructure
from pydeps.reporting.report_builder import ReportBuilder
from pydeps.reporting.report_schema import StageStatus


def test_report_builder_handles_missing_stages_gracefully(tmp_path: Path) -> None:
    """ReportBuilder must construct a valid report even when intermediate stages are absent."""
    builder = ReportBuilder()
    report = builder.build_report(
        project_path=tmp_path,
        structure=None,
        analysis=None,
        package_report=None,
        metadata=None,
        compatibility_matrix=None,
        resolution_result=None,
        validation_report=None,
    )

    assert report.overall_status == StageStatus.PASSED
    assert report.source_analysis.total_files == 0
    assert report.resolution.success is False
    assert report.validation.executed is False


def test_report_builder_generates_recommendations_for_unresolved_and_conflicts(
    tmp_path: Path,
) -> None:
    """Builder must produce actionable recommendations for unmapped candidates and conflicts."""
    struct = ProjectStructure(root_path=tmp_path)
    analysis = ImportAnalysisResult(structure=struct)
    pkg_report = PackageReport(
        analysis=analysis,
        mappings=[],
        ambiguous_imports=[
            PackageMappingResult(
                import_name="cv2",
                candidate_distributions=["opencv-python", "opencv-python-headless"],
                confidence=ConfidenceLevel.LOW,
            )
        ],
        unresolved_imports=["unknown_custom_lib"],
        diagnostics=[],
    )

    conflict_res = ResolutionResult(
        success=False,
        structured_conflicts=[
            ResolutionConflict(
                package_name="flask",
                conflicting_requirements=["werkzeug>=3.0", "werkzeug==2.2"],
                source_packages=["project"],
                original_diagnostics="Flask 3.0 requires Werkzeug >= 3.0, but Werkzeug 2.2 is pinned",
            )
        ],
    )

    builder = ReportBuilder()
    report = builder.build_report(
        project_path=tmp_path,
        package_report=pkg_report,
        resolution_result=conflict_res,
    )

    assert report.overall_status == StageStatus.FAILED
    categories = [r.category for r in report.recommendations]
    assert "missing_dependency" in categories
    assert "ambiguity" in categories
    assert "conflict" in categories

    ambig_rec = next(r for r in report.recommendations if r.category == "ambiguity")
    assert "opencv-python" in ambig_rec.evidence[0]


def test_report_builder_generates_compatibility_recommendations(tmp_path: Path) -> None:
    """Builder must produce critical recommendations when compatibility matrix has incompatible outcomes."""
    target = TargetEnvironment(
        python_version="3.8",
        operating_system=OperatingSystem.WINDOWS,
        architecture=Architecture.X86_64,
    )
    matrix = CompatibilityMatrix(
        targets=[target],
        packages=["modern-pkg"],
        matrix={
            target.platform_tag: {
                "modern-pkg": CompatibilityResult(
                    package_name="modern-pkg",
                    package_version="2.0.0",
                    target_environment=target,
                    status=CompatibilityStatus.INCOMPATIBLE,
                    reason="Requires-Python >= 3.10 is unsatisfied by target Python 3.8",
                )
            }
        },
    )

    builder = ReportBuilder()
    report = builder.build_report(
        project_path=tmp_path,
        compatibility_matrix=matrix,
    )

    compat_recs = [r for r in report.recommendations if r.category == "compatibility"]
    assert len(compat_recs) == 1
    assert "Requires-Python >= 3.10" in compat_recs[0].evidence[0]


def test_report_builder_separates_pipeline_and_health_for_partial_mappings(
    tmp_path: Path,
) -> None:
    """When imports remain unmapped, pipeline_status can pass while dependency_health is partial."""
    from pydeps.reporting.report_schema import DependencyHealthStatus

    struct = ProjectStructure(root_path=tmp_path)
    analysis = ImportAnalysisResult(structure=struct)
    pkg_report = PackageReport(
        analysis=analysis,
        mappings=[],
        ambiguous_imports=[],
        unresolved_imports=["custom_internal_module"],
        diagnostics=[],
    )

    builder = ReportBuilder()
    report = builder.build_report(
        project_path=tmp_path,
        structure=struct,
        analysis=analysis,
        package_report=pkg_report,
        stage_statuses={
            "scan": StageStatus.PASSED,
            "imports": StageStatus.PASSED,
            "mapping": StageStatus.PASSED,
        },
    )

    # Workflow completed successfully
    assert report.pipeline_status == StageStatus.PASSED
    # But dependency health is partial due to unmapped candidates
    assert report.dependency_health_status == DependencyHealthStatus.PARTIAL
    # Runtime validation was not executed
    assert report.runtime_validation_status == StageStatus.SKIPPED
    # Overall status reflects partial health
    assert report.overall_status == StageStatus.PARTIAL
