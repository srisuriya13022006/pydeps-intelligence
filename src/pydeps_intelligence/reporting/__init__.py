"""PyDeps reporting and developer dashboard subsystem."""

from __future__ import annotations

from pydeps_intelligence.reporting.html_renderer import HtmlRenderer
from pydeps_intelligence.reporting.json_renderer import JsonRenderer
from pydeps_intelligence.reporting.report_builder import ReportBuilder
from pydeps_intelligence.reporting.report_comparison import ComparisonReport, ReportComparator
from pydeps_intelligence.reporting.report_schema import (
    DependencyHealthStatus,
    DiagnosticReport,
    RecommendationItem,
    RecommendationSeverity,
    StageResultSummary,
    StageStatus,
)

__all__ = [
    "ComparisonReport",
    "DependencyHealthStatus",
    "DiagnosticReport",
    "HtmlRenderer",
    "JsonRenderer",
    "RecommendationItem",
    "RecommendationSeverity",
    "ReportBuilder",
    "ReportComparator",
    "StageResultSummary",
    "StageStatus",
]
