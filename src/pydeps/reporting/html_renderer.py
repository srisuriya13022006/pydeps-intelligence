"""Self-contained, offline HTML dashboard renderer for PyDeps diagnostic reports."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from pydeps.reporting.report_schema import DiagnosticReport, StageStatus


class HtmlRenderer:
    """Renders DiagnosticReport into a modern, self-contained, offline HTML dashboard."""

    @classmethod
    def _escape(cls, val: Any) -> str:
        """Context-safe string escaping removing null bytes and escaping HTML/XML entities."""
        if val is None:
            return ""
        s = str(val).replace("\x00", "")
        return html.escape(s, quote=True)

    @classmethod
    def render(cls, report: DiagnosticReport) -> str:
        """Generate self-contained HTML markup without external dependencies."""
        esc = cls._escape

        # Distinct status colors
        p_color = cls._status_color(report.pipeline_status)
        h_color = (
            "passed"
            if report.dependency_health_status.value == "healthy"
            else "failed"
            if report.dependency_health_status.value == "problematic"
            else "warning"
        )
        v_color = cls._status_color(report.runtime_validation_status)

        # Embedded safe JSON data (escaping closing script tags, HTML markup, and quotes)
        safe_json_data = (
            json.dumps(report.model_dump(mode="json"), ensure_ascii=False)
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("&", "\\u0026")
            .replace("'", "\\u0027")
        )

        stage_cards_html = cls._render_stage_cards(report)
        source_section_html = cls._render_source_section(report)
        pkg_section_html = cls._render_package_section(report)
        compat_section_html = cls._render_compat_section(report)
        resolution_section_html = cls._render_resolution_section(report)
        validation_section_html = cls._render_validation_section(report)
        recommendations_section_html = cls._render_recommendations_section(report)

        return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PyDeps Report: {esc(report.project_information.name)}</title>
<style>
:root {{
  --bg-primary: #0f172a;
  --bg-secondary: #1e293b;
  --bg-tertiary: #334155;
  --text-primary: #f8fafc;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
  --border-color: #334155;
  --accent-blue: #38bdf8;
  --status-passed: #22c55e;
  --status-failed: #ef4444;
  --status-warning: #f59e0b;
  --status-neutral: #64748b;
  --card-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -2px rgba(0, 0, 0, 0.3);
  --font-sans: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}}

[data-theme="light"] {{
  --bg-primary: #f8fafc;
  --bg-secondary: #ffffff;
  --bg-tertiary: #f1f5f9;
  --text-primary: #0f172a;
  --text-secondary: #475569;
  --text-muted: #94a3b8;
  --border-color: #e2e8f0;
  --accent-blue: #0284c7;
  --card-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
}}

* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: var(--font-sans);
  background-color: var(--bg-primary);
  color: var(--text-primary);
  line-height: 1.5;
  padding: 24px;
}}

.container {{
  max-width: 1400px;
  margin: 0 auto;
}}

header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--border-color);
}}

.header-title {{
  display: flex;
  align-items: center;
  gap: 16px;
}}

.logo-badge {{
  background: linear-gradient(135deg, #0284c7, #38bdf8);
  color: #fff;
  font-weight: 800;
  font-size: 1.1rem;
  padding: 6px 14px;
  border-radius: 8px;
  letter-spacing: 0.5px;
}}

.theme-toggle {{
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  padding: 8px 16px;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.85rem;
}}

.badge {{
  display: inline-block;
  padding: 4px 10px;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}}
.badge-passed {{ background-color: rgba(34, 197, 94, 0.15); color: #22c55e; border: 1px solid rgba(34, 197, 94, 0.3); }}
.badge-failed {{ background-color: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3); }}
.badge-warning {{ background-color: rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.3); }}
.badge-neutral {{ background-color: rgba(100, 116, 139, 0.15); color: #94a3b8; border: 1px solid rgba(100, 116, 139, 0.3); }}

.metric-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
  margin-bottom: 28px;
}}

.card {{
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 20px;
  box-shadow: var(--card-shadow);
}}

.card-title {{
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--text-muted);
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}}

.card-value {{
  font-size: 1.8rem;
  font-weight: 700;
  color: var(--text-primary);
}}

.card-subtext {{
  font-size: 0.8rem;
  color: var(--text-secondary);
  margin-top: 4px;
}}

.section {{
  margin-bottom: 32px;
}}

.section-title {{
  font-size: 1.3rem;
  font-weight: 700;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 10px;
}}

table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}}

th, td {{
  padding: 12px 16px;
  text-align: left;
  border-bottom: 1px solid var(--border-color);
}}

th {{
  background-color: var(--bg-tertiary);
  color: var(--text-secondary);
  font-weight: 600;
}}

tr:hover {{
  background-color: rgba(255, 255, 255, 0.02);
}}

.code {{
  font-family: var(--font-mono);
  font-size: 0.85rem;
  background: var(--bg-tertiary);
  padding: 2px 6px;
  border-radius: 4px;
}}

.matrix-grid {{
  overflow-x: auto;
  border-radius: 8px;
  border: 1px solid var(--border-color);
}}

.heatmap-cell {{
  text-align: center;
  font-weight: 700;
  font-size: 0.75rem;
}}

.rec-card {{
  border-left: 4px solid var(--status-warning);
  margin-bottom: 12px;
  padding: 16px;
  background-color: var(--bg-secondary);
  border-radius: 0 8px 8px 0;
}}
.rec-critical {{ border-left-color: var(--status-failed); }}
.rec-info {{ border-left-color: var(--accent-blue); }}

.rec-title {{
  font-weight: 700;
  font-size: 1rem;
  margin-bottom: 4px;
}}

.rec-body {{
  color: var(--text-secondary);
  font-size: 0.9rem;
  margin-bottom: 8px;
}}

.rec-evidence {{
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  padding: 8px 12px;
  border-radius: 6px;
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: var(--text-secondary);
  margin-top: 8px;
}}

.graph-container {{
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 24px;
  overflow-x: auto;
}}

.node-pill {{
  display: inline-block;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  padding: 6px 12px;
  border-radius: 8px;
  margin: 4px;
  font-family: var(--font-mono);
  font-size: 0.85rem;
}}

footer {{
  margin-top: 48px;
  padding-top: 24px;
  border-top: 1px solid var(--border-color);
  text-align: center;
  color: var(--text-muted);
  font-size: 0.85rem;
}}
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="header-title">
      <span class="logo-badge">PyDeps</span>
      <div>
        <h1 style="font-size: 1.5rem; font-weight: 700;">{esc(report.project_information.name or "Project Report")}</h1>
        <p style="color: var(--text-secondary); font-size: 0.85rem;">{esc(report.project_information.path)} &bull; {report.project_information.analysis_timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")}</p>
      </div>
    </div>
    <div style="display: flex; flex-wrap: wrap; align-items: center; gap: 8px;">
      <span class="badge badge-{p_color}" title="Diagnostic Pipeline Execution Status">Pipeline: {report.pipeline_status.value}</span>
      <span class="badge badge-{h_color}" title="Evidence-Backed Dependency Health">Health: {report.dependency_health_status.value}</span>
      <span class="badge badge-{v_color}" title="Isolated Runtime Validation Status">Validation: {report.runtime_validation_status.value}</span>
      <button class="theme-toggle" id="themeBtn" onclick="toggleTheme()">Theme</button>
    </div>
  </header>

  <!-- Metric Overview Cards -->
  <div class="metric-grid">
    <div class="card">
      <div class="card-title">Scanned Files</div>
      <div class="card-value">{report.source_analysis.total_files}</div>
      <div class="card-subtext">{report.source_analysis.total_imports} imports analyzed</div>
    </div>
    <div class="card">
      <div class="card-title">Mapped Packages</div>
      <div class="card-value">{len(report.package_intelligence.mappings)}</div>
      <div class="card-subtext">{len(report.package_intelligence.ambiguous_mappings)} ambiguous mappings</div>
    </div>
    <div class="card">
      <div class="card-title">Resolution</div>
      <div class="card-value" style="color: {"var(--status-passed)" if report.resolution.success else "var(--status-failed)"}">
        {"SUCCESS" if report.resolution.success else "CONFLICT"}
      </div>
      <div class="card-subtext">{len(report.resolution.pinned_versions)} pinned dependencies</div>
    </div>
    <div class="card">
      <div class="card-title">Compatibility</div>
      <div class="card-value" style="color: {"var(--status-failed)" if report.compatibility.incompatible_count > 0 else "var(--status-passed)"}">
        {report.compatibility.compatible_count} / {report.compatibility.compatible_count + report.compatibility.incompatible_count + report.compatibility.unverified_count}
      </div>
      <div class="card-subtext">{report.compatibility.incompatible_count} incompatible targets</div>
    </div>
  </div>

  <!-- Stage Pipeline Execution -->
  {stage_cards_html}

  <!-- Recommendations -->
  {recommendations_section_html}

  <!-- Source Analysis -->
  {source_section_html}

  <!-- Package Intelligence -->
  {pkg_section_html}

  <!-- Compatibility Matrix -->
  {compat_section_html}

  <!-- Resolution & Graph -->
  {resolution_section_html}

  <!-- Runtime Validation -->
  {validation_section_html}

  <footer>
    Generated by PyDeps v{esc(report.tool_version)} &bull; Schema v{esc(report.schema_version)} &bull; Self-contained offline report
  </footer>
</div>

<script id="pydeps-report-data" type="application/json">{safe_json_data}</script>
<script>
function toggleTheme() {{
  const html = document.documentElement;
  const current = html.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
}}
</script>
</body>
</html>
"""

    @classmethod
    def _status_color(cls, status: StageStatus) -> str:
        if status in (StageStatus.PASSED,):
            return "passed"
        if status in (StageStatus.FAILED, StageStatus.BLOCKED_BY_POLICY):
            return "failed"
        if status in (StageStatus.PARTIAL, StageStatus.UNVERIFIED):
            return "warning"
        return "neutral"

    @classmethod
    def _render_stage_cards(cls, report: DiagnosticReport) -> str:
        esc = cls._escape
        items_html = []
        for name, stage in report.stage_results.items():
            color = cls._status_color(stage.status)
            items_html.append(f"""
              <div style="background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: 8px; padding: 12px; text-align: center;">
                <div style="font-size: 0.75rem; font-weight: 700; text-transform: uppercase; color: var(--text-muted);">{esc(name)}</div>
                <div style="margin: 8px 0;"><span class="badge badge-{color}">{stage.status.value}</span></div>
                <div style="font-size: 0.75rem; color: var(--text-secondary);">{stage.duration_seconds:.2f}s</div>
              </div>
            """)

        grid = "".join(items_html)
        return f"""
        <div class="section">
          <h2 class="section-title">Diagnostic Pipeline Stages</h2>
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 12px;">
            {grid}
          </div>
        </div>
        """

    @classmethod
    def _render_recommendations_section(cls, report: DiagnosticReport) -> str:
        esc = cls._escape
        if not report.recommendations:
            return """
            <div class="section">
              <h2 class="section-title">Recommendations</h2>
              <div class="card" style="color: var(--status-passed); font-weight: 600;">
                All dependency health and compatibility evaluations passed with zero active warnings.
              </div>
            </div>
            """

        items_html = []
        for rec in report.recommendations:
            css_cls = "rec-warning"
            if rec.severity.value == "critical":
                css_cls = "rec-critical"
            elif rec.severity.value == "info":
                css_cls = "rec-info"

            evidence_items = "".join(f"<li>{esc(e)}</li>" for e in rec.evidence)
            evidence_html = (
                f'<div class="rec-evidence"><ul>{evidence_items}</ul></div>' if rec.evidence else ""
            )
            remedy_html = (
                f'<div style="margin-top: 8px; font-size: 0.85rem; color: var(--accent-blue);"><strong>Remedy:</strong> {esc(rec.actionable_remedy)}</div>'
                if rec.actionable_remedy
                else ""
            )

            items_html.append(f"""
            <div class="rec-card {css_cls}">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span class="rec-title">{esc(rec.title)}</span>
                <span class="badge badge-{css_cls.replace("rec-", "")}">{rec.severity.value}</span>
              </div>
              <div class="rec-body">{esc(rec.description)}</div>
              {remedy_html}
              {evidence_html}
            </div>
            """)

        return f"""
        <div class="section">
          <h2 class="section-title">Developer Guidance &amp; Recommendations</h2>
          <div>{"".join(items_html)}</div>
        </div>
        """

    @classmethod
    def _render_source_section(cls, report: DiagnosticReport) -> str:
        esc = cls._escape
        sec = report.source_analysis

        top_ext = "".join(
            f'<span class="node-pill">{esc(c)}</span>' for c in sec.external_candidates[:24]
        )
        top_std = "".join(
            f'<span class="node-pill">{esc(c)}</span>' for c in sec.standard_library[:24]
        )

        return f"""
        <div class="section">
          <h2 class="section-title">Source Intelligence (AST Analysis)</h2>
          <div class="card">
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; margin-bottom: 16px;">
              <div><strong>Scanned Source Files:</strong> {sec.total_files}</div>
              <div><strong>Total Import Statements:</strong> {sec.total_imports}</div>
              <div><strong>Standard Library Imports:</strong> {len(sec.standard_library)}</div>
              <div><strong>Local Project Imports:</strong> {len(sec.local_imports)}</div>
              <div><strong>External Candidates:</strong> {len(sec.external_candidates)}</div>
              <div><strong>Dynamic Imports:</strong> {len(sec.dynamic_imports)}</div>
            </div>
            <div style="margin-top: 16px;">
              <div style="font-weight: 600; font-size: 0.85rem; color: var(--text-muted); margin-bottom: 8px;">EXTERNAL CANDIDATES DISCOVERED</div>
              <div>{top_ext or "<em>None</em>"}</div>
            </div>
            <div style="margin-top: 16px;">
              <div style="font-weight: 600; font-size: 0.85rem; color: var(--text-muted); margin-bottom: 8px;">STANDARD LIBRARY MODULES USED</div>
              <div>{top_std or "<em>None</em>"}</div>
            </div>
          </div>
        </div>
        """

    @classmethod
    def _render_package_section(cls, report: DiagnosticReport) -> str:
        esc = cls._escape
        sec = report.package_intelligence

        rows = []
        for imp_name, dist_name in sorted(sec.mappings.items()):
            conf = sec.confidence_levels.get(imp_name, "HIGH")
            conf_badge = "badge-passed" if conf == "HIGH" else "badge-warning"
            rows.append(f"""
            <tr>
              <td><code class="code">{esc(imp_name)}</code></td>
              <td><strong>{esc(dist_name)}</strong></td>
              <td><span class="badge {conf_badge}">{esc(conf)}</span></td>
            </tr>
            """)

        table_rows = (
            "".join(rows)
            if rows
            else '<tr><td colspan="3">No external mappings identified.</td></tr>'
        )

        ambig_html = ""
        if sec.ambiguous_mappings:
            ambig_items = []
            for imp, cand in sec.ambiguous_mappings.items():
                ambig_items.append(
                    f'<li><code class="code">{esc(imp)}</code>: {", ".join(esc(c) for c in cand)}</li>'
                )
            ambig_html = f"""
            <div style="margin-top: 16px; padding: 12px; background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 8px;">
              <div style="font-weight: 700; color: #f59e0b; margin-bottom: 4px;">Ambiguous Mappings Requiring Configuration</div>
              <ul style="padding-left: 20px; font-size: 0.85rem;">{"".join(ambig_items)}</ul>
            </div>
            """

        return f"""
        <div class="section">
          <h2 class="section-title">Package Intelligence &amp; PyPI Mappings</h2>
          <div class="card">
            <table>
              <thead>
                <tr>
                  <th>Import Name</th>
                  <th>PyPI Distribution Package</th>
                  <th>Mapping Confidence</th>
                </tr>
              </thead>
              <tbody>
                {table_rows}
              </tbody>
            </table>
            {ambig_html}
          </div>
        </div>
        """

    @classmethod
    def _render_compat_section(cls, report: DiagnosticReport) -> str:
        esc = cls._escape
        sec = report.compatibility
        if not sec.matrix or not sec.evaluated_targets:
            return """
            <div class="section">
              <h2 class="section-title">Compatibility Matrix</h2>
              <div class="card" style="color: var(--text-muted);">Compatibility matrix was not evaluated.</div>
            </div>
            """

        # Build matrix table headers (Packages as columns, Targets as rows)
        pkgs = sec.evaluated_packages
        header_th = "".join(f"<th>{esc(p)}</th>" for p in pkgs)

        rows = []
        for t in sec.evaluated_targets:
            t_id = t["id"]
            cells = [f"<td><strong>{esc(t_id)}</strong></td>"]
            t_map = sec.matrix.get(t_id, {})
            for p in pkgs:
                item = t_map.get(p, {})
                stat = item.get("status", "unverified")
                reason = item.get("reason", "")
                badge_cls = (
                    "badge-passed"
                    if stat == "compatible"
                    else "badge-failed"
                    if stat == "incompatible"
                    else "badge-neutral"
                )
                cells.append(f"""
                <td class="heatmap-cell" title="{esc(reason)}">
                  <span class="badge {badge_cls}">{stat[:4]}</span>
                </td>
                """)
            rows.append(f"<tr>{''.join(cells)}</tr>")

        return f"""
        <div class="section">
          <h2 class="section-title">Cross-Platform Compatibility Matrix</h2>
          <div class="card matrix-grid">
            <table>
              <thead>
                <tr>
                  <th>Target Platform</th>
                  {header_th}
                </tr>
              </thead>
              <tbody>
                {"".join(rows)}
              </tbody>
            </table>
          </div>
        </div>
        """

    @classmethod
    def _render_resolution_section(cls, report: DiagnosticReport) -> str:
        esc = cls._escape
        sec = report.resolution
        if not sec.pinned_versions and not sec.conflicts:
            return """
            <div class="section">
              <h2 class="section-title">Dependency Resolution</h2>
              <div class="card" style="color: var(--text-muted);">Dependency resolution was not performed.</div>
            </div>
            """

        rows = []
        for pkg, ver in sorted(sec.pinned_versions.items()):
            dep_type = "DIRECT" if pkg in sec.direct_packages else "TRANSITIVE"
            badge_cls = "badge-passed" if dep_type == "DIRECT" else "badge-neutral"
            deps = sec.dependency_graph.get(pkg, [])
            deps_str = ", ".join(esc(d) for d in deps) if deps else "<em>None</em>"
            rows.append(f"""
            <tr>
              <td><code class="code">{esc(pkg)}</code></td>
              <td><strong>{esc(ver)}</strong></td>
              <td><span class="badge {badge_cls}">{dep_type}</span></td>
              <td><span style="font-size: 0.8rem; color: var(--text-secondary);">{deps_str}</span></td>
            </tr>
            """)

        # Dependency graph visual representation (SVG with fallback for large graphs)
        total_nodes = len(sec.dependency_graph)
        svg_html = ""
        if 0 < total_nodes <= 35:
            # Deterministic SVG dependency tree visualization
            svg_width = 800
            direct_nodes = (
                sec.direct_packages
                or [pkg for pkg, deps in sec.dependency_graph.items() if deps][:6]
            )
            if not direct_nodes:
                direct_nodes = list(sec.dependency_graph.keys())[:6]

            level_0 = sorted(direct_nodes)[:6]
            level_1 = []
            edges = []
            for parent in level_0:
                for child in sec.dependency_graph.get(parent, [])[:4]:
                    if child not in level_1:
                        level_1.append(child)
                    edges.append((parent, child))

            svg_height = max(160, (max(len(level_0), len(level_1)) * 48) + 40)

            node_positions: dict[str, tuple[int, int]] = {}
            for i, node in enumerate(level_0):
                y = 40 + (i * 44)
                node_positions[node] = (140, y)

            for j, node in enumerate(level_1[:8]):
                y = 40 + (j * 44)
                node_positions[node] = (540, y)

            svg_elements: list[str] = [
                f'<svg width="{svg_width}" height="{svg_height}" viewBox="0 0 {svg_width} {svg_height}" xmlns="http://www.w3.org/2000/svg" style="max-width: 100%; height: auto;">',
                "<defs>",
                '  <linearGradient id="rootGrad" x1="0%" y1="0%" x2="100%" y2="100%">',
                '    <stop offset="0%" stop-color="#0284c7"/>',
                '    <stop offset="100%" stop-color="#38bdf8"/>',
                "  </linearGradient>",
                "</defs>",
            ]

            for parent, child in edges:
                if parent in node_positions and child in node_positions:
                    x1, y1 = node_positions[parent]
                    x2, y2 = node_positions[child]
                    cx1 = x1 + 160
                    cx2 = x2 - 160
                    svg_elements.append(
                        f'<path d="M {x1 + 70} {y1} C {cx1} {y1}, {cx2} {y2}, {x2 - 70} {y2}" fill="none" stroke="var(--border-color)" stroke-width="2"/>'
                    )

            for node, (x, y) in node_positions.items():
                is_root = node in level_0
                fill_color = "url(#rootGrad)" if is_root else "var(--bg-tertiary)"
                stroke_color = "#38bdf8" if is_root else "var(--border-color)"
                label_color = "#ffffff" if is_root else "var(--text-primary)"
                svg_elements.append(
                    f'<rect x="{x - 70}" y="{y - 16}" width="140" height="32" rx="6" fill="{fill_color}" stroke="{stroke_color}" stroke-width="1.5"/>'
                )
                svg_elements.append(
                    f'<text x="{x}" y="{y + 4}" fill="{label_color}" font-family="monospace" font-size="11" font-weight="600" text-anchor="middle">{esc(node[:18])}</text>'
                )

            svg_elements.append("</svg>")
            svg_html = f"""
            <div style="margin-top: 16px; margin-bottom: 20px; overflow-x: auto; background: var(--bg-primary); padding: 16px; border-radius: 8px; border: 1px solid var(--border-color);">
              <div style="font-size: 0.8rem; font-weight: 700; color: var(--text-muted); margin-bottom: 8px; text-transform: uppercase;">Direct &rarr; Transitive Dependency Graph</div>
              {"".join(svg_elements)}
            </div>
            """
        elif total_nodes > 35:
            svg_html = f"""
            <div style="margin-top: 16px; margin-bottom: 16px; padding: 12px; background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.2); border-radius: 8px;">
              <span style="font-size: 0.85rem; color: var(--accent-blue);">Large dependency graph detected ({total_nodes} nodes). Displaying tabular adjacency list below to ensure fast rendering.</span>
            </div>
            """

        # Dependency graph visual representation (SVG or node trees)
        graph_nodes = []
        for pkg, deps in sorted(sec.dependency_graph.items()):
            if deps:
                dep_pills = " ".join(f'<span class="node-pill">{esc(d)}</span>' for d in deps)
                graph_nodes.append(f"""
                <div style="margin-bottom: 8px;">
                  <strong class="code">{esc(pkg)}</strong> &rarr; {dep_pills}
                </div>
                """)

        graph_html = f"""
        <div style="margin-top: 20px;">
          <h3 style="font-size: 1rem; margin-bottom: 12px; color: var(--text-secondary);">Dependency Graph Adjacency</h3>
          {svg_html}
          <div class="graph-container">
            {"".join(graph_nodes) or "<em>No transitive dependencies mapped in graph.</em>"}
          </div>
        </div>
        """

        return f"""
        <div class="section">
          <h2 class="section-title">Dependency Resolution (Backend: {esc(sec.backend)}, Strategy: {esc(sec.strategy)})</h2>
          <div class="card">
            <table>
              <thead>
                <tr>
                  <th>Package Name</th>
                  <th>Pinned Version</th>
                  <th>Requirement Type</th>
                  <th>Dependencies</th>
                </tr>
              </thead>
              <tbody>
                {"".join(rows)}
              </tbody>
            </table>
            {graph_html}
          </div>
        </div>
        """

    @classmethod
    def _render_validation_section(cls, report: DiagnosticReport) -> str:
        esc = cls._escape
        sec = report.validation
        if not sec.executed:
            return """
            <div class="section">
              <h2 class="section-title">Runtime Environment Validation</h2>
              <div class="card" style="color: var(--text-muted);">
                Runtime validation was not authorized or executed during this diagnosis run.
              </div>
            </div>
            """

        rows = []
        for res in sec.import_results:
            color = "badge-passed" if res.get("status") == "passed" else "badge-failed"
            rows.append(f"""
            <tr>
              <td><code class="code">{esc(res.get("module", ""))}</code></td>
              <td>{esc(res.get("distribution") or "")}</td>
              <td><span class="badge {color}">{esc(res.get("status", ""))}</span></td>
              <td>{res.get("duration", 0):.4f}s</td>
            </tr>
            """)

        table_html = (
            f"""
        <table style="margin-top: 16px;">
          <thead>
            <tr>
              <th>Module Tested</th>
              <th>Distribution</th>
              <th>Import Status</th>
              <th>Execution Time</th>
            </tr>
          </thead>
          <tbody>
            {"".join(rows)}
          </tbody>
        </table>
        """
            if rows
            else ""
        )

        return f"""
        <div class="section">
          <h2 class="section-title">Runtime Environment Validation</h2>
          <div class="card">
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px;">
              <div><strong>Runner:</strong> {esc(sec.runner_type or "local")}</div>
              <div><strong>Isolation Level:</strong> {esc(sec.isolation_level or "host_venv")}</div>
              <div><strong>Execution Policy:</strong> {esc(sec.execution_policy or "trusted_local")}</div>
              <div><strong>Installed Packages:</strong> {len(sec.installed_packages)}</div>
            </div>
            {table_html}
          </div>
        </div>
        """

    @classmethod
    def export_html(cls, report: DiagnosticReport, output_file: Path | str) -> Path:
        """Export the rendered HTML dashboard to disk."""
        out_path = Path(output_file).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        content = cls.render(report)
        out_path.write_text(content, encoding="utf-8")
        return out_path
