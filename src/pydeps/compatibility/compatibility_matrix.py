"""Compatibility matrix builder aggregating evaluations across packages and targets."""

from __future__ import annotations

from collections.abc import Sequence

from packaging.utils import canonicalize_name

from pydeps.compatibility.compatibility_engine import CompatibilityEngine
from pydeps.metadata.metadata_models import MetadataResult, PackageRelease
from pydeps.models.compatibility import (
    CompatibilityMatrix,
    CompatibilityResult,
    CompatibilityStatus,
    PackageCompatibilityMatrix,
)
from pydeps.models.project import TargetEnvironment


class MatrixBuilder:
    """Coordinates batch evaluation of packages across multi-dimensional target environments."""

    def __init__(self, engine: CompatibilityEngine | None = None) -> None:
        self.engine = engine or CompatibilityEngine()

    def evaluate_package(
        self,
        release: PackageRelease,
        targets: Sequence[TargetEnvironment],
        extra: str | None = None,
    ) -> PackageCompatibilityMatrix:
        """Evaluate a single package release across multiple target environments."""
        results: dict[str, CompatibilityResult] = {}
        comp_count = 0
        incomp_count = 0
        unver_count = 0

        for target in targets:
            tag = target.platform_tag
            res = self.engine.evaluate_release(release, target=target, extra=extra)
            results[tag] = res

            if res.status == CompatibilityStatus.COMPATIBLE:
                comp_count += 1
            elif res.status == CompatibilityStatus.INCOMPATIBLE:
                incomp_count += 1
            else:
                unver_count += 1

        summary = {
            "compatible": comp_count,
            "incompatible": incomp_count,
            "unverified": unver_count,
            "total": len(targets),
        }

        return PackageCompatibilityMatrix(
            package_name=release.distribution_name,
            version=release.version,
            results=results,
            summary=summary,
        )

    def evaluate_matrix(
        self,
        releases: Sequence[PackageRelease] | dict[str, PackageRelease | MetadataResult],
        targets: Sequence[TargetEnvironment],
        extra: str | None = None,
    ) -> CompatibilityMatrix:
        """Build a comprehensive compatibility matrix across packages and targets."""
        # Normalize releases into list of PackageRelease
        release_list: list[PackageRelease] = []
        diagnostics: list[str] = []

        if isinstance(releases, dict):
            for key, val in releases.items():
                if isinstance(val, MetadataResult):
                    if val.success and val.metadata:
                        release_list.append(val.metadata)
                    else:
                        diags_str = ", ".join(val.diagnostics)
                        diag = f"Metadata retrieval failed for package '{key}': {diags_str}"
                        diagnostics.append(diag)
                elif isinstance(val, PackageRelease):
                    release_list.append(val)
        else:
            release_list = list(releases)

        # Deduplicate and sort targets by platform_tag
        unique_targets: dict[str, TargetEnvironment] = {}
        for t in targets:
            if t.platform_tag not in unique_targets:
                unique_targets[t.platform_tag] = t
        sorted_targets = [unique_targets[k] for k in sorted(unique_targets.keys())]

        # Deduplicate releases by package name
        unique_releases: dict[str, PackageRelease] = {}
        for r in release_list:
            canonical = canonicalize_name(r.distribution_name)
            if canonical not in unique_releases:
                unique_releases[canonical] = r

        sorted_releases = [unique_releases[k] for k in sorted(unique_releases.keys())]
        packages_list = [r.distribution_name for r in sorted_releases]

        entries: list[CompatibilityResult] = []
        matrix_dict: dict[str, dict[str, CompatibilityResult]] = {}

        for rel in sorted_releases:
            pkg_name = rel.distribution_name
            matrix_dict[pkg_name] = {}
            for target in sorted_targets:
                res = self.engine.evaluate_release(rel, target=target, extra=extra)
                matrix_dict[pkg_name][target.platform_tag] = res
                entries.append(res)

        matrix = CompatibilityMatrix(
            packages=packages_list,
            targets=sorted_targets,
            entries=entries,
            matrix=matrix_dict,
            diagnostics=diagnostics,
        )
        matrix.summary_counts = matrix.summary()
        return matrix
