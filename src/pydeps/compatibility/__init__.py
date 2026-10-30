"""Compatibility matrix engine package for cross-platform dependency analysis."""

from __future__ import annotations

from pydeps.compatibility.artifact_evaluator import evaluate_release_artifacts
from pydeps.compatibility.compatibility_engine import CompatibilityEngine
from pydeps.compatibility.compatibility_matrix import MatrixBuilder
from pydeps.compatibility.marker_evaluator import MarkerEvaluator, extract_marker_variables
from pydeps.compatibility.platform_profiles import (
    TargetPlatformProfile,
    create_platform_profile,
    get_supported_wheel_tags,
    is_valid_target_configuration,
)
from pydeps.compatibility.python_compatibility import (
    PythonVersionEvaluation,
    evaluate_python_version,
)
from pydeps.compatibility.wheel_compatibility import WheelEvaluation, evaluate_wheel_filename
from pydeps.models.compatibility import (
    ArtifactCompatibility,
    CompatibilityMatrix,
    CompatibilityResult,
    CompatibilityStatus,
    MarkerEvaluation,
    PackageCompatibility,
    PackageCompatibilityMatrix,
)

__all__ = [
    "ArtifactCompatibility",
    "CompatibilityEngine",
    "CompatibilityMatrix",
    "CompatibilityResult",
    "CompatibilityStatus",
    "MarkerEvaluation",
    "MarkerEvaluator",
    "MatrixBuilder",
    "PackageCompatibility",
    "PackageCompatibilityMatrix",
    "PythonVersionEvaluation",
    "TargetPlatformProfile",
    "WheelEvaluation",
    "create_platform_profile",
    "evaluate_python_version",
    "evaluate_release_artifacts",
    "evaluate_wheel_filename",
    "extract_marker_variables",
    "get_supported_wheel_tags",
    "is_valid_target_configuration",
]
