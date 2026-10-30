"""Utilities for inspecting and querying release metadata objects."""

from __future__ import annotations

from collections.abc import Sequence

from pydeps.metadata.metadata_models import PackageRelease, ReleaseArtifact


def find_wheel_artifacts(release: PackageRelease) -> list[ReleaseArtifact]:
    """Return all wheel artifacts for a release."""
    return [f for f in release.release_files if f.package_type == "bdist_wheel" and not f.yanked]


def find_sdist_artifact(release: PackageRelease) -> ReleaseArtifact | None:
    """Return the source distribution artifact for a release, if available and not yanked."""
    for f in release.release_files:
        if f.package_type == "sdist" and not f.yanked:
            return f
    return None


def get_all_platform_tags(artifacts: Sequence[ReleaseArtifact]) -> set[str]:
    """Collect unique platform tags across a sequence of release artifacts."""
    tags: set[str] = set()
    for art in artifacts:
        tags.update(art.platform_tags)
    return tags
