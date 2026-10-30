"""PEP 508 environment marker evaluator against target environment profiles."""

from __future__ import annotations

from typing import Any

from packaging.markers import InvalidMarker, Marker

from pydeps.compatibility.platform_profiles import TargetPlatformProfile, create_platform_profile
from pydeps.models.compatibility import CompatibilityStatus, MarkerEvaluation
from pydeps.models.dependencies import Dependency
from pydeps.models.project import TargetEnvironment


def extract_marker_variables(marker: Marker) -> set[str]:
    """Recursively extract all environment variable names referenced in a Marker AST."""
    variables: set[str] = set()

    def _traverse(node: Any) -> None:
        if isinstance(node, tuple):
            for part in node:
                if type(part).__name__ == "Variable":
                    variables.add(str(part.value))
        elif isinstance(node, list):
            for sub in node:
                _traverse(sub)

    if hasattr(marker, "_markers") and marker._markers:
        _traverse(marker._markers)

    return variables


class MarkerEvaluator:
    """Evaluates PEP 508 dependency markers against target platform profiles."""

    def __init__(
        self,
        target: TargetEnvironment,
        profile: TargetPlatformProfile | None = None,
    ) -> None:
        self.target = target
        self.profile = profile or create_platform_profile(target)

    def evaluate_dependency(
        self,
        dependency: Dependency,
        extra: str | None = None,
    ) -> MarkerEvaluation:
        """Evaluate a Dependency's environment marker against the target environment."""
        req_str = dependency.to_pep508() if hasattr(dependency, "to_pep508") else dependency.name
        marker_str = dependency.environment_marker
        target_tag = self.target.platform_tag

        # 1. Unconditional dependency (no marker specified)
        if not marker_str or not marker_str.strip():
            return MarkerEvaluation(
                requirement=req_str,
                dependency_name=dependency.name,
                marker_expression=None,
                target_environment=target_tag,
                applies=True,
                status=CompatibilityStatus.COMPATIBLE,
                explanation="Unconditional dependency; applies to all target environments.",
                missing_fields=[],
            )

        clean_marker = marker_str.strip()

        # 2. Parse Marker
        try:
            marker = Marker(clean_marker)
        except InvalidMarker as exc:
            return MarkerEvaluation(
                requirement=req_str,
                dependency_name=dependency.name,
                marker_expression=clean_marker,
                target_environment=target_tag,
                applies=None,
                status=CompatibilityStatus.UNVERIFIED,
                explanation=f"Malformed PEP 508 marker expression: {exc}",
                missing_fields=[],
            )

        # 3. Inspect referenced variables
        referenced_vars = extract_marker_variables(marker)
        known_vars = self.profile.get_known_marker_keys()

        # 'extra' is handled explicitly
        non_extra_vars = referenced_vars - {"extra"}
        missing_vars = sorted(list(non_extra_vars - known_vars))

        if missing_vars:
            missing_str = ", ".join(missing_vars)
            return MarkerEvaluation(
                requirement=req_str,
                dependency_name=dependency.name,
                marker_expression=clean_marker,
                target_environment=target_tag,
                applies=None,
                status=CompatibilityStatus.UNVERIFIED,
                explanation=(
                    f"Marker expression '{clean_marker}' references variable(s) not supplied "
                    f"by the target profile ({missing_str}). Evaluation unverified."
                ),
                missing_fields=missing_vars,
            )

        # 4. Construct complete, isolated environment dictionary
        marker_env = self.profile.to_marker_environment(extra=extra)

        # 5. Evaluate marker strictly within target environment
        try:
            applies = marker.evaluate(environment=marker_env)
        except Exception as exc:
            return MarkerEvaluation(
                requirement=req_str,
                dependency_name=dependency.name,
                marker_expression=clean_marker,
                target_environment=target_tag,
                applies=None,
                status=CompatibilityStatus.UNVERIFIED,
                explanation=f"Error evaluating marker '{clean_marker}': {exc}",
                missing_fields=[],
            )

        if applies:
            expl = (
                f"Marker '{clean_marker}' evaluates to True for target {target_tag}; "
                f"dependency applies."
            )
        else:
            expl = (
                f"Marker '{clean_marker}' evaluates to False for target {target_tag}; "
                f"dependency is excluded."
            )

        return MarkerEvaluation(
            requirement=req_str,
            dependency_name=dependency.name,
            marker_expression=clean_marker,
            target_environment=target_tag,
            applies=applies,
            status=CompatibilityStatus.COMPATIBLE,
            explanation=expl,
            missing_fields=[],
        )

    def evaluate_dependencies(
        self,
        dependencies: list[Dependency],
        extra: str | None = None,
    ) -> list[MarkerEvaluation]:
        """Evaluate a collection of declared dependencies against the target environment."""
        return [self.evaluate_dependency(dep, extra=extra) for dep in dependencies]
