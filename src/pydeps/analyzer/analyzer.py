"""High-level Python source and project import analyzer."""

from __future__ import annotations

import ast
from pathlib import Path

from pydeps.aggregator.aggregator import ImportAggregator
from pydeps.analyzer.ast_visitor import ASTImportVisitor
from pydeps.classifier.stdlib import StdlibCatalog
from pydeps.models.analysis import ImportAnalysisResult
from pydeps.models.imports import ImportRecord
from pydeps.models.structure import ProjectStructure
from pydeps.scanner.scanner import ProjectScanner


class ImportAnalyzer:
    """Performs static AST import analysis on individual source files or entire projects."""

    def __init__(
        self,
        aggregator: ImportAggregator | None = None,
        stdlib_catalog: StdlibCatalog | None = None,
    ) -> None:
        self.stdlib_catalog = stdlib_catalog or StdlibCatalog()
        self.aggregator = aggregator or ImportAggregator(stdlib_catalog=self.stdlib_catalog)

    def analyze_source(
        self,
        source_code: str,
        source_file: Path | str = "<string>",
    ) -> tuple[list[ImportRecord], list[str]]:
        """Parse Python source code statically and extract all import statements."""
        path = Path(source_file)
        visitor = ASTImportVisitor(path)
        diagnostics: list[str] = []

        try:
            tree = ast.parse(source_code, filename=str(path))
            visitor.visit(tree)
        except SyntaxError as exc:
            msg = f"Syntax error parsing {path}:{exc.lineno or 1}: {exc.msg}"
            diagnostics.append(msg)
        except Exception as exc:
            msg = f"Unexpected error parsing AST for {path}: {exc}"
            diagnostics.append(msg)

        diagnostics.extend(visitor.diagnostics)
        return visitor.imports, diagnostics

    def analyze_file(self, file_path: Path | str) -> tuple[list[ImportRecord], list[str]]:
        """Read a source file (.py or .ipynb) and perform static import extraction."""
        path = Path(file_path)
        if not path.is_file():
            return [], [f"File not found: {path}"]

        if path.suffix.lower() == ".ipynb":
            code = ProjectScanner.extract_notebook_code(path)
            return self.analyze_source(code, source_file=path)

        # Standard .py file
        try:
            with path.open("r", encoding="utf-8") as f:
                code = f.read()
        except UnicodeDecodeError:
            try:
                with path.open("r", encoding="utf-8", errors="replace") as f:
                    code = f.read()
                return self.analyze_source(code, source_file=path)
            except Exception as exc:
                return [], [f"Failed to read file {path}: {exc}"]
        except Exception as exc:
            return [], [f"Failed to read file {path}: {exc}"]

        return self.analyze_source(code, source_file=path)

    def analyze_project(
        self,
        structure: ProjectStructure,
        target_python_version: str = "3.11",
    ) -> ImportAnalysisResult:
        """Analyze all discovered source and notebook files across a project structure."""
        all_imports: list[ImportRecord] = []
        all_diagnostics: list[str] = []

        # Analyze .py files
        for sf in structure.source_files:
            file_imports, diags = self.analyze_file(sf)
            all_imports.extend(file_imports)
            all_diagnostics.extend(diags)

        # Analyze .ipynb notebook files
        for nb in structure.notebook_files:
            nb_imports, diags = self.analyze_file(nb)
            all_imports.extend(nb_imports)
            all_diagnostics.extend(diags)

        return self.aggregator.aggregate(
            structure=structure,
            raw_imports=all_imports,
            target_python_version=target_python_version,
            diagnostics=all_diagnostics,
        )
