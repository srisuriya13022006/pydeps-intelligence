"""PyDeps dependency resolution subsystem."""

from __future__ import annotations

from pydeps_intelligence.resolver.conflict_analyzer import ConflictAnalyzer
from pydeps_intelligence.resolver.constraint_collector import ConstraintCollector
from pydeps_intelligence.resolver.dependency_classifier import DependencyClassifier
from pydeps_intelligence.resolver.dependency_resolver import DependencyResolver
from pydeps_intelligence.resolver.lockfile_exporter import LockfileExporter
from pydeps_intelligence.resolver.pip_backend import PipBackend
from pydeps_intelligence.resolver.resolution_orchestrator import ResolutionOrchestrator
from pydeps_intelligence.resolver.resolution_strategy import StrategyMapper
from pydeps_intelligence.resolver.resolution_workspace import ResolutionWorkspace
from pydeps_intelligence.resolver.uv_backend import UvBackend

__all__ = [
    "ConflictAnalyzer",
    "ConstraintCollector",
    "DependencyClassifier",
    "DependencyResolver",
    "LockfileExporter",
    "PipBackend",
    "ResolutionOrchestrator",
    "ResolutionWorkspace",
    "StrategyMapper",
    "UvBackend",
]
