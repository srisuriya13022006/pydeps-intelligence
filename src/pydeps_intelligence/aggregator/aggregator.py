"""Aggregation and categorization of extracted import statements."""

from __future__ import annotations

from collections.abc import Sequence

from pydeps_intelligence.classifier.local import LocalModuleDetector
from pydeps_intelligence.classifier.stdlib import StdlibCatalog
from pydeps_intelligence.models.analysis import ImportAnalysisResult
from pydeps_intelligence.models.imports import ImportContext, ImportRecord, ImportType
from pydeps_intelligence.models.structure import ProjectStructure


class ImportAggregator:
    """Aggregates, deduplicates, and categorizes import records using catalogs and detectors."""

    def __init__(
        self,
        stdlib_catalog: StdlibCatalog | None = None,
    ) -> None:
        self.stdlib_catalog = stdlib_catalog or StdlibCatalog()

    def aggregate(
        self,
        structure: ProjectStructure,
        raw_imports: Sequence[ImportRecord],
        target_python_version: str = "3.11",
        diagnostics: Sequence[str] | None = None,
    ) -> ImportAnalysisResult:
        """Categorize raw import statements and assemble the ImportAnalysisResult."""
        detector = LocalModuleDetector(structure)
        all_diags: list[str] = list(structure.diagnostics)
        if diagnostics:
            all_diags.extend(diagnostics)

        stdlib_imports: list[ImportRecord] = []
        local_imports: list[ImportRecord] = []
        external_imports: list[ImportRecord] = []
        dynamic_imports: list[ImportRecord] = []
        unresolved_imports: list[ImportRecord] = []
        type_checking_imports: list[ImportRecord] = []
        optional_imports: list[ImportRecord] = []

        seen_keys: set[tuple[str, str, int]] = set()
        deduped_all: list[ImportRecord] = []

        for record in raw_imports:
            key = (record.module_name, str(record.source_file), record.line_number)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped_all.append(record)

            # Categorize based on context
            if record.import_context == ImportContext.TYPE_CHECKING:
                type_checking_imports.append(record)
            if record.import_context in (ImportContext.TRY_EXCEPT, ImportContext.CONDITIONAL):
                optional_imports.append(record)
            if record.is_dynamic:
                dynamic_imports.append(record)

            if record.module_name == "<dynamic>":
                unresolved_imports.append(record)
                continue

            # Classify origin: Local vs Stdlib vs Third-party vs Unresolved
            if detector.is_local_module(record.module_name, record.source_file):
                # Classify as local (first party)
                updated = record.model_copy(update={"import_type": ImportType.FIRST_PARTY})
                local_imports.append(updated)
            else:
                stdlib_status = self.stdlib_catalog.is_stdlib(
                    record.module_name,
                    target_python_version,
                )
                if stdlib_status is True:
                    updated = record.model_copy(update={"import_type": ImportType.STANDARD_LIBRARY})
                    stdlib_imports.append(updated)
                elif stdlib_status is False:
                    updated = record.model_copy(update={"import_type": ImportType.THIRD_PARTY})
                    external_imports.append(updated)
                else:
                    # Unverified status for target Python version
                    diag_msg = (
                        f"Unverified standard library classification for '{record.module_name}' "
                        f"on target Python {target_python_version}."
                    )
                    all_diags.append(diag_msg)
                    updated = record.model_copy(
                        update={"diagnostic": diag_msg, "import_type": ImportType.UNKNOWN}
                    )
                    unresolved_imports.append(updated)

        return ImportAnalysisResult(
            structure=structure,
            target_python_version=target_python_version,
            standard_library_imports=stdlib_imports,
            local_imports=local_imports,
            external_candidate_imports=external_imports,
            dynamic_imports=dynamic_imports,
            unresolved_imports=unresolved_imports,
            type_checking_imports=type_checking_imports,
            optional_imports=optional_imports,
            all_imports=deduped_all,
            diagnostics=all_diags,
        )
