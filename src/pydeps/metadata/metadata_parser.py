"""Parser for PyPI JSON API responses into validated structured metadata models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

from pydeps.metadata.metadata_models import PackageRelease, ReleaseArtifact
from pydeps.models.dependencies import Dependency, DependencyType


def parse_wheel_platform_tags(filename: str) -> list[str]:
    """Extract platform tags from a wheel archive filename per PEP 427."""
    if not filename.endswith(".whl"):
        return []

    stem = filename[:-4]
    parts = stem.split("-")
    if len(parts) >= 5:
        # Format: {distribution}-{version}(-{build})?-{python}-{abi}-{platform}
        platform_part = parts[-1]
        # Platform part can contain multiple tags joined by '.' (e.g. manylinux1_x86_64)
        return platform_part.split(".")
    return []


def parse_requirement_entry(req_str: str) -> tuple[Dependency | None, str | None]:
    """Parse a single PEP 508 Requires-Dist entry into a Dependency model."""
    clean = req_str.strip()
    if not clean:
        return None, None

    try:
        req = Requirement(clean)
        dep = Dependency(
            name=canonicalize_name(req.name),
            version_specifier=str(req.specifier) if str(req.specifier) else None,
            extras=req.extras,
            environment_marker=str(req.marker) if req.marker else None,
            dependency_type=DependencyType.DIRECT,
        )
        return dep, None
    except InvalidRequirement as exc:
        return None, f"Malformed requirement string '{clean}': {exc}"


def parse_release_files(raw_files: list[dict[str, Any]]) -> list[ReleaseArtifact]:
    """Parse a list of file dictionaries from PyPI release JSON."""
    artifacts: list[ReleaseArtifact] = []

    for file_info in raw_files:
        filename = file_info.get("filename", "")
        if not filename:
            continue

        pkg_type = file_info.get("packagetype", "unknown")
        py_ver = file_info.get("python_version")
        req_py = file_info.get("requires_python")
        digests = file_info.get("digests", {})
        sha256 = digests.get("sha256")
        yanked = bool(file_info.get("yanked", False))
        size = file_info.get("size")
        upload_time = file_info.get("upload_time_iso_8601") or file_info.get("upload_time")

        platform_tags = parse_wheel_platform_tags(filename)

        artifacts.append(
            ReleaseArtifact(
                filename=filename,
                package_type=pkg_type,
                python_version=py_ver,
                platform_tags=platform_tags,
                requires_python=req_py,
                sha256=sha256,
                yanked=yanked,
                size=size,
                upload_time=upload_time,
            )
        )

    # Sort artifacts deterministically by filename
    artifacts.sort(key=lambda a: a.filename)
    return artifacts


def parse_pypi_release(
    data: dict[str, Any],
    version: str | None = None,
    source_name: str = "pypi_json_api",
) -> tuple[PackageRelease, list[str]]:
    """Convert raw PyPI JSON payload into a structured PackageRelease model."""
    diagnostics: list[str] = []
    info = data.get("info", {})

    raw_name = info.get("name") or data.get("name", "unknown")
    dist_name = canonicalize_name(raw_name)

    # Determine target version
    target_version = version or info.get("version", "")
    if not target_version:
        target_version = "0.0.0"

    requires_python = info.get("requires_python")
    summary = info.get("summary")
    project_urls = info.get("project_urls") or {}

    # Yanked status
    yanked = bool(info.get("yanked", False))
    yanked_reason = info.get("yanked_reason")

    # Parse dependencies (Requires-Dist)
    raw_requires = info.get("requires_dist") or []
    dependencies: list[Dependency] = []

    for req_line in raw_requires:
        dep, err = parse_requirement_entry(req_line)
        if dep is not None:
            dependencies.append(dep)
        if err is not None:
            diagnostics.append(err)

    # Parse files
    # PyPI response either has 'urls' for the targeted release, or 'releases' dictionary
    urls: list[dict[str, Any]] = []
    if "urls" in data and isinstance(data["urls"], list):
        urls = data["urls"]
    elif "releases" in data and isinstance(data["releases"], dict):
        urls = data["releases"].get(target_version, [])

    release_artifacts = parse_release_files(urls)

    # Provides extra
    provides_extra = info.get("provides_extra") or []

    release = PackageRelease(
        distribution_name=dist_name,
        version=target_version,
        requires_python=requires_python,
        requires_dist=dependencies,
        provides_extra=sorted(provides_extra),
        release_files=release_artifacts,
        yanked=yanked,
        yanked_reason=yanked_reason,
        metadata_source=source_name,
        retrieved_at=datetime.now(timezone.utc),
        summary=summary,
        project_urls=project_urls,
    )

    return release, diagnostics
