"""Integration tests for CLI diagnose, report, and compare commands."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from pydeps_intelligence.cli.main import app
from pydeps_intelligence.reporting.report_schema import DiagnosticReport, StageStatus

runner = CliRunner()


def test_cli_diagnose_json_purity_on_stdout(tmp_path: Path) -> None:
    """When --json is passed, stdout must contain only valid JSON without decorative text."""
    test_file = tmp_path / "app.py"
    test_file.write_text("import sys\nimport os\n", encoding="utf-8")

    res = runner.invoke(app, ["diagnose", str(tmp_path), "--offline", "--json"])
    assert res.exit_code == 0, f"Command failed: {res.stdout}"

    # stdout must parse cleanly as JSON
    try:
        data = json.loads(res.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"stdout is not pure JSON: {res.stdout}") from exc

    assert data["schema_version"] == "1.0.0"
    assert "project_information" in data
    assert "source_analysis" in data
    assert "stage_results" in data


def test_cli_diagnose_exports_artifacts(tmp_path: Path) -> None:
    """diagnose --output <dir> must export report.json and index.html."""
    test_file = tmp_path / "main.py"
    test_file.write_text("import json\n", encoding="utf-8")

    out_dir = tmp_path / "pydeps-output"

    res = runner.invoke(app, ["diagnose", str(tmp_path), "--offline", "--output", str(out_dir)])
    assert res.exit_code == 0, f"Command failed: {res.stdout}"

    assert (out_dir / "report.json").is_file()
    assert (out_dir / "index.html").is_file()

    html_content = (out_dir / "index.html").read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html_content
    assert "Diagnostic Pipeline Stages" in html_content


def test_cli_report_command_generates_html(tmp_path: Path) -> None:
    """pydeps report <report.json> must generate an HTML dashboard."""
    report_file = tmp_path / "report.json"
    report = DiagnosticReport(
        schema_version="1.0.0",
        tool_version="0.1.0",
        overall_status=StageStatus.PASSED,
        project_information={
            "name": "sample-proj",
            "path": str(tmp_path),
            "file_count": 1,
        },
        execution_environment={
            "operating_system": "windows",
            "architecture": "x86_64",
            "python_version": "3.11",
        },
    )
    report_file.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    out_html = tmp_path / "custom-dashboard.html"
    res = runner.invoke(app, ["report", str(report_file), "--output", str(out_html)])
    assert res.exit_code == 0
    assert out_html.is_file()
    assert "sample-proj" in out_html.read_text(encoding="utf-8")


def test_cli_compare_command_detects_regressions(tmp_path: Path) -> None:
    """pydeps compare must detect regressions and exit with code 1 if regressions are found."""
    rep_a_file = tmp_path / "report_a.json"
    rep_b_file = tmp_path / "report_b.json"

    rep_a = DiagnosticReport(
        schema_version="1.0.0",
        tool_version="0.1.0",
        overall_status=StageStatus.PASSED,
        project_information={"name": "test-v1", "path": str(tmp_path)},
        execution_environment={
            "operating_system": "linux",
            "architecture": "x86_64",
            "python_version": "3.11",
        },
        compatibility={
            "matrix": {
                "linux-x86_64-cpython-py3.11": {
                    "requests": {"status": "compatible"},
                }
            }
        },
    )

    # Report B introduces an incompatibility regression
    rep_b = DiagnosticReport(
        schema_version="1.0.0",
        tool_version="0.1.0",
        overall_status=StageStatus.FAILED,
        project_information={"name": "test-v2", "path": str(tmp_path)},
        execution_environment={
            "operating_system": "linux",
            "architecture": "x86_64",
            "python_version": "3.11",
        },
        compatibility={
            "matrix": {
                "linux-x86_64-cpython-py3.11": {
                    "requests": {
                        "status": "incompatible",
                        "reason": "Missing binary wheel",
                    },
                }
            }
        },
    )

    rep_a_file.write_text(rep_a.model_dump_json(indent=2), encoding="utf-8")
    rep_b_file.write_text(rep_b.model_dump_json(indent=2), encoding="utf-8")

    # Compare without json
    res = runner.invoke(app, ["compare", str(rep_a_file), str(rep_b_file)])
    assert res.exit_code == 1  # Exits 1 due to regression
    assert "[REGRESSION DETECTED]" in res.stdout

    # Compare with --json
    res_json = runner.invoke(app, ["compare", str(rep_a_file), str(rep_b_file), "--json"])
    assert res_json.exit_code == 1
    cmp_data = json.loads(res_json.stdout)
    assert cmp_data["has_regressions"] is True
    assert len(cmp_data["new_compatibility_failures"]) == 1
