"""Unit tests for DiagnosticReport schema and serialization."""

from __future__ import annotations

import json

from pydeps.models.project import Architecture, OperatingSystem, TargetEnvironment
from pydeps.reporting.report_schema import (
    CompatibilitySection,
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


def test_diagnostic_report_serialization_and_deserialization() -> None:
    """DiagnosticReport must serialize to valid JSON and deserialize losslessly."""
    report = DiagnosticReport(
        schema_version="1.0.0",
        tool_version="0.1.0",
        overall_status=StageStatus.PASSED,
        project_information=ProjectInfo(
            name="test-project",
            path="/path/to/test-project",
            file_count=5,
            test_file_count=2,
            lines_of_code=120,
        ),
        execution_environment=ExecutionEnvironmentInfo(
            operating_system="linux",
            architecture="x86_64",
            python_version="3.11.9",
            python_implementation="CPython",
            offline_mode=False,
        ),
        target_environments=[
            TargetEnvironment(
                python_version="3.11",
                operating_system=OperatingSystem.LINUX,
                architecture=Architecture.X86_64,
            )
        ],
        stage_results={
            "scan": StageResultSummary(
                stage_name="scan",
                status=StageStatus.PASSED,
                duration_seconds=0.1,
            ),
            "imports": StageResultSummary(
                stage_name="imports",
                status=StageStatus.PASSED,
                duration_seconds=0.2,
            ),
        },
        source_analysis=SourceAnalysisSection(
            total_files=5,
            total_imports=10,
            standard_library=["sys", "os"],
            local_imports=["utils"],
            external_candidates=["requests"],
        ),
        package_intelligence=PackageIntelligenceSection(
            mappings={"requests": "requests"},
            confidence_levels={"requests": "HIGH"},
        ),
        compatibility=CompatibilitySection(
            evaluated_targets=[{"id": "linux-x86_64-cpython-py3.11"}],
            evaluated_packages=["requests"],
            compatible_count=1,
        ),
        resolution=ResolutionSection(
            success=True,
            direct_packages=["requests"],
            pinned_versions={"requests": "2.31.0"},
        ),
        validation=ValidationSection(executed=False, status=StageStatus.SKIPPED),
        recommendations=[
            RecommendationItem(
                category="info",
                severity=RecommendationSeverity.INFO,
                title="All good",
                description="No issues found",
            )
        ],
        diagnostics=["Sample diagnostic message"],
        provenance=ProvenanceInfo(cli_command="pydeps diagnose ."),
    )

    json_str = report.model_dump_json(indent=2)
    parsed = json.loads(json_str)

    assert parsed["schema_version"] == "1.0.0"
    assert parsed["overall_status"] == "passed"
    assert parsed["project_information"]["name"] == "test-project"

    deserialized = DiagnosticReport.model_validate(parsed)
    assert deserialized.overall_status == StageStatus.PASSED
    assert deserialized.project_information.file_count == 5
    assert deserialized.source_analysis.external_candidates == ["requests"]
    assert len(deserialized.recommendations) == 1


def test_json_schema_generation_and_conformance() -> None:
    """DiagnosticReport JSON schema must correctly declare definitions, required fields, and enums."""
    from pydeps.reporting.report_schema import DependencyHealthStatus

    schema = DiagnosticReport.model_json_schema()

    # Verify top-level structure
    assert schema["title"] == "DiagnosticReport"
    assert schema["type"] == "object"
    assert "properties" in schema
    assert "required" in schema

    # Required fields must be explicitly specified
    req = set(schema["required"])
    assert "schema_version" in req
    assert "tool_version" in req
    assert "overall_status" in req
    assert "project_information" in req
    assert "execution_environment" in req

    # Enums must be present in definitions
    defs = schema.get("$defs", {})
    assert "StageStatus" in defs
    assert "DependencyHealthStatus" in defs
    assert "RecommendationSeverity" in defs

    stage_status_values = defs["StageStatus"]["enum"]
    for s in StageStatus:
        assert s.value in stage_status_values

    health_values = defs["DependencyHealthStatus"]["enum"]
    for h in DependencyHealthStatus:
        assert h.value in health_values

    # Test round-trip model validation against generated schema structure
    report = DiagnosticReport(
        schema_version="1.0.0",
        tool_version="0.1.0",
        pipeline_status=StageStatus.PASSED,
        dependency_health_status=DependencyHealthStatus.HEALTHY,
        runtime_validation_status=StageStatus.SKIPPED,
        overall_status=StageStatus.PASSED,
        project_information=ProjectInfo(name="schema-valid", path="/tmp/schema"),
        execution_environment=ExecutionEnvironmentInfo(
            operating_system="linux",
            architecture="x86_64",
            python_version="3.11",
        ),
    )
    dumped = json.loads(report.model_dump_json())
    validated = DiagnosticReport.model_validate(dumped)
    assert validated.schema_version == "1.0.0"
    assert validated.pipeline_status == StageStatus.PASSED
    assert validated.dependency_health_status == DependencyHealthStatus.HEALTHY
