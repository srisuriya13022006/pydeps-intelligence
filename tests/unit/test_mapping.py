"""Unit tests for package mapping engine and databases."""

from __future__ import annotations

from pathlib import Path

from pydeps_intelligence.models.analysis import ImportAnalysisResult
from pydeps_intelligence.models.imports import ImportRecord, ImportType, MappingSource
from pydeps_intelligence.models.mapping import ConfidenceLevel
from pydeps_intelligence.models.structure import ProjectStructure
from pydeps_intelligence.registry.mapping_overrides import MappingOverrides
from pydeps_intelligence.registry.package_mapper import PackageMapper


def test_known_curated_mappings() -> None:
    """Test resolution of standard 1-to-1 curated mappings."""
    mapper = PackageMapper()

    # sklearn -> scikit-learn
    res_sklearn = mapper.map_import("sklearn")
    assert res_sklearn.selected_distribution == "scikit-learn"
    assert res_sklearn.confidence == ConfidenceLevel.HIGH
    assert res_sklearn.is_ambiguous is False
    assert res_sklearn.mapping_source == MappingSource.KNOWN_MAPPING

    # PIL -> pillow
    res_pil = mapper.map_import("PIL")
    assert res_pil.selected_distribution == "pillow"
    assert res_pil.confidence == ConfidenceLevel.HIGH

    # yaml -> pyyaml
    res_yaml = mapper.map_import("yaml")
    assert res_yaml.selected_distribution == "pyyaml"

    # dotenv -> python-dotenv
    res_dotenv = mapper.map_import("dotenv")
    assert res_dotenv.selected_distribution == "python-dotenv"

    # bs4 -> beautifulsoup4
    res_bs4 = mapper.map_import("bs4")
    assert res_bs4.selected_distribution == "beautifulsoup4"


def test_ambiguous_mappings() -> None:
    """Test detection of ambiguous imports providing multiple distributions."""
    mapper = PackageMapper()

    # cv2 can be opencv-python, opencv-contrib-python, etc.
    res_cv2 = mapper.map_import("cv2")
    assert res_cv2.is_ambiguous is True
    assert res_cv2.selected_distribution is None
    assert "opencv-python" in res_cv2.candidate_distributions
    assert "opencv-python-headless" in res_cv2.candidate_distributions
    assert res_cv2.diagnostic is not None

    # crypto can be pycryptodome or pycrypto
    res_crypto = mapper.map_import("Crypto")
    assert res_crypto.is_ambiguous is True
    assert res_crypto.selected_distribution is None
    assert "pycryptodome" in res_crypto.candidate_distributions
    assert "pycrypto" in res_crypto.candidate_distributions


def test_user_mapping_overrides() -> None:
    """Test that explicit user overrides take highest priority and disambiguate."""
    overrides = MappingOverrides(
        {
            "cv2": "opencv-python-headless",
            "custom_internal": "internal-package-dist",
        }
    )
    mapper = PackageMapper(overrides=overrides)

    res_cv2 = mapper.map_import("cv2")
    assert res_cv2.selected_distribution == "opencv-python-headless"
    assert res_cv2.is_ambiguous is False
    assert res_cv2.confidence == ConfidenceLevel.HIGH
    assert res_cv2.mapping_source == MappingSource.OVERRIDE

    res_custom = mapper.map_import("custom_internal")
    assert res_custom.selected_distribution == "internal-package-dist"
    assert res_custom.mapping_source == MappingSource.OVERRIDE


def test_direct_heuristic_fallback() -> None:
    """Test fallback heuristic for packages whose distribution matches the module name."""
    mapper = PackageMapper()
    res = mapper.map_import("some_uncommon_pkg")
    assert res.selected_distribution == "some-uncommon-pkg"
    assert res.confidence == ConfidenceLevel.LOW
    assert res.mapping_source == MappingSource.HEURISTIC
    assert res.is_ambiguous is False


def test_unresolved_dynamic_imports() -> None:
    """Test that dynamic unresolvable imports return UNRESOLVED confidence."""
    mapper = PackageMapper()
    res = mapper.map_import("<dynamic>")
    assert res.confidence == ConfidenceLevel.UNRESOLVED
    assert res.selected_distribution is None
    assert res.candidate_distributions == []


def test_name_normalization() -> None:
    """Test distribution name normalization adheres to PEP 503."""
    mapper = PackageMapper(overrides={"Foo_Bar.Baz": "My_Package.Distribution-Core"})
    res = mapper.map_import("Foo_Bar.Baz")
    assert res.selected_distribution == "my-package-distribution-core"


def test_map_analysis_integration(tmp_path: Path) -> None:
    """Test PackageMapper.map_analysis integrating with ImportAnalysisResult."""
    structure = ProjectStructure(
        root_path=tmp_path,
        source_files=[],
        notebook_files=[],
        source_roots=[tmp_path],
        metadata_files=[],
        local_modules=["local_pkg"],
        diagnostics=[],
    )

    analysis = ImportAnalysisResult(
        structure=structure,
        target_python_version="3.11",
        external_candidate_imports=[
            ImportRecord(
                module_name="yaml",
                source_file=tmp_path / "app.py",
                line_number=1,
                import_type=ImportType.THIRD_PARTY,
                top_level_package="yaml",
            ),
            ImportRecord(
                module_name="cv2",
                source_file=tmp_path / "app.py",
                line_number=2,
                import_type=ImportType.THIRD_PARTY,
                top_level_package="cv2",
            ),
        ],
    )

    mapper = PackageMapper()
    report = mapper.map_analysis(analysis)

    assert "pyyaml" in report.selected_distributions
    # cv2 is ambiguous so not in selected_distributions
    assert "opencv-python" not in report.selected_distributions
    assert len(report.ambiguous_imports) == 1
    assert report.ambiguous_imports[0].import_name == "cv2"
