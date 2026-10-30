"""AST Visitor for static discovery and extraction of Python import statements."""

from __future__ import annotations

import ast
from pathlib import Path

from pydeps.models.imports import ImportContext, ImportRecord, ImportType


class ASTImportVisitor(ast.NodeVisitor):
    """Walks an AST to collect import statements and their syntactic contexts."""

    def __init__(self, source_file: Path) -> None:
        self.source_file = source_file
        self.imports: list[ImportRecord] = []
        self.diagnostics: list[str] = []

        # Context trackers
        self._scope_stack: list[str] = ["top_level"]
        self._type_checking_depth = 0
        self._try_except_depth = 0
        self._conditional_depth = 0

    @property
    def current_context(self) -> ImportContext:
        """Derive the current syntactic import context."""
        if self._type_checking_depth > 0:
            return ImportContext.TYPE_CHECKING
        if self._try_except_depth > 0:
            return ImportContext.TRY_EXCEPT
        if self._conditional_depth > 0:
            return ImportContext.CONDITIONAL
        scope = self._scope_stack[-1]
        if scope == "function":
            return ImportContext.FUNCTION
        if scope == "class":
            return ImportContext.CLASS
        return ImportContext.TOP_LEVEL

    @property
    def current_import_type(self) -> ImportType:
        """Derive the import type based on the context."""
        if self._type_checking_depth > 0:
            return ImportType.TYPE_CHECKING
        if self._try_except_depth > 0 or self._conditional_depth > 0:
            return ImportType.CONDITIONAL
        return ImportType.UNKNOWN

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._scope_stack.append("function")
        self.generic_visit(node)
        self._scope_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._scope_stack.append("function")
        self.generic_visit(node)
        self._scope_stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._scope_stack.append("class")
        self.generic_visit(node)
        self._scope_stack.pop()

    def _is_type_checking_test(self, test_node: ast.AST) -> bool:
        """Check if an `if` condition tests TYPE_CHECKING."""
        if isinstance(test_node, ast.Name) and test_node.id == "TYPE_CHECKING":
            return True
        if isinstance(test_node, ast.Attribute) and test_node.attr == "TYPE_CHECKING":
            if isinstance(test_node.value, ast.Name) and test_node.value.id in (
                "typing",
                "typing_extensions",
            ):
                return True
        return False

    def visit_If(self, node: ast.If) -> None:
        is_type_checking = self._is_type_checking_test(node.test)
        if is_type_checking:
            self._type_checking_depth += 1
        else:
            self._conditional_depth += 1

        for item in node.body:
            self.visit(item)

        if is_type_checking:
            self._type_checking_depth -= 1
        else:
            self._conditional_depth -= 1

        # Visit else branch
        if node.orelse:
            self._conditional_depth += 1
            for item in node.orelse:
                self.visit(item)
            self._conditional_depth -= 1

    def visit_Try(self, node: ast.Try) -> None:
        # Check if any exception handler targets ImportError or ModuleNotFoundError
        catches_import_error = False
        for handler in node.handlers:
            if handler.type is None:
                catches_import_error = True
            elif isinstance(handler.type, ast.Name) and handler.type.id in (
                "ImportError",
                "ModuleNotFoundError",
                "Exception",
                "BaseException",
            ):
                catches_import_error = True
            elif isinstance(handler.type, ast.Tuple):
                for elt in handler.type.elts:
                    if isinstance(elt, ast.Name) and elt.id in (
                        "ImportError",
                        "ModuleNotFoundError",
                        "Exception",
                        "BaseException",
                    ):
                        catches_import_error = True

        if catches_import_error:
            self._try_except_depth += 1

        for item in node.body:
            self.visit(item)

        for handler in node.handlers:
            for item in handler.body:
                self.visit(item)

        if catches_import_error:
            self._try_except_depth -= 1

        for item in node.orelse:
            self.visit(item)
        for item in node.finalbody:
            self.visit(item)

    def visit_Import(self, node: ast.Import) -> None:
        ctx = self.current_context
        itype = self.current_import_type

        for alias in node.names:
            mod_name = alias.name.strip()
            if not mod_name:
                continue
            clean = mod_name.lstrip(".")
            top_level = clean.split(".")[0] if clean else mod_name

            record = ImportRecord(
                module_name=mod_name,
                source_file=self.source_file,
                line_number=node.lineno,
                import_type=itype,
                confidence=1.0,
                top_level_package=top_level,
                import_context=ctx,
                is_dynamic=False,
            )
            self.imports.append(record)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        ctx = self.current_context
        itype = self.current_import_type

        # Relative import handling
        if node.level and node.level > 0:
            prefix = "." * node.level
            if node.module:
                base_mod = f"{prefix}{node.module}"
                clean = node.module.lstrip(".")
                top_level = clean.split(".")[0] if clean else node.module
                self.imports.append(
                    ImportRecord(
                        module_name=base_mod,
                        source_file=self.source_file,
                        line_number=node.lineno,
                        import_type=ImportType.FIRST_PARTY,
                        confidence=1.0,
                        top_level_package=top_level,
                        import_context=ctx,
                        is_dynamic=False,
                    )
                )
            else:
                for alias in node.names:
                    if alias.name == "*":
                        mod_name = prefix
                        top_level = ""
                    else:
                        mod_name = f"{prefix}{alias.name}"
                        top_level = alias.name
                    self.imports.append(
                        ImportRecord(
                            module_name=mod_name,
                            source_file=self.source_file,
                            line_number=node.lineno,
                            import_type=ImportType.FIRST_PARTY,
                            confidence=1.0,
                            top_level_package=top_level,
                            import_context=ctx,
                            is_dynamic=False,
                        )
                    )
            return

        # Absolute from ... import ...
        if not node.module:
            return

        base_mod = node.module.strip()
        top_level = base_mod.split(".")[0]

        record = ImportRecord(
            module_name=base_mod,
            source_file=self.source_file,
            line_number=node.lineno,
            import_type=itype,
            confidence=1.0,
            top_level_package=top_level,
            import_context=ctx,
            is_dynamic=False,
        )
        self.imports.append(record)

    def visit_Call(self, node: ast.Call) -> None:
        ctx = self.current_context
        itype = self.current_import_type

        # Check __import__("pkg")
        is_dunder_import = isinstance(node.func, ast.Name) and node.func.id == "__import__"

        # Check importlib.import_module("pkg")
        is_importlib = (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "import_module"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "importlib"
        )

        if is_dunder_import or is_importlib:
            func_name = "__import__" if is_dunder_import else "importlib.import_module"

            if node.args:
                first_arg = node.args[0]
                if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                    mod_name = first_arg.value.strip()
                    if mod_name:
                        clean = mod_name.lstrip(".")
                        top_level = clean.split(".")[0] if clean else mod_name
                        self.imports.append(
                            ImportRecord(
                                module_name=mod_name,
                                source_file=self.source_file,
                                line_number=node.lineno,
                                import_type=itype,
                                confidence=0.85,
                                top_level_package=top_level,
                                import_context=ctx,
                                is_dynamic=True,
                                diagnostic=f"Literal dynamic import via {func_name}('{mod_name}')",
                            )
                        )
                        self.generic_visit(node)
                        return

            # Non-literal or unresolvable dynamic import
            diag = (
                f"Non-literal dynamic import via {func_name}() at "
                f"{self.source_file}:{node.lineno}; cannot be statically resolved."
            )
            self.diagnostics.append(diag)
            self.imports.append(
                ImportRecord(
                    module_name="<dynamic>",
                    source_file=self.source_file,
                    line_number=node.lineno,
                    import_type=ImportType.UNKNOWN,
                    confidence=0.0,
                    top_level_package=None,
                    import_context=ctx,
                    is_dynamic=True,
                    diagnostic=diag,
                )
            )

        self.generic_visit(node)
