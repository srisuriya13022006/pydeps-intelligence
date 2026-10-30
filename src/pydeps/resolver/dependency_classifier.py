"""Classification of project imports and mappings into typed dependency groups."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from packaging.utils import canonicalize_name

from pydeps.models.analysis import ImportAnalysisResult
from pydeps.models.dependencies import Dependency, DependencyType, ResolutionDiagnostic
from pydeps.models.imports import ImportContext
from pydeps.models.mapping import ConfidenceLevel, PackageReport


class DependencyClassifier:
    """Classifies discovered project imports into structured dependency categories.

    Applies safety rules:
    - High-confidence unambiguous mappings become automatic candidates.
    - Medium-confidence mappings are marked and recorded.
    - Low-confidence mappings require explicit opt-in policy.
    - Ambiguous imports are never silently selected.
    - Test-only, type-checking, notebook, and guarded imports are separated from runtime.
    """

    def __init__(
        self,
        include_medium_confidence: bool = True,
        include_low_confidence: bool = False,
        overrides: dict[str, str | DependencyType] | None = None,
    ) -> None:
        self.include_medium_confidence = include_medium_confidence
        self.include_low_confidence = include_low_confidence
        self.overrides = overrides or {}

    def is_test_path(self, path: Path | str) -> bool:
        """Determine whether a source path represents a test or dev file."""
        p_str = str(path).replace("\\", "/").lower()
        parts = p_str.split("/")
        filename = parts[-1] if parts else ""

        # Check directories
        test_dir_names = ("tests", "test", "testing", "tests_unit", "tests_integration")
        if any(seg in test_dir_names for seg in parts[:-1]):
            return True

        # Check file prefixes/suffixes
        if filename.startswith("test_") or filename.endswith("_test.py"):
            return True
        if filename.startswith("conftest.py"):
            return True

        return False

    def is_notebook_path(self, path: Path | str) -> bool:
        """Determine whether a source path represents a Jupyter notebook."""
        return str(path).lower().endswith(".ipynb")

    def classify(
        self,
        package_report: PackageReport,
        analysis: ImportAnalysisResult | None = None,
        constraints: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Classify mapped imports into runtime, dev, type_checking, optional, and notebook."""
        constraints = constraints or {}
        runtime_deps: dict[str, Dependency] = {}
        dev_deps: dict[str, Dependency] = {}
        type_checking_deps: dict[str, Dependency] = {}
        optional_deps: dict[str, Dependency] = {}
        notebook_deps: dict[str, Dependency] = {}
        diagnostics: list[ResolutionDiagnostic] = []

        # Index import contexts by import name if analysis is available
        import_contexts: dict[str, set[ImportContext]] = {}
        import_paths: dict[str, set[Path]] = {}

        if analysis:
            for rec in analysis.all_imports:
                pkg_key = rec.top_level_package or rec.module_name.split(".")[0]
                if hasattr(rec, "import_context") and rec.import_context:
                    import_contexts.setdefault(pkg_key, set()).add(rec.import_context)
                elif hasattr(rec, "contexts") and getattr(rec, "contexts", None):
                    contexts_val = getattr(rec, "contexts", None)
                    if contexts_val:
                        import_contexts.setdefault(pkg_key, set()).update(contexts_val)
                import_paths.setdefault(pkg_key, set()).add(rec.source_file)

        # 1. Process ambiguous mappings
        for amb in package_report.ambiguous_imports:
            candidates = ", ".join(amb.candidate_distributions)
            msg = (
                f"Import '{amb.import_name}' maps ambiguously to multiple distributions "
                f"({candidates}). It was not automatically selected and requires manual override."
            )
            diagnostics.append(
                ResolutionDiagnostic(
                    message=msg,
                    level="warning",
                    package_name=amb.import_name,
                    source="classifier",
                )
            )

        # 2. Process unresolved imports
        for unres in package_report.unresolved_imports:
            msg = f"Import '{unres}' could not be resolved to any known package distribution."
            diagnostics.append(
                ResolutionDiagnostic(
                    message=msg,
                    level="warning",
                    package_name=unres,
                    source="classifier",
                )
            )

        # 3. Process resolved mappings
        for mapping in package_report.mappings:
            if mapping.is_ambiguous or not mapping.selected_distribution:
                continue

            dist_name = canonicalize_name(mapping.selected_distribution)
            conf = mapping.confidence

            # Confidence safety filters
            if conf == ConfidenceLevel.LOW and not self.include_low_confidence:
                diagnostics.append(
                    ResolutionDiagnostic(
                        message=(
                            f"Mapped distribution '{dist_name}' for import '{mapping.import_name}' "
                            f"has LOW confidence and was excluded by policy."
                        ),
                        level="info",
                        package_name=dist_name,
                        source="classifier",
                    )
                )
                continue

            if conf == ConfidenceLevel.MEDIUM and not self.include_medium_confidence:
                diagnostics.append(
                    ResolutionDiagnostic(
                        message=(
                            f"Mapped distribution '{dist_name}' for import '{mapping.import_name}' "
                            f"has MEDIUM confidence and was excluded by policy."
                        ),
                        level="info",
                        package_name=dist_name,
                        source="classifier",
                    )
                )
                continue

            # Determine primary context and source paths
            raw_import = mapping.import_name
            contexts = import_contexts.get(raw_import, set())
            paths = import_paths.get(raw_import, set())

            # Check user override
            explicit_type: DependencyType | None = None
            if dist_name in self.overrides:
                override_val = self.overrides[dist_name]
                if isinstance(override_val, DependencyType):
                    explicit_type = override_val
                elif isinstance(override_val, str):
                    try:
                        explicit_type = DependencyType(override_val)
                    except ValueError:
                        pass

            version_spec = constraints.get(dist_name)

            # Classify dependency type based on paths and contexts
            all_in_tests = bool(paths) and all(self.is_test_path(p) for p in paths)
            all_in_notebooks = bool(paths) and all(self.is_notebook_path(p) for p in paths)
            only_type_checking = bool(contexts) and contexts == {ImportContext.TYPE_CHECKING}
            only_guarded = bool(contexts) and contexts.issubset(
                {ImportContext.TRY_EXCEPT, ImportContext.CONDITIONAL}
            )

            if explicit_type is not None:
                dep_type = explicit_type
            elif all_in_tests:
                dep_type = DependencyType.DEV
            elif all_in_notebooks:
                dep_type = DependencyType.NOTEBOOK
            elif only_type_checking:
                dep_type = DependencyType.TYPE_CHECKING
            elif only_guarded:
                dep_type = DependencyType.OPTIONAL
            else:
                dep_type = DependencyType.DIRECT

            dep = Dependency(
                name=dist_name,
                version_specifier=version_spec,
                dependency_type=dep_type,
            )

            # Route to appropriate bucket
            if dep_type == DependencyType.DEV:
                dev_deps[dist_name] = dep
            elif dep_type == DependencyType.NOTEBOOK:
                notebook_deps[dist_name] = dep
            elif dep_type == DependencyType.TYPE_CHECKING:
                type_checking_deps[dist_name] = dep
            elif dep_type == DependencyType.OPTIONAL:
                optional_deps[dist_name] = dep
            else:
                runtime_deps[dist_name] = dep

        return {
            "runtime": list(runtime_deps.values()),
            "dev": list(dev_deps.values()),
            "type_checking": list(type_checking_deps.values()),
            "optional": list(optional_deps.values()),
            "notebook": list(notebook_deps.values()),
            "ambiguous": package_report.ambiguous_imports,
            "unresolved": package_report.unresolved_imports,
            "diagnostics": diagnostics,
        }
