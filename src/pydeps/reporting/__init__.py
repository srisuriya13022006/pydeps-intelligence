"""PyDeps reporting and developer dashboard subsystem."""

from __future__ import annotations

from pydeps.reporting.html_renderer import HtmlRenderer
from pydeps.reporting.json_renderer import JsonRenderer
from pydeps.reporting.report_builder import ReportBuilder
from pydeps.reporting.report_comparison import ComparisonReport, ReportComparator
from pydeps.reporting.report_schema import (
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
