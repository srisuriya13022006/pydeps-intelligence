"""Report generation for validation results: JSON, HTML dashboard, and stage log files."""

from __future__ import annotations

import html
from pathlib import Path

from pydeps.models.validation import ValidationReport, ValidationStatus
from pydeps.validation.network_policy import NetworkPolicyController


class ReportGenerator:
    """Exports structured validation outputs: JSON, HTML summary, and raw logs."""

    @staticmethod
    def generate_all(
        report: ValidationReport,
        output_dir: Path | str,
    ) -> list[Path]:
        """Generate validation.json, validation-report.html, and stage log files."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        logs_dir = out / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        generated_files: list[Path] = []

        # 1. validation.json
        json_path = out / "validation.json"
        raw_json = report.model_dump_json(indent=2)
        sanitized_json = NetworkPolicyController.sanitize_log(raw_json)
        json_path.write_text(sanitized_json, encoding="utf-8")
        generated_files.append(json_path)

        # 2. validation-report.html
        html_path = out / "validation-report.html"
        html_content = ReportGenerator._render_html(report)
        html_path.write_text(html_content, encoding="utf-8")
        generated_files.append(html_path)

        # 3. Stage log files
        for stage_name, stage_res in report.stages.items():
            clean_name = stage_name.replace("_", "-")
            log_file = logs_dir / f"{clean_name}.log"
            sanitized_log = NetworkPolicyController.sanitize_log(stage_res.logs)
            log_file.write_text(sanitized_log, encoding="utf-8")
            generated_files.append(log_file)

        report.output_files = generated_files
        return generated_files

    @staticmethod
    def _render_html(report: ValidationReport) -> str:
        """Render a clean, modern HTML validation dashboard."""
        status_color = (
            "#10b981"
            if report.status in (ValidationStatus.PASSED, ValidationStatus.SUCCESS)
            else "#ef4444"
        )
        if report.status in (
            ValidationStatus.BLOCKED_BY_POLICY,
            ValidationStatus.SKIPPED,
            ValidationStatus.UNVERIFIED,
        ):
            status_color = "#f59e0b"

        # Packages table rows
        pkg_rows = ""
        for name, ver in sorted(report.installed_packages.items()):
            esc_name = html.escape(name)
            esc_ver = html.escape(ver)
            pkg_rows += f"<tr><td><code>{esc_name}</code></td><td><code>{esc_ver}</code></td></tr>"

        if not pkg_rows:
            pkg_rows = "<tr><td colspan='2'><em>No packages installed or recorded</em></td></tr>"

        # Stages list
        stage_cards = ""
        for s_name, s_res in report.stages.items():
            s_color = (
                "#10b981"
                if s_res.status in (ValidationStatus.PASSED, ValidationStatus.SUCCESS)
                else "#ef4444"
            )
            if s_res.status in (
                ValidationStatus.SKIPPED,
                ValidationStatus.BLOCKED_BY_POLICY,
                ValidationStatus.UNVERIFIED,
            ):
                s_color = "#f59e0b"

            details = ""
            if s_res.import_results:
                details += (
                    "<table class='sub-table'><tr><th>Module</th>"
                    "<th>Distribution</th><th>Status</th><th>Duration</th></tr>"
                )
                for imp in s_res.import_results:
                    imp_badge = (
                        "color:#10b981"
                        if imp.status == ValidationStatus.PASSED
                        else "color:#ef4444"
                    )
                    status_val = html.escape(imp.status.value)
                    details += (
                        f"<tr><td><code>{html.escape(imp.module_name)}</code></td>"
                        f"<td>{html.escape(imp.distribution_name or '-')}</td>"
                        f"<td style='{imp_badge};font-weight:bold'>{status_val}</td>"
                        f"<td>{imp.duration_seconds}s</td></tr>"
                    )
                details += "</table>"

            if s_res.test_result:
                tr = s_res.test_result
                cmd_str = " ".join(html.escape(c) for c in tr.command)
                details += (
                    f"<p><strong>Command:</strong> <code>{cmd_str}</code> | "
                    f"<strong>Exit Code:</strong> {tr.exit_code} | "
                    f"<strong>Duration:</strong> {tr.duration_seconds}s</p>"
                )

            if s_res.errors:
                details += "<div class='error-box'><strong>Errors:</strong><ul>"
                for err in s_res.errors:
                    details += f"<li>{html.escape(err)}</li>"
                details += "</ul></div>"

            stage_status_val = html.escape(s_res.status.value)
            stage_cards += f"""
            <div class='stage-card'>
                <div class='stage-header'>
                    <span class='stage-title'>{html.escape(s_name.upper())}</span>
                    <span class='badge' style='background-color:{s_color}'>{stage_status_val}</span>
                </div>
                <p><strong>Duration:</strong> {s_res.duration_seconds}s</p>
                {details}
            </div>
            """

        diagnostics_html = ""
        if report.diagnostics:
            diagnostics_html = "<div class='diag-card'><h3>Diagnostics & Policy Notices</h3><ul>"
            for d in report.diagnostics:
                diagnostics_html += f"<li>{html.escape(d)}</li>"
            diagnostics_html += "</ul></div>"

        target_desc = (
            f"Target: {html.escape(report.target_environment.platform_tag)} | "
            f"Runner: {html.escape(report.runner_type)} ({html.escape(report.isolation_level)})"
        )
        report_status_val = html.escape(report.status.value.upper())
        py_interp_val = html.escape(report.python_interpreter_version or "N/A")

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>PyDeps Validation Report - {html.escape(report.project_name or "Project")}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #0f172a;
            color: #f8fafc;
            margin: 0;
            padding: 2rem;
        }}
        .container {{ max-width: 1000px; margin: 0 auto; }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #334155;
            padding-bottom: 1.5rem;
        }}
        .badge {{
            padding: 0.35rem 0.8rem;
            border-radius: 9999px;
            font-weight: bold;
            font-size: 0.9rem;
            color: #fff;
        }}
        .grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
            margin: 1.5rem 0;
        }}
        .card {{
            background: #1e293b;
            border-radius: 8px;
            padding: 1.25rem;
            border: 1px solid #334155;
        }}
        .stage-card {{
            background: #1e293b;
            border-radius: 8px;
            padding: 1.25rem;
            border: 1px solid #334155;
            margin-bottom: 1rem;
        }}
        .stage-header {{ display: flex; justify-content: space-between; align-items: center; }}
        .stage-title {{ font-size: 1.1rem; font-weight: bold; color: #38bdf8; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 0.5rem; }}
        th, td {{ padding: 0.5rem 0.75rem; text-align: left; border-bottom: 1px solid #334155; }}
        th {{ background: #0f172a; color: #94a3b8; font-size: 0.85rem; text-transform: uppercase; }}
        code {{ background: #0f172a; padding: 0.2rem 0.4rem; border-radius: 4px; color: #f43f5e; }}
        .error-box {{
            background: #450a0a;
            border: 1px solid #ef4444;
            border-radius: 4px;
            padding: 0.75rem;
            margin-top: 0.5rem;
            color: #fca5a5;
        }}
        .diag-card {{
            background: #1e293b;
            border-left: 4px solid #f59e0b;
            padding: 1rem;
            border-radius: 4px;
            margin-top: 1rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>PyDeps Runtime Validation Report</h1>
                <p style="color:#94a3b8">{target_desc}</p>
            </div>
            <div>
                <span class="badge" style="background-color:{status_color}">
                    {report_status_val}
                </span>
            </div>
        </div>

        <div class="grid">
            <div class="card">
                <h3>Execution Policy & Environment</h3>
                <p><strong>Trust Policy:</strong> {html.escape(report.execution_policy.value)}</p>
                <p><strong>Network Policy:</strong> {html.escape(report.network_policy.value)}</p>
                <p><strong>Python Interpreter:</strong> {py_interp_val}</p>
                <p><strong>Cleanup Status:</strong> {html.escape(report.cleanup_status)}</p>
            </div>
            <div class="card">
                <h3>Installed Packages ({len(report.installed_packages)})</h3>
                <div style="max-height: 180px; overflow-y: auto;">
                    <table>
                        <thead><tr><th>Distribution</th><th>Version</th></tr></thead>
                        <tbody>{pkg_rows}</tbody>
                    </table>
                </div>
            </div>
        </div>

        <h2>Validation Stages</h2>
        {stage_cards}

        {diagnostics_html}
    </div>
</body>
</html>
"""
