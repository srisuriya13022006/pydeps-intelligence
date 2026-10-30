"""Unit tests for AST import analyzer and visitor."""

from __future__ import annotations

from pathlib import Path

from pydeps.analyzer import ImportAnalyzer
from pydeps.models.imports import ImportContext, ImportType


def test_standard_and_from_imports() -> None:
    """Test standard and from imports."""
    code = """
import os
import sys as system
from pathlib import Path
from math import sqrt, pi
"""
    analyzer = ImportAnalyzer()
    imports, diags = analyzer.analyze_source(code, source_file="sample.py")

    assert len(diags) == 0
    mod_names = [imp.module_name for imp in imports]
    assert "os" in mod_names
    assert "sys" in mod_names
    assert "pathlib" in mod_names
    assert "math" in mod_names

    for imp in imports:
        assert imp.import_context == ImportContext.TOP_LEVEL
        assert imp.is_dynamic is False


def test_relative_imports() -> None:
    """Test relative imports with levels."""
    code = """
from . import sibling
from .child import item
from ..parent import base
"""
    analyzer = ImportAnalyzer()
    imports, diags = analyzer.analyze_source(code, source_file="pkg/mod.py")

    assert len(diags) == 0
    mod_names = [imp.module_name for imp in imports]
    assert ".sibling" in mod_names
    assert ".child" in mod_names
    assert "..parent" in mod_names

    for imp in imports:
        assert imp.import_type == ImportType.FIRST_PARTY


def test_nested_imports_in_function_and_class() -> None:
    """Test imports located inside functions, async functions, and class definitions."""
    code = """
class MyClass:
    import json

    def my_method(self):
        import csv

    async def my_async_method(self):
        import sqlite3
"""
    analyzer = ImportAnalyzer()
    imports, diags = analyzer.analyze_source(code, source_file="nested.py")
    assert len(diags) == 0

    by_mod = {imp.module_name: imp for imp in imports}
    assert by_mod["json"].import_context == ImportContext.CLASS
    assert by_mod["csv"].import_context == ImportContext.FUNCTION
    assert by_mod["sqlite3"].import_context == ImportContext.FUNCTION


def test_conditional_imports() -> None:
    """Test conditional imports inside if-else blocks."""
    code = """
import sys

if sys.platform == "win32":
    import winreg
else:
    import posix
"""
    analyzer = ImportAnalyzer()
    imports, diags = analyzer.analyze_source(code, source_file="cond.py")
    assert len(diags) == 0

    by_mod = {imp.module_name: imp for imp in imports}
    assert by_mod["sys"].import_context == ImportContext.TOP_LEVEL
    assert by_mod["winreg"].import_context == ImportContext.CONDITIONAL
    assert by_mod["posix"].import_context == ImportContext.CONDITIONAL


def test_type_checking_imports() -> None:
    """Test imports guarded by TYPE_CHECKING conditions."""
    code = """
from typing import TYPE_CHECKING
import typing

if TYPE_CHECKING:
    import heavy_type_lib
    from pandas import DataFrame

if typing.TYPE_CHECKING:
    import another_type_dep
"""
    analyzer = ImportAnalyzer()
    imports, diags = analyzer.analyze_source(code, source_file="typing_test.py")
    assert len(diags) == 0

    by_mod = {imp.module_name: imp for imp in imports}
    assert by_mod["heavy_type_lib"].import_context == ImportContext.TYPE_CHECKING
    assert by_mod["pandas"].import_context == ImportContext.TYPE_CHECKING
    assert by_mod["another_type_dep"].import_context == ImportContext.TYPE_CHECKING


def test_optional_try_except_imports() -> None:
    """Test imports inside try/except ImportError blocks."""
    code = """
try:
    import ujson as json
except ImportError:
    import json

try:
    import uvloop
except (ImportError, ModuleNotFoundError):
    pass
"""
    analyzer = ImportAnalyzer()
    imports, diags = analyzer.analyze_source(code, source_file="optional.py")
    assert len(diags) == 0

    by_mod = {imp.module_name: imp for imp in imports}
    assert by_mod["ujson"].import_context == ImportContext.TRY_EXCEPT
    assert by_mod["json"].import_context == ImportContext.TRY_EXCEPT
    assert by_mod["uvloop"].import_context == ImportContext.TRY_EXCEPT


def test_literal_and_nonliteral_dynamic_imports() -> None:
    """Test static identification of literal dynamic imports and diagnostics for nonliterals."""
    code = """
import importlib

# Literal dynamic imports
pkg1 = __import__("yaml")
pkg2 = importlib.import_module("requests.sessions")

# Non-literal dynamic imports
dynamic_name = "os"
pkg3 = __import__(dynamic_name)
pkg4 = importlib.import_module(dynamic_name)
"""
    analyzer = ImportAnalyzer()
    imports, diags = analyzer.analyze_source(code, source_file="dynamic.py")

    # Should discover yaml and requests.sessions as dynamic imports
    by_mod = {imp.module_name: imp for imp in imports if imp.module_name != "<dynamic>"}
    assert "yaml" in by_mod
    assert by_mod["yaml"].is_dynamic is True
    assert "requests.sessions" in by_mod
    assert by_mod["requests.sessions"].is_dynamic is True

    # Should contain explicit diagnostics for the nonliteral calls
    assert len(diags) == 2
    assert any("Non-literal dynamic import via __import__()" in d for d in diags)
    assert any("Non-literal dynamic import via importlib.import_module()" in d for d in diags)

    dynamic_records = [imp for imp in imports if imp.module_name == "<dynamic>"]
    assert len(dynamic_records) == 2


def test_syntax_error_resilience() -> None:
    """Test analyzer handles syntax errors gracefully without raising exceptions."""
    bad_code = "import os\ndef broken_func(: pass\nimport sys"
    analyzer = ImportAnalyzer()
    imports, diags = analyzer.analyze_source(bad_code, source_file="broken.py")

    assert len(diags) >= 1
    assert "Syntax error" in diags[0]
    # Function should return gracefully
    assert isinstance(imports, list)


def test_file_reading_and_encoding_resilience(tmp_path: Path) -> None:
    """Test reading normal files and files with non-utf8 characters."""
    valid_file = tmp_path / "normal.py"
    valid_file.write_text("import json\n", encoding="utf-8")

    analyzer = ImportAnalyzer()
    imports, diags = analyzer.analyze_file(valid_file)
    assert len(diags) == 0
    assert len(imports) == 1
    assert imports[0].module_name == "json"

    # Non-existent file
    missing_file = tmp_path / "missing.py"
    imports_missing, diags_missing = analyzer.analyze_file(missing_file)
    assert imports_missing == []
    assert len(diags_missing) == 1
