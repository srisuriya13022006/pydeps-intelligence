"""Report comparison and regression detection engine."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from packaging.utils import canonicalize_name
from pydantic import BaseModel, ConfigDict, Field

from pydeps_intelligence.reporting.report_schema import DiagnosticReport, StageStatus


class MappingDifference(BaseModel):
    """Change in an import-to-distribution mapping."""

    model_config = ConfigDict(extra="forbid")

    import_name: str
    old_distribution: str | None
    new_distribution: str | None
    old_confidence: str | None
    new_confidence: str | None


class VersionDifference(BaseModel):
    """Change in resolved package version."""

    model_config = ConfigDict(extra="forbid")

    package: str
    old_version: str | None
    new_version: str | None


class CompatibilityDifference(BaseModel):
    """Change in compatibility outcome for a package-target pair."""

    model_config = ConfigDict(extra="forbid")

    target: str
    package: str
    old_status: str | None
    new_status: str | None
    reason: str | None
    is_regression: bool


class ComparisonReport(BaseModel):
    """Structured delta comparison between two diagnostic reports."""

    model_config = ConfigDict(extra="allow")

    report_a_project: str = ""
    report_b_project: str = ""
    report_a_timestamp: str = ""
    report_b_timestamp: str = ""
    schema_version_a: str = ""
    schema_version_b: str = ""
    tool_version_a: str = ""
    tool_version_b: str = ""
    schema_version_mismatch: bool = False
    tool_version_mismatch: bool = False

    target_environments_match: bool = True
    target_differences: list[str] = Field(default_factory=list)
    added_targets: list[str] = Field(default_factory=list)
    removed_targets: list[str] = Field(default_factory=list)

    # Diffs
    new_imports: list[str] = Field(default_factory=list)
    removed_imports: list[str] = Field(default_factory=list)
    changed_mappings: list[MappingDifference] = Field(default_factory=list)
    version_changes: list[VersionDifference] = Field(default_factory=list)

    new_compatibility_failures: list[CompatibilityDifference] = Field(default_factory=list)
    resolved_compatibility_failures: list[CompatibilityDifference] = Field(default_factory=list)
    unverified_compatibility_changes: list[CompatibilityDifference] = Field(default_factory=list)

    new_conflicts: list[dict[str, Any]] = Field(default_factory=list)
    resolved_conflicts: list[dict[str, Any]] = Field(default_factory=list)

    stage_changes: list[dict[str, Any]] = Field(default_factory=list)
    validation_changes: list[dict[str, Any]] = Field(default_factory=list)

    has_regressions: bool = False
    diagnostics: list[str] = Field(default_factory=list)


class ReportComparator:
    """Compares two diagnostic reports to detect regressions, diffs, and improvements."""

    @classmethod
    def load_report(cls, path_or_dict: Path | str | dict[str, Any]) -> DiagnosticReport:
        """Parse DiagnosticReport from file path or dictionary."""
        if isinstance(path_or_dict, (Path, str)):
            p = Path(path_or_dict).resolve()
            if not p.is_file():
                raise FileNotFoundError(f"Report file not found: {p}")
            data = json.loads(p.read_text(encoding="utf-8"))
        else:
            data = path_or_dict
        return DiagnosticReport.model_validate(data)

    @classmethod
    def compare(
        cls,
        report_a: Path | str | dict[str, Any] | DiagnosticReport,
        report_b: Path | str | dict[str, Any] | DiagnosticReport,
    ) -> ComparisonReport:
        """Compute delta between baseline report_a and target report_b."""
        rep_a = report_a if isinstance(report_a, DiagnosticReport) else cls.load_report(report_a)
        rep_b = report_b if isinstance(report_b, DiagnosticReport) else cls.load_report(report_b)

        has_regressions = False
        diagnostics: list[str] = []

        # 1. Target Environment Separation
        targets_a = {t.platform_tag for t in rep_a.target_environments} or set(
            rep_a.compatibility.matrix.keys()
        )
        targets_b = {t.platform_tag for t in rep_b.target_environments} or set(
            rep_b.compatibility.matrix.keys()
        )
        added_targets = sorted(list(targets_b - targets_a))
        removed_targets = sorted(list(targets_a - targets_b))
        target_diffs = sorted(list(set(added_targets) | set(removed_targets)))
        if target_diffs:
            diagnostics.append(
                f"Target environment configurations differ between reports: added {added_targets}, removed {removed_targets}. "
                "Differences on new targets are caused by target shifts rather than package regressions."
            )

        # 2. Schema and Tool Version Inspection
        schema_a = rep_a.schema_version
        schema_b = rep_b.schema_version
        tool_a = rep_a.tool_version
        tool_b = rep_b.tool_version
        schema_mismatch = schema_a != schema_b
        tool_mismatch = tool_a != tool_b
        if schema_mismatch:
            diagnostics.append(
                f"Report schema version mismatch: baseline is v{schema_a}, target is v{schema_b}."
            )
        if tool_mismatch:
            diagnostics.append(
                f"PyDeps tool version difference: baseline produced by v{tool_a}, target by v{tool_b}."
            )

        # 3. Pipeline Stage Outcomes (Missing stages are not treated as passed)
        stage_changes: list[dict[str, Any]] = []
        all_stage_names = set(rep_a.stage_results.keys()) | set(rep_b.stage_results.keys())
        for st in sorted(all_stage_names):
            s_a = rep_a.stage_results.get(st)
            s_b = rep_b.stage_results.get(st)
            stat_a = s_a.status if s_a else StageStatus.SKIPPED
            stat_b = s_b.status if s_b else StageStatus.SKIPPED
            if stat_a != stat_b:
                stage_changes.append(
                    {
                        "stage": st,
                        "old_status": stat_a.value,
                        "new_status": stat_b.value,
                    }
                )
                if stat_a == StageStatus.PASSED and stat_b in (
                    StageStatus.FAILED,
                    StageStatus.BLOCKED_BY_POLICY,
                ):
                    has_regressions = True

        # 4. Source Imports
        all_imports_a = (
            set(rep_a.source_analysis.standard_library)
            | set(rep_a.source_analysis.local_imports)
            | set(rep_a.source_analysis.external_candidates)
        )
        all_imports_b = (
            set(rep_b.source_analysis.standard_library)
            | set(rep_b.source_analysis.local_imports)
            | set(rep_b.source_analysis.external_candidates)
        )
        new_imports = sorted(list(all_imports_b - all_imports_a))
        removed_imports = sorted(list(all_imports_a - all_imports_b))

        # 5. Package Mappings
        changed_mappings: list[MappingDifference] = []
        all_map_keys = set(rep_a.package_intelligence.mappings.keys()) | set(
            rep_b.package_intelligence.mappings.keys()
        )
        for k in sorted(all_map_keys):
            dist_a = rep_a.package_intelligence.mappings.get(k)
            dist_b = rep_b.package_intelligence.mappings.get(k)
            conf_a = rep_a.package_intelligence.confidence_levels.get(k)
            conf_b = rep_b.package_intelligence.confidence_levels.get(k)
            if dist_a != dist_b or conf_a != conf_b:
                changed_mappings.append(
                    MappingDifference(
                        import_name=k,
                        old_distribution=dist_a,
                        new_distribution=dist_b,
                        old_confidence=conf_a,
                        new_confidence=conf_b,
                    )
                )

        # 6. Pinned Versions using canonicalized package identity
        version_changes: list[VersionDifference] = []
        norm_versions_a: dict[str, tuple[str, str]] = {
            canonicalize_name(pkg): (pkg, str(ver))
            for pkg, ver in rep_a.resolution.pinned_versions.items()
        }
        norm_versions_b: dict[str, tuple[str, str]] = {
            canonicalize_name(pkg): (pkg, str(ver))
            for pkg, ver in rep_b.resolution.pinned_versions.items()
        }
        common_norm_pkgs = sorted(set(norm_versions_a.keys()) & set(norm_versions_b.keys()))
        for norm_name in common_norm_pkgs:
            orig_a, v_a = norm_versions_a[norm_name]
            orig_b, v_b = norm_versions_b[norm_name]
            if v_a != v_b:
                version_changes.append(
                    VersionDifference(package=orig_b or orig_a, old_version=v_a, new_version=v_b)
                )

        # 7. Conflicts using canonicalized names
        conflicts_a = {
            canonicalize_name(c.get("package", "unknown")): c
            for c in rep_a.resolution.conflicts
            if isinstance(c, dict) and "package" in c
        }
        conflicts_b = {
            canonicalize_name(c.get("package", "unknown")): c
            for c in rep_b.resolution.conflicts
            if isinstance(c, dict) and "package" in c
        }
        new_conflicts = [conflicts_b[pkg] for pkg in sorted(set(conflicts_b) - set(conflicts_a))]
        resolved_conflicts = [
            conflicts_a[pkg] for pkg in sorted(set(conflicts_a) - set(conflicts_b))
        ]
        if new_conflicts:
            has_regressions = True

        # 8. Compatibility Differences (Evaluated across common targets only)
        new_compat_failures: list[CompatibilityDifference] = []
        resolved_compat_failures: list[CompatibilityDifference] = []
        unverified_compat_changes: list[CompatibilityDifference] = []

        common_targets = targets_a & targets_b
        for t_id in sorted(common_targets):
            matrix_a = rep_a.compatibility.matrix.get(t_id, {})
            matrix_b = rep_b.compatibility.matrix.get(t_id, {})
            all_matrix_pkgs = set(matrix_a.keys()) | set(matrix_b.keys())

            for pkg in sorted(all_matrix_pkgs):
                stat_a = matrix_a.get(pkg, {}).get("status")
                stat_b = matrix_b.get(pkg, {}).get("status")
                reason_b = matrix_b.get(pkg, {}).get("reason")

                if stat_a != "incompatible" and stat_b == "incompatible":
                    new_compat_failures.append(
                        CompatibilityDifference(
                            target=t_id,
                            package=pkg,
                            old_status=stat_a,
                            new_status=stat_b,
                            reason=reason_b,
                            is_regression=True,
                        )
                    )
                    has_regressions = True
                elif stat_a == "incompatible" and stat_b == "compatible":
                    resolved_compat_failures.append(
                        CompatibilityDifference(
                            target=t_id,
                            package=pkg,
                            old_status=stat_a,
                            new_status=stat_b,
                            reason=None,
                            is_regression=False,
                        )
                    )
                elif stat_a == "compatible" and stat_b == "unverified":
                    unverified_compat_changes.append(
                        CompatibilityDifference(
                            target=t_id,
                            package=pkg,
                            old_status=stat_a,
                            new_status=stat_b,
                            reason=reason_b,
                            is_regression=False,
                        )
                    )

        # 9. Runtime Validation differences
        validation_changes: list[dict[str, Any]] = []
        val_stat_a = rep_a.validation.status
        val_stat_b = rep_b.validation.status
        if val_stat_a != val_stat_b:
            validation_changes.append(
                {
                    "item": "overall_validation",
                    "old_status": val_stat_a.value,
                    "new_status": val_stat_b.value,
                }
            )
            if val_stat_b == StageStatus.FAILED and val_stat_a != StageStatus.FAILED:
                has_regressions = True

        return ComparisonReport(
            report_a_project=rep_a.project_information.name,
            report_b_project=rep_b.project_information.name,
            report_a_timestamp=rep_a.project_information.analysis_timestamp.isoformat(),
            report_b_timestamp=rep_b.project_information.analysis_timestamp.isoformat(),
            schema_version_a=schema_a,
            schema_version_b=schema_b,
            tool_version_a=tool_a,
            tool_version_b=tool_b,
            schema_version_mismatch=schema_mismatch,
            tool_version_mismatch=tool_mismatch,
            target_environments_match=(len(target_diffs) == 0),
            target_differences=target_diffs,
            added_targets=added_targets,
            removed_targets=removed_targets,
            new_imports=new_imports,
            removed_imports=removed_imports,
            changed_mappings=changed_mappings,
            version_changes=version_changes,
            new_compatibility_failures=new_compat_failures,
            resolved_compatibility_failures=resolved_compat_failures,
            unverified_compatibility_changes=unverified_compat_changes,
            new_conflicts=new_conflicts,
            resolved_conflicts=resolved_conflicts,
            stage_changes=stage_changes,
            validation_changes=validation_changes,
            has_regressions=has_regressions,
            diagnostics=diagnostics,
        )
