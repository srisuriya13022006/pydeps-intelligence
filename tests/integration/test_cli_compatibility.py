"""Integration tests for 'pydeps compatibility' CLI command."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from pydeps_intelligence.cli.main import app
from pydeps_intelligence.metadata.metadata_cache import MetadataCache
from pydeps_intelligence.metadata.metadata_models import PackageRelease, ReleaseArtifact

runner = CliRunner()


def test_cli_compatibility_non_existent_path(tmp_path: Path) -> None:
    """Test 'pydeps compatibility' on a non-existent path exits with code 1."""
    bad_path = tmp_path / "missing_dir"
    result = runner.invoke(app, ["compatibility", str(bad_path)])
    assert result.exit_code == 1
    assert "does not exist" in result.stderr or "does not exist" in result.stdout


def test_cli_compatibility_offline_cached_run(tmp_path: Path) -> None:
    """Test 'pydeps compatibility' in offline mode with pre-cached metadata."""
    # 1. Create a dummy project importing requests
    proj_dir = tmp_path / "test_project"
    proj_dir.mkdir()
    (proj_dir / "app.py").write_text("import requests\n", encoding="utf-8")

    # 2. Prepopulate metadata cache in the project's .pydeps/cache directory
    cache_dir = proj_dir / ".pydeps" / "cache"
    cache = MetadataCache(cache_dir=cache_dir)
    rel = PackageRelease(
        distribution_name="requests",
        version="2.31.0",
        requires_python=">=3.7",
        release_files=[
            ReleaseArtifact(
                filename="requests-2.31.0-py3-none-any.whl",
                package_type="bdist_wheel",
            )
        ],
    )
    cache.set("requests", rel)

    # 3. Invoke compatibility CLI with explicit targets in offline mode
    result = runner.invoke(
        app,
        [
            "compatibility",
            str(proj_dir),
            "--python",
            "3.10,3.11",
            "--os",
            "linux,windows",
            "--arch",
            "x86_64",
            "--offline",
        ],
    )
    assert result.exit_code == 0
    assert "PyDeps Compatibility Matrix" in result.stdout
    assert "Packages Evaluated:   1" in result.stdout
    assert "Targets Evaluated:    4" in result.stdout
    assert "Compatible:         4" in result.stdout
    assert "requests" in result.stdout


def test_cli_compatibility_json_output(tmp_path: Path) -> None:
    """Test 'pydeps compatibility --json' outputs valid structured CompatibilityMatrix JSON."""
    proj_dir = tmp_path / "proj"
    proj_dir.mkdir()
    (proj_dir / "main.py").write_text("import requests\n", encoding="utf-8")

    # Cache metadata
    cache_dir = proj_dir / ".pydeps" / "cache"
    cache = MetadataCache(cache_dir=cache_dir)
    rel = PackageRelease(
        distribution_name="requests",
        version="2.31.0",
        requires_python=">=3.7",
        release_files=[
            ReleaseArtifact(
                filename="requests-2.31.0-py3-none-any.whl",
                package_type="bdist_wheel",
            )
        ],
    )
    cache.set("requests", rel)

    result = runner.invoke(
        app,
        [
            "compatibility",
            str(proj_dir),
            "--python",
            "3.11",
            "--os",
            "linux",
            "--arch",
            "x86_64",
            "--offline",
            "--json",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "packages" in data
    assert "targets" in data
    assert "matrix" in data
    assert "requests" in data["packages"]
    assert len(data["targets"]) == 1


def test_cli_compatibility_impossible_target_warning(tmp_path: Path) -> None:
    """Test that impossible target combinations (e.g. macOS 32-bit x86) are skipped and reported."""
    proj_dir = tmp_path / "proj"
    proj_dir.mkdir()
    (proj_dir / "main.py").write_text("import requests\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "compatibility",
            str(proj_dir),
            "--python",
            "3.11",
            "--os",
            "macos",
            "--arch",
            "x86",  # 32-bit macOS is invalid
            "--offline",
        ],
    )
    # Since only impossible target was passed, CLI reports error
    assert result.exit_code == 1
    assert (
        "No valid target environments specified" in result.stderr
        or "No valid target environments" in result.stdout
    )
