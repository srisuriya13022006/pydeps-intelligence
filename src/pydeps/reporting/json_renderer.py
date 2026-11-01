"""JSON serializer and artifact exporter for diagnostic reports."""

from __future__ import annotations

import json
from pathlib import Path

from pydeps.reporting.report_schema import DiagnosticReport


class JsonRenderer:
    """Renders DiagnosticReport instances to structured, valid JSON."""

    @staticmethod
    def render(report: DiagnosticReport, indent: int = 2) -> str:
        """Render the complete report as formatted JSON string."""
        data = report.model_dump(mode="json")
        return json.dumps(data, indent=indent, sort_keys=False)

    @classmethod
    def export_artifacts(
        cls,
        report: DiagnosticReport,
        output_dir: Path | str,
    ) -> list[Path]:
        """Export report.json and stage-specific json files for executed stages."""
        out_path = Path(output_dir).resolve()
        out_path.mkdir(parents=True, exist_ok=True)
        created_files: list[Path] = []

        # 1. Complete report.json
        report_file = out_path / "report.json"
        report_file.write_text(cls.render(report), encoding="utf-8")
        created_files.append(report_file)

        # 2. compatibility.json (only if compatibility stage was executed)
        if report.compatibility.evaluated_packages or report.compatibility.matrix:
            compat_file = out_path / "compatibility.json"
            compat_data = {
                "schema_version": report.schema_version,
                "project_name": report.project_information.name,
                "timestamp": report.project_information.analysis_timestamp.isoformat(),
                "compatibility": report.compatibility.model_dump(mode="json"),
            }
            compat_file.write_text(json.dumps(compat_data, indent=2), encoding="utf-8")
            created_files.append(compat_file)

        # 3. resolution.json (only if resolution stage was executed)
        if (
            report.resolution.direct_packages
            or report.resolution.pinned_versions
            or report.resolution.conflicts
        ):
            res_file = out_path / "resolution.json"
            res_data = {
                "schema_version": report.schema_version,
                "project_name": report.project_information.name,
                "timestamp": report.project_information.analysis_timestamp.isoformat(),
                "resolution": report.resolution.model_dump(mode="json"),
            }
            res_file.write_text(json.dumps(res_data, indent=2), encoding="utf-8")
            created_files.append(res_file)

        # 4. validation.json (only if runtime validation was executed)
        if report.validation.executed:
            val_file = out_path / "validation.json"
            val_data = {
                "schema_version": report.schema_version,
                "project_name": report.project_information.name,
                "timestamp": report.project_information.analysis_timestamp.isoformat(),
                "validation": report.validation.model_dump(mode="json"),
            }
            val_file.write_text(json.dumps(val_data, indent=2), encoding="utf-8")
            created_files.append(val_file)

        return created_files
