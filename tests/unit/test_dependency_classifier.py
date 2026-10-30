"""Unit tests for DependencyClassifier."""

from __future__ import annotations

from pathlib import Path

from pydeps.models.analysis import ImportAnalysisResult
from pydeps.models.dependencies import DependencyType
from pydeps.models.imports import ImportContext, ImportRecord, ImportType, MappingSource
from pydeps.models.mapping import ConfidenceLevel, PackageMappingResult, PackageReport
from pydeps.models.structure import ProjectStructure
from pydeps.resolver.dependency_classifier import DependencyClassifier


def _make_analysis(all_imports: list[ImportRecord] | None = None) -> ImportAnalysisResult:
    return ImportAnalysisResult(
        structure=ProjectStructure(root_path=Path(".")),
        all_imports=all_imports or [],
    )


def test_classifier_runtime_and_dev_separation() -> None:
    """Test that imports in test files or test contexts are classified as DEV."""
    classifier = DependencyClassifier()

    rec_runtime = ImportRecord(
        module_name="requests.get",
        import_type=ImportType.THIRD_PARTY,
        source_file=Path("src/app/main.py"),
        line_number=1,
        import_context=ImportContext.TOP_LEVEL,
    )
    rec_dev = ImportRecord(
        module_name="pytest.fixture",
        import_type=ImportType.THIRD_PARTY,
        source_file=Path("tests/test_main.py"),
        line_number=2,
        import_context=ImportContext.TOP_LEVEL,
    )

    analysis = _make_analysis([rec_runtime, rec_dev])

    mapping_requests = PackageMappingResult(
        import_name="requests",
        selected_distribution="requests",
        candidate_distributions=["requests"],
        confidence=ConfidenceLevel.HIGH,
        mapping_source=MappingSource.KNOWN_MAPPING,
    )
    mapping_pytest = PackageMappingResult(
        import_name="pytest",
        selected_distribution="pytest",
        candidate_distributions=["pytest"],
        confidence=ConfidenceLevel.HIGH,
        mapping_source=MappingSource.KNOWN_MAPPING,
    )

    report = PackageReport(
        analysis=analysis,
        mappings=[mapping_requests, mapping_pytest],
    )

    res = classifier.classify(report, analysis=analysis)
    runtime_names = [d.name for d in res["runtime"]]
    dev_names = [d.name for d in res["dev"]]

    assert "requests" in runtime_names
    assert "pytest" in dev_names
    assert "pytest" not in runtime_names


def test_classifier_type_checking_imports() -> None:
    """Test that imports appearing only inside TYPE_CHECKING blocks are separated."""
    classifier = DependencyClassifier()

    rec_typing = ImportRecord(
        module_name="pandas.DataFrame",
        import_type=ImportType.THIRD_PARTY,
        source_file=Path("src/app/types.py"),
        line_number=5,
        import_context=ImportContext.TYPE_CHECKING,
    )

    analysis = _make_analysis([rec_typing])
    report = PackageReport(
        analysis=analysis,
        mappings=[
            PackageMappingResult(
                import_name="pandas",
                selected_distribution="pandas",
                candidate_distributions=["pandas"],
                confidence=ConfidenceLevel.HIGH,
                mapping_source=MappingSource.KNOWN_MAPPING,
            )
        ],
    )

    res = classifier.classify(report, analysis=analysis)
    assert len(res["type_checking"]) == 1
    assert res["type_checking"][0].name == "pandas"
    assert res["type_checking"][0].dependency_type == DependencyType.TYPE_CHECKING
    assert len(res["runtime"]) == 0


def test_classifier_optional_guarded_imports() -> None:
    """Test that imports occurring only inside try/except blocks are classified as OPTIONAL."""
    classifier = DependencyClassifier()

    rec_opt = ImportRecord(
        module_name="uvloop",
        import_type=ImportType.THIRD_PARTY,
        source_file=Path("src/app/server.py"),
        line_number=10,
        import_context=ImportContext.TRY_EXCEPT,
    )

    analysis = _make_analysis([rec_opt])
    report = PackageReport(
        analysis=analysis,
        mappings=[
            PackageMappingResult(
                import_name="uvloop",
                selected_distribution="uvloop",
                candidate_distributions=["uvloop"],
                confidence=ConfidenceLevel.HIGH,
                mapping_source=MappingSource.KNOWN_MAPPING,
            )
        ],
    )

    res = classifier.classify(report, analysis=analysis)
    assert len(res["optional"]) == 1
    assert res["optional"][0].name == "uvloop"
    assert res["optional"][0].dependency_type == DependencyType.OPTIONAL


def test_classifier_notebook_imports() -> None:
    """Test that imports from Jupyter notebooks are classified into the notebook group."""
    classifier = DependencyClassifier()

    rec_nb = ImportRecord(
        module_name="matplotlib.pyplot",
        import_type=ImportType.THIRD_PARTY,
        source_file=Path("notebooks/exploratory.ipynb"),
        line_number=1,
        import_context=ImportContext.TOP_LEVEL,
    )

    analysis = _make_analysis([rec_nb])
    report = PackageReport(
        analysis=analysis,
        mappings=[
            PackageMappingResult(
                import_name="matplotlib",
                selected_distribution="matplotlib",
                candidate_distributions=["matplotlib"],
                confidence=ConfidenceLevel.HIGH,
                mapping_source=MappingSource.KNOWN_MAPPING,
            )
        ],
    )

    res = classifier.classify(report, analysis=analysis)
    assert len(res["notebook"]) == 1
    assert res["notebook"][0].name == "matplotlib"
    assert res["notebook"][0].dependency_type == DependencyType.NOTEBOOK


def test_classifier_ambiguous_and_unresolved_safety() -> None:
    """Test that ambiguous and unresolved imports are not auto-selected and produce diagnostics."""
    classifier = DependencyClassifier()

    amb_mapping = PackageMappingResult(
        import_name="cv2",
        selected_distribution=None,
        candidate_distributions=["opencv-python", "opencv-python-headless"],
        confidence=ConfidenceLevel.LOW,
        is_ambiguous=True,
    )

    analysis = _make_analysis()
    report = PackageReport(
        analysis=analysis,
        mappings=[amb_mapping],
        ambiguous_imports=[amb_mapping],
        unresolved_imports=["some_dynamic_module"],
    )

    res = classifier.classify(report)
    assert len(res["runtime"]) == 0
    assert len(res["ambiguous"]) == 1
    assert len(res["unresolved"]) == 1
    assert any("ambiguously" in d.message for d in res["diagnostics"])
    assert any("some_dynamic_module" in d.message for d in res["diagnostics"])


def test_classifier_user_classification_override() -> None:
    """Test that user overrides can reassign dependencies to specific groups."""
    classifier = DependencyClassifier(overrides={"pytest": DependencyType.DIRECT})

    rec_dev = ImportRecord(
        module_name="pytest",
        import_type=ImportType.THIRD_PARTY,
        source_file=Path("tests/test_x.py"),
        line_number=1,
        import_context=ImportContext.TOP_LEVEL,
    )
    analysis = _make_analysis([rec_dev])

    report = PackageReport(
        analysis=analysis,
        mappings=[
            PackageMappingResult(
                import_name="pytest",
                selected_distribution="pytest",
                candidate_distributions=["pytest"],
                confidence=ConfidenceLevel.HIGH,
                mapping_source=MappingSource.KNOWN_MAPPING,
            )
        ],
    )

    res = classifier.classify(report, analysis=analysis)
    assert len(res["runtime"]) == 1
    assert res["runtime"][0].name == "pytest"
    assert res["runtime"][0].dependency_type == DependencyType.DIRECT
