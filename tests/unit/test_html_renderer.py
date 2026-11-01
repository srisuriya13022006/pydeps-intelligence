"""Unit tests for HtmlRenderer security, self-containment, and escaping."""

from __future__ import annotations

from pathlib import Path

from pydeps_intelligence.reporting.html_renderer import HtmlRenderer
from pydeps_intelligence.reporting.report_schema import (
    CompatibilitySection,
    DiagnosticReport,
    ExecutionEnvironmentInfo,
    ProjectInfo,
    StageStatus,
)


def test_html_renderer_is_strictly_self_contained() -> None:
    """Rendered HTML dashboard must not reference external CDN links, scripts, or styles."""
    report = DiagnosticReport(
        schema_version="1.0.0",
        tool_version="0.1.0",
        overall_status=StageStatus.PASSED,
        project_information=ProjectInfo(name="clean-project", path="/tmp/clean"),
        execution_environment=ExecutionEnvironmentInfo(
            operating_system="linux",
            architecture="x86_64",
            python_version="3.11",
        ),
    )

    rendered_html = HtmlRenderer.render(report)

    assert "http://" not in rendered_html.lower()
    assert "https://" not in rendered_html.lower()
    assert '<link rel="stylesheet" href="http' not in rendered_html
    assert '<script src="http' not in rendered_html
    assert 'data-theme="dark"' in rendered_html
    assert "toggleTheme()" in rendered_html


def test_html_renderer_escapes_untrusted_strings() -> None:
    """Untrusted project names and package reasons must be properly HTML-escaped to prevent XSS."""
    malicious_name = "<script>alert('xss')</script>"
    malicious_reason = "<img src=x onerror=alert(1)>"

    report = DiagnosticReport(
        schema_version="1.0.0",
        tool_version="0.1.0",
        overall_status=StageStatus.PASSED,
        project_information=ProjectInfo(name=malicious_name, path="/tmp/test"),
        execution_environment=ExecutionEnvironmentInfo(
            operating_system="linux",
            architecture="x86_64",
            python_version="3.11",
        ),
        compatibility=CompatibilitySection(
            evaluated_targets=[{"id": "test-target"}],
            evaluated_packages=["malicious-pkg"],
            matrix={
                "test-target": {
                    "malicious-pkg": {
                        "status": "incompatible",
                        "reason": malicious_reason,
                    }
                }
            },
        ),
    )

    rendered_html = HtmlRenderer.render(report)

    assert "<script>alert('xss')</script>" not in rendered_html
    assert (
        "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;" in rendered_html
        or "&lt;script&gt;alert('xss')&lt;/script&gt;" in rendered_html
    )
    assert "<img src=x onerror=alert(1)>" not in rendered_html


def test_html_renderer_exports_to_disk(tmp_path: Path) -> None:
    """HtmlRenderer.export_html must write valid HTML file to the specified path."""
    report = DiagnosticReport(
        schema_version="1.0.0",
        tool_version="0.1.0",
        overall_status=StageStatus.PASSED,
        project_information=ProjectInfo(name="export-test", path=str(tmp_path)),
        execution_environment=ExecutionEnvironmentInfo(
            operating_system="linux",
            architecture="x86_64",
            python_version="3.11",
        ),
    )

    out_file = tmp_path / "dashboard.html"
    exported = HtmlRenderer.export_html(report, out_file)

    assert exported.is_file()
    assert "<!DOCTYPE html>" in exported.read_text(encoding="utf-8")


