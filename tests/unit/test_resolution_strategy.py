"""Unit tests for StrategyMapper and resolution strategy CLI flag translation."""

from __future__ import annotations

from pydeps_intelligence.models.dependencies import ResolutionStrategy
from pydeps_intelligence.resolver.resolution_strategy import StrategyMapper


def test_strategy_mapper_uv_latest_compatible() -> None:
    """Test CLI flags for uv latest-compatible strategy."""
    flags = StrategyMapper.get_uv_flags(
        strategy=ResolutionStrategy.LATEST_COMPATIBLE,
        allow_prereleases=False,
    )
    assert "--resolution" in flags
    assert "highest" in flags
    assert "--prerelease" in flags
    assert "disallow" in flags


def test_strategy_mapper_uv_fewest_versions() -> None:
    """Test CLI flags for uv fewest-versions strategy."""
    flags = StrategyMapper.get_uv_flags(
        strategy=ResolutionStrategy.FEWEST_VERSIONS,
        allow_prereleases=True,
    )
    assert "--resolution" in flags
    assert "lowest-direct" in flags
    assert "--prerelease" in flags
    assert "allow" in flags


def test_strategy_mapper_uv_upgrade_options() -> None:
    """Test upgrade flags for uv."""
    flags_all = StrategyMapper.get_uv_flags(
        strategy=ResolutionStrategy.LATEST_COMPATIBLE,
        upgrade=True,
    )
    assert "--upgrade" in flags_all

    flags_pkg = StrategyMapper.get_uv_flags(
        strategy=ResolutionStrategy.LATEST_COMPATIBLE,
        upgrade=False,
        upgrade_packages=["requests", "urllib3"],
    )
    assert "--upgrade-package" in flags_pkg
    assert "requests" in flags_pkg
    assert "urllib3" in flags_pkg


def test_strategy_mapper_pip_flags() -> None:
    """Test CLI flags for pip strategy mapping."""
    flags_std = StrategyMapper.get_pip_flags(
        strategy=ResolutionStrategy.LATEST_COMPATIBLE,
        allow_prereleases=False,
        upgrade=False,
    )
    assert "--upgrade-strategy" in flags_std
    assert "only-if-needed" in flags_std
    assert "--pre" not in flags_std

    flags_pre = StrategyMapper.get_pip_flags(
        strategy=ResolutionStrategy.LATEST_COMPATIBLE,
        allow_prereleases=True,
        upgrade=True,
    )
    assert "--pre" in flags_pre
    assert "--upgrade" in flags_pre
    assert "eager" in flags_pre
