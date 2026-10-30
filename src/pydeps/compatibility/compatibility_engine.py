"""Core compatibility evaluation engine orchestrating Python, wheel, and marker checks."""

from __future__ import annotations

from packaging.tags import Tag

from pydeps.compatibility.artifact_evaluator import evaluate_release_artifacts
from pydeps.compatibility.marker_evaluator import MarkerEvaluator
from pydeps.compatibility.platform_profiles import (
    TargetPlatformProfile,
    create_platform_profile,
    get_supported_wheel_tags,
    is_valid_target_configuration,
)
from pydeps.compatibility.python_compatibility import evaluate_python_version
from pydeps.metadata.metadata_models import PackageRelease
from pydeps.models.compatibility import CompatibilityResult, CompatibilityStatus
from pydeps.models.project import TargetEnvironment


class CompatibilityEngine:
    """Evaluates Python package releases against cross-platform target environments."""

    def __init__(
        self,
        tag_cache: dict[str, frozenset[Tag]] | None = None,
    ) -> None:
        self._tag_cache: dict[str, frozenset[Tag]] = tag_cache if tag_cache is not None else {}

    def get_target_tags(
        self,
        target: TargetEnvironment,
        profile: TargetPlatformProfile | None = None,
    ) -> frozenset[Tag]:
        """Retrieve or compute target supported wheel tags with caching."""
        cache_key = target.platform_tag
        if cache_key in self._tag_cache:
            return self._tag_cache[cache_key]

        tags = get_supported_wheel_tags(target, profile=profile)
        self._tag_cache[cache_key] = tags
        return tags

    def evaluate_release(
        self,
        release: PackageRelease,
        target: TargetEnvironment,
        profile: TargetPlatformProfile | None = None,
        extra: str | None = None,
    ) -> CompatibilityResult:
        """Evaluate package release against target environment to produce CompatibilityResult."""
        pkg_name = release.distribution_name
        version = release.version
        prof = profile or create_platform_profile(target)

        evidence: list[str] = []
        unverified_conditions: list[str] = []
        warnings: list[str] = []

        # 1. Check target feasibility
        is_valid_cfg, invalid_reason = is_valid_target_configuration(target)
        if not is_valid_cfg:
            warnings.append(invalid_reason or "Non-standard target configuration")
            return CompatibilityResult(
                package_name=pkg_name,
                package_version=version,
                target_environment=target,
                status=CompatibilityStatus.UNVERIFIED,
                reason=f"Target environment configuration is not supported: {invalid_reason}",
                evidence=[f"target_configuration: {target.platform_tag} (unsupported)"],
                python_constraint_compatible=None,
                evaluated_python_constraints=release.requires_python,
                wheel_candidates=[],
                incompatible_wheels=[],
                has_source_distribution=False,
                sdist_name=None,
                marker_evaluations=[],
                evidence_source="configuration_check",
                unverified_conditions=[invalid_reason or "Invalid target configuration"],
                warnings=warnings,
            )

        # 2. Evaluate Python version compatibility
        py_eval = evaluate_python_version(
            requires_python=release.requires_python,
            target_python_version=target.python_version,
        )
        evidence.append(f"python_requires: {release.requires_python or 'none_declared'}")
        if py_eval.diagnostic:
            warnings.append(py_eval.diagnostic)
        if py_eval.status == CompatibilityStatus.UNVERIFIED:
            unverified_conditions.append(py_eval.reason)

        # 3. Evaluate artifacts (wheels and sdist)
        target_tags = self.get_target_tags(target, profile=prof)
        art_eval = evaluate_release_artifacts(
            release=release,
            target=target,
            profile=prof,
            supported_tags=target_tags,
        )
        warnings.extend(art_eval.warnings)
        if art_eval.has_compatible_wheel:
            evidence.append(f"compatible_wheels: {len(art_eval.compatible_wheels)} available")
        if art_eval.has_sdist:
            evidence.append(f"sdist: {art_eval.sdist_filename}")
        if art_eval.status == CompatibilityStatus.UNVERIFIED:
            unverified_conditions.extend(art_eval.reasons)

        # 4. Evaluate dependency environment markers
        marker_evaluator = MarkerEvaluator(target=target, profile=prof)
        marker_evals = marker_evaluator.evaluate_dependencies(release.requires_dist, extra=extra)

        applicable_deps: list[str] = []
        for m in marker_evals:
            if m.applies:
                applicable_deps.append(m.dependency_name)
            if m.status == CompatibilityStatus.UNVERIFIED:
                unverified_conditions.append(m.explanation)

        if applicable_deps:
            evidence.append(f"applicable_dependencies: {', '.join(sorted(set(applicable_deps)))}")

        # 5. Determine overall compatibility status
        # Definite incompatibility: Python version mismatch OR no wheels and no sdist
        if (
            py_eval.status == CompatibilityStatus.INCOMPATIBLE
            or art_eval.status == CompatibilityStatus.INCOMPATIBLE
        ):
            status = CompatibilityStatus.INCOMPATIBLE
            reasons = []
            if py_eval.status == CompatibilityStatus.INCOMPATIBLE:
                reasons.append(py_eval.reason)
            if art_eval.status == CompatibilityStatus.INCOMPATIBLE:
                reasons.extend(art_eval.reasons)
            overall_reason = " | ".join(reasons)

        # Unverified if either Python constraint or artifacts are unverified
        elif (
            py_eval.status == CompatibilityStatus.UNVERIFIED
            or art_eval.status == CompatibilityStatus.UNVERIFIED
            or len(unverified_conditions) > 0
        ):
            status = CompatibilityStatus.UNVERIFIED
            reasons = []
            if py_eval.status == CompatibilityStatus.UNVERIFIED:
                reasons.append(py_eval.reason)
            if art_eval.status == CompatibilityStatus.UNVERIFIED:
                reasons.extend(art_eval.reasons)
            if not reasons and unverified_conditions:
                reasons.extend(unverified_conditions)
            overall_reason = " | ".join(reasons)

        # Compatible when both Python version and artifact binary wheels are verified
        else:
            status = CompatibilityStatus.COMPATIBLE
            wheel_summary = f"{len(art_eval.compatible_wheels)} compatible wheel(s) available"
            overall_reason = (
                f"Release is compatible with target {target.platform_tag}. "
                f"{py_eval.reason} {wheel_summary}."
            )

        return CompatibilityResult(
            package_name=pkg_name,
            package_version=version,
            target_environment=target,
            status=status,
            reason=overall_reason,
            evidence=evidence,
            python_constraint_compatible=py_eval.is_compatible,
            evaluated_python_constraints=release.requires_python,
            wheel_candidates=art_eval.compatible_wheels,
            incompatible_wheels=art_eval.incompatible_wheels,
            has_source_distribution=art_eval.has_sdist,
            sdist_name=art_eval.sdist_filename,
            marker_evaluations=marker_evals,
            evidence_source=release.metadata_source,
            unverified_conditions=unverified_conditions,
            warnings=warnings,
        )
