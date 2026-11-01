"""Unit tests for ImportAggregator."""

from __future__ import annotations

from pathlib import Path

from pydeps_intelligence.aggregator import ImportAggregator
from pydeps_intelligence.classifier import StdlibCatalog
from pydeps_intelligence.models.imports import ImportContext, ImportRecord, ImportType
from pydeps_intelligence.models.structure import ProjectStructure


def test_aggregator_categorization() -> None:
    """Test categorization across stdlib, local, external, dynamic, optional, and typing imports."""
    root = Path("/test/project")
    structure = ProjectStructure(
        root_path=root,
        source_files=[root / "local_mod.py"],
        notebook_files=[],
        source_roots=[root],
        metadata_files=[],
        local_modules=["local_mod"],
        diagnostics=[],
    )

    records = [
        # Stdlib
        ImportRecord(
            module_name="os",
            source_file=root / "main.py",
            line_number=1,
            import_type=ImportType.UNKNOWN,
            confidence=1.0,
        ),
        # Local
        ImportRecord(
            module_name="local_mod",
            source_file=root / "main.py",
            line_number=2,
            import_type=ImportType.UNKNOWN,
            confidence=1.0,
        ),
        # External candidate
        ImportRecord(
            module_name="requests",
            source_file=root / "main.py",
            line_number=3,
            import_type=ImportType.UNKNOWN,
            confidence=1.0,
        ),
        # TYPE_CHECKING
        ImportRecord(
            module_name="pydantic",
            source_file=root / "main.py",
            line_number=4,
            import_type=ImportType.TYPE_CHECKING,
            import_context=ImportContext.TYPE_CHECKING,
            confidence=1.0,
        ),
        # Optional (try/except)
        ImportRecord(
            module_name="ujson",
            source_file=root / "main.py",
            line_number=5,
            import_type=ImportType.CONDITIONAL,
            import_context=ImportContext.TRY_EXCEPT,
            confidence=1.0,
        ),
        # Dynamic literal
        ImportRecord(
            module_name="yaml",
            source_file=root / "main.py",
            line_number=6,
            import_type=ImportType.UNKNOWN,
            is_dynamic=True,
            confidence=0.85,
        ),
        # Non-literal dynamic unresolved
        ImportRecord(
            module_name="<dynamic>",
            source_file=root / "main.py",
            line_number=7,
            import_type=ImportType.UNKNOWN,
            is_dynamic=True,
            confidence=0.0,
        ),
    ]

    aggregator = ImportAggregator(stdlib_catalog=StdlibCatalog())
    result = aggregator.aggregate(
        structure,
        raw_imports=records,
        target_python_version="3.11",
    )

    assert len(result.standard_library_imports) == 1
    assert result.standard_library_imports[0].module_name == "os"

    assert len(result.local_imports) == 1
    assert result.local_imports[0].module_name == "local_mod"

    ext_pkgs = result.unique_external_packages
    assert "requests" in ext_pkgs
    assert "pydantic" in ext_pkgs
    assert "ujson" in ext_pkgs
    assert "yaml" in ext_pkgs

    assert len(result.type_checking_imports) == 1
    assert result.type_checking_imports[0].module_name == "pydantic"

    assert len(result.optional_imports) == 1
    assert result.optional_imports[0].module_name == "ujson"

    assert len(result.dynamic_imports) == 2
    assert len(result.unresolved_imports) == 1
    assert result.unresolved_imports[0].module_name == "<dynamic>"


def test_aggregator_deduplication() -> None:
    """Test deduplication of identical import records at the same file and line."""
    root = Path("/test/project")
    structure = ProjectStructure(
        root_path=root,
        source_files=[],
        notebook_files=[],
        source_roots=[root],
        metadata_files=[],
        local_modules=[],
        diagnostics=[],
    )

    dup1 = ImportRecord(
        module_name="sys",
        source_file=root / "app.py",
        line_number=1,
    )
    dup2 = ImportRecord(
        module_name="sys",
        source_file=root / "app.py",
        line_number=1,
    )

    aggregator = ImportAggregator()
    result = aggregator.aggregate(structure, raw_imports=[dup1, dup2])
    assert len(result.all_imports) == 1


def test_aggregator_to_analysis_report() -> None:
    """Test converting ImportAnalysisResult into an AnalysisReport."""
    root = Path("/my/app")
    structure = ProjectStructure(
        root_path=root,
        source_files=[root / "app.py"],
        notebook_files=[],
        source_roots=[root],
        metadata_files=[],
        local_modules=["app"],
        diagnostics=["Warning 1"],
    )

    rec = ImportRecord(
        module_name="click",
        source_file=root / "app.py",
        line_number=1,
    )

    aggregator = ImportAggregator()
    result = aggregator.aggregate(structure, raw_imports=[rec])
    report = result.to_analysis_report()

    assert report.project_information.project_name == "app"
    assert len(report.discovered_imports) == 1
    assert report.warnings == ["Warning 1"]
