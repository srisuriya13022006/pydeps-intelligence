"""Integration tests for high-level PyDeps facade."""

from __future__ import annotations

import httpx
import pytest

from pydeps_intelligence.facade import PyDeps
from pydeps_intelligence.metadata.pypi_client import PyPIClient


@pytest.fixture
def mock_project_tree(tmp_path):
    proj_dir = tmp_path / "sample_project"
    proj_dir.mkdir()
    src_dir = proj_dir / "src"
    src_dir.mkdir()

    # Local module
    local_mod = src_dir / "helpers.py"
    local_mod.write_text("def helper(): pass\n", encoding="utf-8")

    # Main script with standard library, local, and external imports
    app_py = src_dir / "app.py"
    app_py.write_text(
        "import sys\nimport json\nimport helpers\nimport requests\nimport yaml\n",
        encoding="utf-8",
    )
    return proj_dir


def test_facade_end_to_end_flow(mock_project_tree, tmp_path) -> None:
    """Test full PyDeps workflow: analyze -> resolve_packages -> fetch_metadata."""
    queries_made: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        pkg = path.split("/")[2]
        queries_made.append(pkg)
        return httpx.Response(
            200,
            json={
                "info": {
                    "name": pkg,
                    "version": "1.0.0",
                    "requires_python": ">=3.8",
                    "requires_dist": [],
                },
                "releases": {"1.0.0": []},
                "urls": [],
            },
        )

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        pypi_client = PyPIClient(client=http_client)
        cache_dir = tmp_path / "cache"

        engine = PyDeps(project_path=mock_project_tree, cache_dir=cache_dir)
        # Inject mocked PyPI client into engine's metadata provider
        engine.metadata_provider.client = pypi_client

        # 1. Analyze
        analysis = engine.analyze()
        assert analysis.structure.total_source_files >= 2
        # Stdlib should be identified
        stdlib_names = {i.module_name for i in analysis.standard_library_imports}
        assert "sys" in stdlib_names
        assert "json" in stdlib_names

        # 2. Resolve packages
        report = engine.resolve_packages(analysis)
        resolved_dists = set(report.selected_distributions)
        assert "requests" in resolved_dists
        # yaml should be mapped to pyyaml via curated database
        assert "pyyaml" in resolved_dists

        # 3. Fetch metadata
        metadata_results = engine.fetch_metadata(report)
        assert "requests" in metadata_results
        assert "pyyaml" in metadata_results
        assert metadata_results["requests"].success is True
        assert metadata_results["pyyaml"].success is True

        # CRITICAL ASSERTION: sys, json, and helpers MUST NEVER be queried against PyPI
        assert "sys" not in queries_made
        assert "json" not in queries_made
        assert "helpers" not in queries_made
        assert set(queries_made) == {"pyyaml", "requests"}