def test_html_renderer_malicious_fixtures_and_escaping() -> None:
    """Malicious scripts, event handlers, closing script tags, quotes, entities and paths must be sanitized."""
    malicious_inputs = [
        "<script>alert(1)</script>",
        "</script><script>alert('pwned')</script>",
        '" onmouseover="alert(1)"',
        "' onclick='alert(1)'",
        "&amp;&lt;&gt;\"'",
        "malicious\x00pkg_with_null",
        "../../../etc/passwd",
        "pkg<foo>bar",
        "Unicode_🚀_مرحبا_123",
    ]

    for payload in malicious_inputs:
        report = DiagnosticReport(
            schema_version="1.0.0",
            tool_version="0.1.0",
            overall_status=StageStatus.FAILED,
            project_information=ProjectInfo(name=payload, path=f"/tmp/{payload}"),
            execution_environment=ExecutionEnvironmentInfo(
                operating_system="linux",
                architecture="x86_64",
                python_version="3.11",
            ),
            compatibility=CompatibilitySection(
                evaluated_targets=[{"id": payload}],
                evaluated_packages=[payload],
                matrix={payload: {payload: {"status": "incompatible", "reason": payload}}},
            ),
        )

        rendered = HtmlRenderer.render(report)

        # Unescaped executable script tags must NEVER appear in HTML
        assert "<script>alert(1)</script>" not in rendered
        assert "<script>alert('pwned')</script>" not in rendered
        assert 'onmouseover="alert(1)"' not in rendered
        assert "onclick='alert(1)'" not in rendered
        assert "\x00" not in rendered

        # If payload contained '</script>', it must NOT prematurely close the application/json script block
        assert "</script><script>" not in rendered


def test_html_renderer_displays_separate_statuses() -> None:
    """Dashboard must render pipeline, health, and validation badges distinctly."""
    report = DiagnosticReport(
        schema_version="1.0.0",
        tool_version="0.1.0",
        pipeline_status=StageStatus.PASSED,
        dependency_health_status="partial",
        runtime_validation_status=StageStatus.SKIPPED,
        overall_status=StageStatus.PARTIAL,
        project_information=ProjectInfo(name="multi-status", path="/tmp/test"),
        execution_environment=ExecutionEnvironmentInfo(
            operating_system="linux",
            architecture="x86_64",
            python_version="3.11",
        ),
    )

    rendered = HtmlRenderer.render(report)
    assert "Pipeline: passed" in rendered
    assert "Health: partial" in rendered
    assert "Validation: skipped" in rendered


def test_html_renderer_large_graph_fallback() -> None:
    """Small graphs must render SVG; large graphs (>35 nodes) must render the fallback message."""
    from pydeps_intelligence.reporting.report_schema import ResolutionSection

    # Small graph
    small_sec = ResolutionSection(
        success=True,
        pinned_versions={"flask": "3.0.0", "werkzeug": "3.0.1"},
        dependency_graph={"flask": ["werkzeug"], "werkzeug": []},
    )
    rep_small = DiagnosticReport(
        schema_version="1.0.0",
        tool_version="0.1.0",
        overall_status=StageStatus.PASSED,
        project_information=ProjectInfo(name="small", path="/tmp/small"),
        execution_environment=ExecutionEnvironmentInfo(
            operating_system="linux", architecture="x86_64", python_version="3.11"
        ),
        resolution=small_sec,
    )
    rendered_small = HtmlRenderer.render(rep_small)
    assert "<svg" in rendered_small
    assert "Direct &rarr; Transitive Dependency Graph" in rendered_small

    # Large graph (> 35 nodes)
    large_graph = {f"pkg_{i}": [f"pkg_{i + 1}"] for i in range(40)}
    large_sec = ResolutionSection(
        success=True,
        pinned_versions={f"pkg_{i}": "1.0.0" for i in range(40)},
        dependency_graph=large_graph,
    )
    rep_large = DiagnosticReport(
        schema_version="1.0.0",
        tool_version="0.1.0",
        overall_status=StageStatus.PASSED,
        project_information=ProjectInfo(name="large", path="/tmp/large"),
        execution_environment=ExecutionEnvironmentInfo(
            operating_system="linux", architecture="x86_64", python_version="3.11"
        ),
        resolution=large_sec,
    )
    rendered_large = HtmlRenderer.render(rep_large)
    assert "Large dependency graph detected (40 nodes)" in rendered_large
