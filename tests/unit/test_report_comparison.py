"""Unit tests for ReportComparator regression and diff detection."""

from __future__ import annotations

from pydeps_intelligence.models.project import Architecture, OperatingSystem, TargetEnvironment
from pydeps_intelligence.reporting.report_comparison import ReportComparator
from pydeps_intelligence.reporting.report_schema import (
    CompatibilitySection,
    DiagnosticReport,
    ExecutionEnvironmentInfo,
    PackageIntelligenceSection,
    ProjectInfo,
    ResolutionSection,
    SourceAnalysisSection,
    StageStatus,
)


def _build_stub_report(
    name: str,
    imports: list[str],
    mappings: dict[str, str],
    pinned: dict[str, str],
    compat_matrix: dict[str, dict[str, dict[str, str]]],
    targets: list[TargetEnvironment] | None = None,
) -> DiagnosticReport:
    """Helper to construct stub DiagnosticReports for comparison testing."""
    target_list = targets or [
        TargetEnvironment(
            python_version="3.11",
            operating_system=OperatingSystem.LINUX,
            architecture=Architecture.X86_64,
        )
    ]
    return DiagnosticReport(
        schema_version="1.0.0",
        tool_version="0.1.0",
        overall_status=StageStatus.PASSED,
        project_information=ProjectInfo(name=name, path="/tmp/stub"),
        execution_environment=ExecutionEnvironmentInfo(
            operating_system="linux",
            architecture="x86_64",
            python_version="3.11",
        ),
        target_environments=target_list,
        source_analysis=SourceAnalysisSection(external_candidates=imports),
        package_intelligence=PackageIntelligenceSection(mappings=mappings),
        resolution=ResolutionSection(success=True, pinned_versions=pinned),
        compatibility=CompatibilitySection(matrix=compat_matrix),
    )


def test_comparator_detects_regressions_and_diffs() -> None:
    """ReportComparator must detect newly added/removed imports and compatibility regressions."""
    report_a = _build_stub_report(
        name="project-v1",
        imports=["requests", "urllib3"],
        mappings={"requests": "requests", "urllib3": "urllib3"},
        pinned={"requests": "2.28.0", "urllib3": "1.26.0"},
        compat_matrix={
            "linux-x86_64-cpython-py3.11": {
                "requests": {"status": "compatible"},
            }
        },
    )

    report_b = _build_stub_report(
        name="project-v2",
        imports=["requests", "httpx"],  # urllib3 removed, httpx added
        mappings={"requests": "requests", "httpx": "httpx"},
        pinned={"requests": "2.31.0", "httpx": "0.24.0"},
        compat_matrix={
            "linux-x86_64-cpython-py3.11": {
                "requests": {
                    "status": "incompatible",
                    "reason": "Binary wheel missing for target",
                },
            }
        },
    )

    comparison = ReportComparator.compare(report_a, report_b)

    assert comparison.new_imports == ["httpx"]
    assert comparison.removed_imports == ["urllib3"]
    assert len(comparison.version_changes) == 1
    assert comparison.version_changes[0].package == "requests"
    assert comparison.version_changes[0].old_version == "2.28.0"
    assert comparison.version_changes[0].new_version == "2.31.0"

    assert len(comparison.new_compatibility_failures) == 1
    assert comparison.new_compatibility_failures[0].package == "requests"
    assert comparison.has_regressions is True


def test_comparator_identifies_target_environment_shifts() -> None:
    """When target environments differ, comparison must flag target shifts in diagnostics."""
    target_linux = [
        TargetEnvironment(
            python_version="3.11",
            operating_system=OperatingSystem.LINUX,
            architecture=Architecture.X86_64,
        )
    ]
    target_windows = [
        TargetEnvironment(
            python_version="3.11",
            operating_system=OperatingSystem.WINDOWS,
            architecture=Architecture.X86_64,
        )
    ]

    report_a = _build_stub_report(
        name="linux-run",
        imports=["requests"],
        mappings={"requests": "requests"},
        pinned={"requests": "2.31.0"},
        compat_matrix={},
        targets=target_linux,
    )

    report_b = _build_stub_report(
        name="windows-run",
        imports=["requests"],
        mappings={"requests": "requests"},
        pinned={"requests": "2.31.0"},
        compat_matrix={},
        targets=target_windows,
    )

    comparison = ReportComparator.compare(report_a, report_b)

    assert comparison.target_environments_match is False
    assert len(comparison.target_differences) > 0
    assert any("Target environment configurations differ" in d for d in comparison.diagnostics)


