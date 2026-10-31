"""Integration tests for the `pydeps validate` CLI command."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from pydeps.cli.main import app

cli_runner = CliRunner()


def test_cli_validate_dry_run_success(tmp_path: Path) -> None:
    """CLI dry run executes successfully without running any code."""
    res_file = tmp_path / "resolution.json"
    res_data = {
        "success": True,
        "mode": "universal",
        "strategy": "latest-compatible",
        "status": "success",
        "graph": {
            "roots": ["requests"],
            "packages": {
                "requests": {
                    "name": "requests",
                    "version": "2.31.0",
                    "dependency_type": "direct",
                }
            },
            "edges": {},
            "direct_count": 1,
            "transitive_count": 0,
        },
    }
    res_file.write_text(json.dumps(res_data), encoding="utf-8")

    result = cli_runner.invoke(
        app,
        ["validate", str(tmp_path), "--resolution", str(res_file), "--dry-run"],
    )
    assert result.exit_code == 0
    assert "PyDeps Runtime Validation" in result.output
    assert "Dry Run Execution Plan" in result.output
    assert "requests==2.31.0" in result.output


def test_cli_validate_blocked_by_policy_when_unauthorized(tmp_path: Path) -> None:
    """CLI validate exits with code 1 when local code execution is unauthorized."""
    res_file = tmp_path / "resolution.json"
    res_data = {
        "success": True,
        "mode": "universal",
        "strategy": "latest-compatible",
        "status": "success",
    }
    res_file.write_text(json.dumps(res_data), encoding="utf-8")

    import platform
    import sys

    host_os = "windows" if platform.system() == "Windows" else "linux"
    host_py = f"{sys.version_info.major}.{sys.version_info.minor}"
    target_str = f"{host_os}-x86_64-cpython-py{host_py}"

    # Invocation without --allow-local-execution
    result = cli_runner.invoke(
        app,
        ["validate", str(tmp_path), "--resolution", str(res_file), "--target", target_str],
    )
    assert result.exit_code == 1
    assert "BLOCKED BY POLICY" in result.output
    assert "STATIC_ONLY" in result.output


def test_cli_validate_json_output(tmp_path: Path) -> None:
    """CLI validate produces valid structured JSON when --json flag is passed."""
    res_file = tmp_path / "resolution.json"
    res_data = {
        "success": True,
        "mode": "universal",
        "strategy": "latest-compatible",
        "status": "success",
    }
    res_file.write_text(json.dumps(res_data), encoding="utf-8")

    result = cli_runner.invoke(
        app,
        ["validate", str(tmp_path), "--resolution", str(res_file), "--dry-run", "--json"],
    )
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["status"] == "passed"
    assert "dry_run_plan" in parsed
