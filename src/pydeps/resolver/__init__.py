"""PyDeps dependency resolution subsystem."""

from __future__ import annotations

from pydeps.resolver.conflict_analyzer import ConflictAnalyzer
from pydeps.resolver.constraint_collector import ConstraintCollector
from pydeps.resolver.dependency_classifier import DependencyClassifier
from pydeps.resolver.dependency_resolver import DependencyResolver
from pydeps.resolver.lockfile_exporter import LockfileExporter
from pydeps.resolver.pip_backend import PipBackend
from pydeps.resolver.resolution_orchestrator import ResolutionOrchestrator
from pydeps.resolver.resolution_strategy import StrategyMapper
from pydeps.resolver.resolution_workspace import ResolutionWorkspace
from pydeps.resolver.uv_backend import UvBackend

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
