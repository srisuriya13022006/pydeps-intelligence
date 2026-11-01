"""Artifact compatibility evaluation across wheels and source distributions."""

from __future__ import annotations

from packaging.tags import Tag

from pydeps_intelligence.compatibility.platform_profiles import (
    TargetPlatformProfile,
    create_platform_profile,
    get_supported_wheel_tags,
)
from pydeps_intelligence.compatibility.wheel_compatibility import evaluate_wheel_filename
from pydeps_intelligence.metadata.metadata_models import PackageRelease, ReleaseArtifact
from pydeps_intelligence.models.compatibility import ArtifactCompatibility, CompatibilityStatus
from pydeps_intelligence.models.project import TargetEnvironment


def evaluate_release_artifacts(
    release: PackageRelease,
    target: TargetEnvironment,
    profile: TargetPlatformProfile | None = None,
    supported_tags: frozenset[Tag] | None = None,
) -> ArtifactCompatibility:
    """Evaluate all release artifacts (wheels, sdists) against a target environment."""
    prof = profile or create_platform_profile(target)
    tags = supported_tags or get_supported_wheel_tags(target, profile=prof)

    compatible_wheels: list[str] = []
    incompatible_wheels: list[str] = []
    sdist_file: ReleaseArtifact | None = None
    warnings: list[str] = []
    reasons: list[str] = []

    # Check whole release yanked status
    if release.yanked:
        yank_msg = f"Release {release.distribution_name}=={release.version} was yanked on PyPI"
        if release.yanked_reason:
            yank_msg += f": {release.yanked_reason}"
        warnings.append(yank_msg)

    # 1. Handle missing/empty artifacts
    if not release.release_files:
        return ArtifactCompatibility(
            has_compatible_wheel=False,
            compatible_wheels=[],
            incompatible_wheels=[],
            has_sdist=False,
            sdist_filename=None,
            status=CompatibilityStatus.UNVERIFIED,
            reasons=["No artifact files declared in release metadata."],
            warnings=[*warnings, "Missing artifact metadata; compatibility unverified."],
        )

    # 2. Iterate through files
    for artifact in release.release_files:
        filename = artifact.filename

        if artifact.yanked:
            warnings.append(f"Artifact '{filename}' has been yanked on PyPI.")

        # Wheel evaluation
        if artifact.package_type == "bdist_wheel" or filename.endswith(".whl"):
            wheel_eval = evaluate_wheel_filename(
                filename=filename,
                supported_tags=tags,
                target_python_version=target.python_version,
                artifact_requires_python=artifact.requires_python,
            )
            if wheel_eval.is_compatible:
                compatible_wheels.append(filename)
            else:
                incompatible_wheels.append(filename)
                if wheel_eval.is_invalid:
                    warnings.append(wheel_eval.reason)

        # Source distribution detection
        elif (
            artifact.package_type == "sdist"
            or filename.endswith(".tar.gz")
            or filename.endswith(".zip")
            or filename.endswith(".tgz")
        ):
            if sdist_file is None:
                sdist_file = artifact

    has_compatible_wheel = len(compatible_wheels) > 0
    has_sdist = sdist_file is not None
    sdist_name = sdist_file.filename if sdist_file else None

    # 3. Determine status according to ADR-005 and P3 requirements
    if has_compatible_wheel:
        status = CompatibilityStatus.COMPATIBLE
        reasons.append(
            f"Found {len(compatible_wheels)} compatible binary wheel(s) for target "
            f"{target.platform_tag} (e.g. '{compatible_wheels[0]}')."
        )
    elif has_sdist:
        # Prebuilt wheel is missing, but sdist exists: unverified without runtime validation
        status = CompatibilityStatus.UNVERIFIED
        reasons.append(
            f"No compatible binary wheels found for target {target.platform_tag}. "
            f"Source distribution is available ('{sdist_name}'), but building from "
            f"source requires runtime validation (build tools, C/C++ compilers, headers)."
        )
    else:
        status = CompatibilityStatus.INCOMPATIBLE
        reasons.append(
            f"No compatible binary wheels and no source distributions available for target "
            f"{target.platform_tag}."
        )

    return ArtifactCompatibility(
        has_compatible_wheel=has_compatible_wheel,
        compatible_wheels=compatible_wheels,
        incompatible_wheels=incompatible_wheels,
        has_sdist=has_sdist,
        sdist_filename=sdist_name,
        status=status,
        reasons=reasons,
        warnings=warnings,
    )
