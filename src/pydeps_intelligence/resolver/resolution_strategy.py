"""Mapping of resolution strategies to resolver backend flags and options."""

from __future__ import annotations

from pydeps_intelligence.models.dependencies import ResolutionStrategy


class StrategyMapper:
    """Translates high-level PyDeps resolution strategies into concrete backend options."""

    @staticmethod
    def get_uv_flags(
        strategy: ResolutionStrategy,
        allow_prereleases: bool = False,
        upgrade: bool = False,
        upgrade_packages: list[str] | None = None,
    ) -> list[str]:
        """Compute CLI arguments for uv resolution commands."""
        flags: list[str] = []

        # Resolution preference
        if strategy == ResolutionStrategy.LATEST_COMPATIBLE:
            flags.extend(["--resolution", "highest"])
        elif strategy == ResolutionStrategy.FEWEST_VERSIONS:
            flags.extend(["--resolution", "lowest-direct"])
        elif strategy == ResolutionStrategy.PREFER_EXISTING_CONSTRAINTS:
            flags.extend(["--resolution", "highest"])

        # Prerelease policy
        if allow_prereleases:
            flags.extend(["--prerelease", "allow"])
        else:
            flags.extend(["--prerelease", "disallow"])

        # Upgrade options
        if upgrade:
            flags.append("--upgrade")
        elif upgrade_packages:
            for pkg in upgrade_packages:
                flags.extend(["--upgrade-package", pkg])

        return flags

    @staticmethod
    def get_pip_flags(
        strategy: ResolutionStrategy,
        allow_prereleases: bool = False,
        upgrade: bool = False,
    ) -> list[str]:
        """Compute CLI arguments for pip install --dry-run commands."""
        flags: list[str] = []

        if allow_prereleases:
            flags.append("--pre")

        if upgrade:
            flags.extend(["--upgrade", "--upgrade-strategy", "eager"])
        else:
            flags.extend(["--upgrade-strategy", "only-if-needed"])

        return flags
