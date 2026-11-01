"""Structured diagnostic analyzer for dependency resolution conflicts and failures."""

from __future__ import annotations

import re

from pydeps_intelligence.models.dependencies import ResolutionConflict


class ConflictAnalyzer:
    """Analyzes raw resolver error outputs from uv or pip to build structured conflict reports."""

    @staticmethod
    def analyze_uv_error(
        stderr: str,
        stdout: str = "",
        target_environment: str | None = None,
    ) -> list[ResolutionConflict]:
        """Extract structured conflict details from uv resolution failures."""
        combined = f"{stderr}\n{stdout}"
        conflicts: list[ResolutionConflict] = []

        # 1. Version incompatibility conflict:
        # e.g.: "Because package-a==1.0.0 depends on package-b>=2.0 and package-c depends..."
        version_conflict_match = re.search(
            r"Because\s+(.*?)\s+and\s+(.*?),\s+we\s+can\s+conclude\s+that.*?"
            r"(incompatible|conflict|cannot be used)",
            combined,
            re.IGNORECASE | re.DOTALL,
        )
        if version_conflict_match:
            cause_1 = version_conflict_match.group(1).strip()
            cause_2 = version_conflict_match.group(2).strip()

            # Find package name
            pkg_match = re.search(
                r"\b([a-zA-Z0-9_\-\.]+)\b(?:\s*==|\s*>=|\s*<=|\s*<|\s*>)", cause_1
            )
            pkg_name = pkg_match.group(1) if pkg_match else "unknown"

            conflicts.append(
                ResolutionConflict(
                    package_name=pkg_name,
                    conflicting_requirements=[cause_1, cause_2],
                    source_packages=[],
                    target_environment=target_environment,
                    resolver_backend="uv",
                    error_category="version_conflict",
                    original_diagnostics=combined.strip(),
                    suggested_investigation=(
                        f"Check dependency constraints requiring '{pkg_name}'. "
                        "Conflicting bounds cannot be simultaneously satisfied."
                    ),
                )
            )
            return conflicts

        # 2. No matching distribution for Python version:
        no_release_match = re.search(
            r"(?:No solution found|No matching distribution found).*?"
            r"(?:package|distribution)\s+[`']?([a-zA-Z0-9_\-\.]+)[`']?.*?"
            r"(?:no releases matching|requires python)\s*([^\n\.]+)",
            combined,
            re.IGNORECASE | re.DOTALL,
        )
        if no_release_match:
            pkg_name = no_release_match.group(1)
            detail = no_release_match.group(2).strip()
            conflicts.append(
                ResolutionConflict(
                    package_name=pkg_name,
                    conflicting_requirements=[detail],
                    source_packages=[],
                    target_environment=target_environment,
                    resolver_backend="uv",
                    error_category="no_matching_release",
                    original_diagnostics=combined.strip(),
                    suggested_investigation=(
                        f"Package '{pkg_name}' has no releases satisfying requested "
                        f"Python version or platform constraints. "
                        "Verify target Python support in package metadata."
                    ),
                )
            )
            return conflicts

        # 3. Binary-only wheel failure:
        # e.g.: "No pre-built wheel available for `scipy` and source builds disabled (--no-build)"
        no_wheel_match = re.search(
            r"No (?:pre-built|compatible) wheel available for [`']?([a-zA-Z0-9_\-\.]+)[`']?",
            combined,
            re.IGNORECASE,
        )
        if no_wheel_match:
            pkg_name = no_wheel_match.group(1)
            conflicts.append(
                ResolutionConflict(
                    package_name=pkg_name,
                    conflicting_requirements=["binary wheel required (--no-build enabled)"],
                    source_packages=[],
                    target_environment=target_environment,
                    resolver_backend="uv",
                    error_category="no_compatible_wheel",
                    original_diagnostics=combined.strip(),
                    suggested_investigation=(
                        f"No prebuilt binary wheel exists for '{pkg_name}' on "
                        f"target environment {target_environment}. "
                        "Source build is required or target architecture/OS is unsupported."
                    ),
                )
            )
            return conflicts

        # 4. Network or registry failure:
        if (
            "Failed to fetch" in combined
            or "Could not resolve host" in combined
            or "404 Not Found" in combined
        ):
            conflicts.append(
                ResolutionConflict(
                    package_name="network_or_index",
                    conflicting_requirements=[],
                    source_packages=[],
                    target_environment=target_environment,
                    resolver_backend="uv",
                    error_category="registry_failure",
                    original_diagnostics=combined.strip(),
                    suggested_investigation=(
                        "Check internet connectivity, PyPI availability, or custom index URL."
                    ),
                )
            )
            return conflicts

        # 5. Generic fallback conflict:
        # Try to find any quoted package name
        pkg_generic = re.search(r"[`']([a-zA-Z0-9_\-\.]+)[`']", combined)
        detected_pkg = pkg_generic.group(1) if pkg_generic else "unresolved"

        conflicts.append(
            ResolutionConflict(
                package_name=detected_pkg,
                conflicting_requirements=[combined[:300].strip()],
                source_packages=[],
                target_environment=target_environment,
                resolver_backend="uv",
                error_category="unspecified_resolution_failure",
                original_diagnostics=combined.strip(),
                suggested_investigation=(
                    "Review the resolver diagnostics for contradictory constraints or "
                    "unsupported flags."
                ),
            )
        )
        return conflicts

    @staticmethod
    def analyze_pip_error(
        stderr: str,
        stdout: str = "",
        target_environment: str | None = None,
    ) -> list[ResolutionConflict]:
        """Extract structured conflict details from pip install dry-run failures."""
        combined = f"{stderr}\n{stdout}"
        conflicts: list[ResolutionConflict] = []

        # Check for pip conflict message:
        conflict_match = re.search(
            r"ERROR:\s*Cannot install\s+(.*?)\s+because\s+(.*)",
            combined,
            re.IGNORECASE,
        )
        if conflict_match:
            packages = conflict_match.group(1).strip()
            reason = conflict_match.group(2).strip()
            first_pkg = re.split(r"[\s,]+", packages)[0] if packages else "unknown"

            conflicts.append(
                ResolutionConflict(
                    package_name=first_pkg,
                    conflicting_requirements=[packages, reason],
                    source_packages=[],
                    target_environment=target_environment,
                    resolver_backend="pip",
                    error_category="version_conflict",
                    original_diagnostics=combined.strip(),
                    suggested_investigation=f"Pip detected version conflict between: {packages}.",
                )
            )
            return conflicts

        # Check for no matching distribution:
        no_match = re.search(
            r"ERROR:\s*No matching distribution found for\s+([^\n\r]+)",
            combined,
            re.IGNORECASE,
        )
        if no_match:
            req_str = no_match.group(1).strip()
            pkg_name = re.split(r"[><=~;]", req_str)[0].strip()

            conflicts.append(
                ResolutionConflict(
                    package_name=pkg_name,
                    conflicting_requirements=[req_str],
                    source_packages=[],
                    target_environment=target_environment,
                    resolver_backend="pip",
                    error_category="no_matching_release",
                    original_diagnostics=combined.strip(),
                    suggested_investigation=(
                        f"Pip found no matching distribution for '{req_str}'. "
                        "Target platform tags or Python version may be incompatible."
                    ),
                )
            )
            return conflicts

        # Generic fallback
        conflicts.append(
            ResolutionConflict(
                package_name="pip_resolution",
                conflicting_requirements=[combined[:300].strip()],
                source_packages=[],
                target_environment=target_environment,
                resolver_backend="pip",
                error_category="pip_failure",
                original_diagnostics=combined.strip(),
                suggested_investigation="Review pip dry-run diagnostics for constraint issues.",
            )
        )
        return conflicts