def test_comparator_normalizes_distribution_identity() -> None:
    """Package version comparisons must use normalized distribution names (PEP 503)."""
    report_a = _build_stub_report(
        name="a",
        imports=["pillow"],
        mappings={"pillow": "Pillow"},
        pinned={"Pillow": "10.0.0"},
        compat_matrix={},
    )
    report_b = _build_stub_report(
        name="b",
        imports=["pillow"],
        mappings={"pillow": "pillow"},
        pinned={"pillow": "10.1.0"},
        compat_matrix={},
    )

    comparison = ReportComparator.compare(report_a, report_b)
    # Must identify as the same package with a version change
    assert len(comparison.version_changes) == 1
    assert comparison.version_changes[0].old_version == "10.0.0"
    assert comparison.version_changes[0].new_version == "10.1.0"


def test_comparator_distinguishes_unverified_from_incompatible() -> None:
    """An unverified status change must not be counted as a compatibility failure regression."""
    report_a = _build_stub_report(
        name="a",
        imports=["foo"],
        mappings={"foo": "foo"},
        pinned={"foo": "1.0.0"},
        compat_matrix={"linux-x86_64-cpython-py3.11": {"foo": {"status": "compatible"}}},
    )
    report_b = _build_stub_report(
        name="b",
        imports=["foo"],
        mappings={"foo": "foo"},
        pinned={"foo": "1.0.0"},
        compat_matrix={"linux-x86_64-cpython-py3.11": {"foo": {"status": "unverified"}}},
    )

    comparison = ReportComparator.compare(report_a, report_b)
    assert len(comparison.new_compatibility_failures) == 0
    assert len(comparison.unverified_compatibility_changes) == 1
    assert comparison.has_regressions is False


def test_comparator_records_schema_and_tool_version_differences() -> None:
    """Schema and tool version shifts must be explicitly recorded in comparison report."""
    report_a = _build_stub_report(
        name="a",
        imports=[],
        mappings={},
        pinned={},
        compat_matrix={},
    )
    report_a.schema_version = "1.0.0"
    report_a.tool_version = "0.1.0"

    report_b = _build_stub_report(
        name="b",
        imports=[],
        mappings={},
        pinned={},
        compat_matrix={},
    )
    report_b.schema_version = "1.1.0"
    report_b.tool_version = "0.2.0"

    comparison = ReportComparator.compare(report_a, report_b)
    assert comparison.schema_version_mismatch is True
    assert comparison.tool_version_mismatch is True
    assert any("schema version mismatch" in d.lower() for d in comparison.diagnostics)
    assert any("tool version difference" in d.lower() for d in comparison.diagnostics)


def test_comparator_reports_added_and_removed_targets_separately() -> None:
    """Added and removed targets must be categorized separately from package regressions."""
    t_linux = TargetEnvironment(
        python_version="3.11",
        operating_system=OperatingSystem.LINUX,
        architecture=Architecture.X86_64,
    )
    t_macos = TargetEnvironment(
        python_version="3.11",
        operating_system=OperatingSystem.MACOS,
        architecture=Architecture.AARCH64,
    )

    report_a = _build_stub_report(
        name="a",
        imports=["requests"],
        mappings={"requests": "requests"},
        pinned={"requests": "2.31.0"},
        compat_matrix={t_linux.platform_tag: {"requests": {"status": "compatible"}}},
        targets=[t_linux],
    )
    report_b = _build_stub_report(
        name="b",
        imports=["requests"],
        mappings={"requests": "requests"},
        pinned={"requests": "2.31.0"},
        compat_matrix={
            t_linux.platform_tag: {"requests": {"status": "compatible"}},
            t_macos.platform_tag: {
                "requests": {"status": "incompatible", "reason": "No macos wheel"}
            },
        },
        targets=[t_linux, t_macos],
    )

    comparison = ReportComparator.compare(report_a, report_b)
    assert comparison.added_targets == [t_macos.platform_tag]
    assert comparison.removed_targets == []
    # Since macos was not in baseline, the failure on macos was due to target addition
    assert len(comparison.new_compatibility_failures) == 0
    assert comparison.has_regressions is False
