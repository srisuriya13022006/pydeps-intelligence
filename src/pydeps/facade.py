"""High-level unified API facade for PyDeps."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from pydeps.analyzer.analyzer import ImportAnalyzer
from pydeps.config import resolve_project_config
from pydeps.metadata.metadata_cache import MetadataCache
from pydeps.metadata.metadata_models import MetadataResult
from pydeps.metadata.metadata_provider import MetadataProvider
from pydeps.models.analysis import ImportAnalysisResult
from pydeps.models.mapping import PackageReport
from pydeps.models.project import ProjectConfig
from pydeps.models.structure import ProjectStructure
from pydeps.registry.package_mapper import PackageMapper
from pydeps.scanner.scanner import ProjectScanner


class PyDeps:
    """Unified engine coordinator for scanning, import analysis, package mapping, and metadata."""

    def __init__(
        self,
        project_path: Path | str = ".",
        config: ProjectConfig | None = None,
        offline: bool = False,
        cache_dir: Path | str | None = None,
        overrides: Mapping[str, str | list[str]] | None = None,
    ) -> None:
        self.project_path = Path(project_path)
        self.config = config or resolve_project_config(self.project_path)
        self.offline = offline

        self.cache_dir = (
            Path(cache_dir)
            if cache_dir
            else self.project_path / self.config.output_directory / "cache"
        )
        self.metadata_cache = MetadataCache(cache_dir=self.cache_dir, offline=offline)
        self.scanner = ProjectScanner(config=self.config)
        self.analyzer = ImportAnalyzer()
        self.mapper = PackageMapper(overrides=overrides)
        self.metadata_provider = MetadataProvider(cache=self.metadata_cache, offline=offline)

    def scan(self) -> ProjectStructure:
        """Scan project directory and discover source files, notebooks, and metadata."""
        return self.scanner.scan(self.project_path)

    def analyze(self, python_version: str = "3.11") -> ImportAnalysisResult:
        """Scan the project and perform static AST import extraction and classification."""
        structure = self.scan()
        return self.analyzer.analyze_project(structure, target_python_version=python_version)

    def resolve_packages(
        self,
        analysis: ImportAnalysisResult | None = None,
        overrides: Mapping[str, str | list[str]] | None = None,
    ) -> PackageReport:
        """Map discovered external candidate imports to PyPI distribution names."""
        if analysis is None:
            analysis = self.analyze()

        mapper = self.mapper
        if overrides:
            mapper = PackageMapper(overrides=overrides)

        return mapper.map_analysis(analysis)

    def fetch_metadata(
        self,
        package_report: PackageReport | None = None,
        offline: bool | None = None,
    ) -> dict[str, MetadataResult]:
        """Retrieve PyPI release metadata for resolved distribution packages.

        Never queries PyPI for standard library or local project packages.
        """
        if package_report is None:
            package_report = self.resolve_packages()

        is_offline = self.offline if offline is None else offline

        # Only query distributions resolved from external imports
        target_dists = package_report.selected_distributions
        return self.metadata_provider.get_batch_metadata(target_dists, offline=is_offline)
