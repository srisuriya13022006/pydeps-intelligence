"""High-level Package Mapping Engine resolving import statements to PyPI distributions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from packaging.utils import canonicalize_name

from pydeps.models.analysis import ImportAnalysisResult
from pydeps.models.imports import MappingSource
from pydeps.models.mapping import ConfidenceLevel, PackageMappingResult, PackageReport
from pydeps.registry.mapping_cache import MappingCache
from pydeps.registry.mapping_database import MappingDatabase
from pydeps.registry.mapping_overrides import MappingOverrides
from pydeps.registry.mapping_provider import (
    DatabaseMappingProvider,
    DirectHeuristicMappingProvider,
    InstalledEnvironmentMappingProvider,
    MappingProvider,
    OverrideMappingProvider,
)


class PackageMapper:
    """Resolves Python module import names to PyPI distribution package names."""

    def __init__(
        self,
        overrides: MappingOverrides | Mapping[str, str | list[str]] | None = None,
        database: MappingDatabase | None = None,
        cache: MappingCache | None = None,
        use_installed_env: bool = True,
    ) -> None:
        self.cache = cache or MappingCache()
        self.overrides = (
            overrides if isinstance(overrides, MappingOverrides) else MappingOverrides(overrides)
        )
        self.database = database or MappingDatabase()

        # Build prioritized providers list
        self.providers: list[MappingProvider] = [
            OverrideMappingProvider(self.overrides),
            DatabaseMappingProvider(self.database),
        ]
        if use_installed_env:
            self.providers.append(InstalledEnvironmentMappingProvider())
        self.providers.append(DirectHeuristicMappingProvider())

    def map_import(self, import_name: str) -> PackageMappingResult:
        """Resolve a single import name into its candidate distribution packages and confidence."""
        clean_import = import_name.strip()
        top_level = clean_import.lstrip(".").split(".")[0]

        if not top_level or top_level == "<dynamic>":
            return PackageMappingResult(
                import_name=clean_import,
                candidate_distributions=[],
                selected_distribution=None,
                mapping_source=MappingSource.HEURISTIC,
                confidence=ConfidenceLevel.UNRESOLVED,
                confidence_score=0.0,
                is_ambiguous=False,
                explanation="Dynamic or invalid import cannot be mapped statically.",
                evidence=[],
                diagnostic=f"Cannot map unresolvable import '{clean_import}'.",
            )

        # Check cache
        cached = self.cache.get(clean_import) or self.cache.get(top_level)
        if cached is not None:
            return cached

        # Try providers in order
        all_evidence: list[str] = []

        for provider in self.providers:
            candidates = provider.resolve_candidates(clean_import)
            if not candidates and clean_import != top_level:
                candidates = provider.resolve_candidates(top_level)
            if not candidates:
                continue

            normalized_candidates = [canonicalize_name(c) for c in candidates]
            # Deduplicate preserving order
            unique_candidates: list[str] = []
            for c in normalized_candidates:
                if c not in unique_candidates:
                    unique_candidates.append(c)

            source = provider.source
            evidence_desc = f"{source.value}: {', '.join(unique_candidates)}"
            all_evidence.append(evidence_desc)

            # If provider is user override: highest confidence
            if source == MappingSource.OVERRIDE:
                is_ambiguous = len(unique_candidates) > 1
                selected = unique_candidates[0] if not is_ambiguous else None
                conf = ConfidenceLevel.HIGH
                conf_score = 1.0 if not is_ambiguous else 0.8
                explanation = (
                    f"User override resolved '{clean_import}' to "
                    f"{unique_candidates[0] if selected else unique_candidates}."
                )
                diag = (
                    f"User override for '{clean_import}' specifies multiple candidates: "
                    f"{unique_candidates}"
                    if is_ambiguous
                    else None
                )
                result = PackageMappingResult(
                    import_name=clean_import,
                    candidate_distributions=unique_candidates,
                    selected_distribution=selected,
                    mapping_source=source,
                    confidence=conf,
                    confidence_score=conf_score,
                    is_ambiguous=is_ambiguous,
                    explanation=explanation,
                    evidence=all_evidence,
                    diagnostic=diag,
                )
                self.cache.set(clean_import, result)
                return result

            # If provider is curated database: high confidence
            if source == MappingSource.KNOWN_MAPPING:
                is_ambiguous = len(unique_candidates) > 1
                selected = unique_candidates[0] if not is_ambiguous else None
                conf = ConfidenceLevel.HIGH if not is_ambiguous else ConfidenceLevel.MEDIUM
                conf_score = 0.95 if not is_ambiguous else 0.65
                if is_ambiguous:
                    explanation = (
                        f"Curated database maps '{clean_import}' to multiple distributions: "
                        f"{', '.join(unique_candidates)}. Requires explicit selection."
                    )
                    diag = (
                        f"Ambiguous import mapping for '{clean_import}': "
                        f"candidates={unique_candidates}"
                    )
                else:
                    explanation = f"Curated database mapped '{clean_import}' to '{selected}'."
                    diag = None

                result = PackageMappingResult(
                    import_name=clean_import,
                    candidate_distributions=unique_candidates,
                    selected_distribution=selected,
                    mapping_source=source,
                    confidence=conf,
                    confidence_score=conf_score,
                    is_ambiguous=is_ambiguous,
                    explanation=explanation,
                    evidence=all_evidence,
                    diagnostic=diag,
                )
                self.cache.set(clean_import, result)
                return result

            # If provider is installed environment metadata: medium confidence
            if source == MappingSource.METADATA:
                is_ambiguous = len(unique_candidates) > 1
                selected = unique_candidates[0] if not is_ambiguous else None
                conf = ConfidenceLevel.MEDIUM
                conf_score = 0.7 if not is_ambiguous else 0.5
                explanation = (
                    f"Local environment metadata maps '{clean_import}' to {unique_candidates}."
                )
                diag = (
                    f"Ambiguous local environment mapping for '{clean_import}'."
                    if is_ambiguous
                    else None
                )
                result = PackageMappingResult(
                    import_name=clean_import,
                    candidate_distributions=unique_candidates,
                    selected_distribution=selected,
                    mapping_source=source,
                    confidence=conf,
                    confidence_score=conf_score,
                    is_ambiguous=is_ambiguous,
                    explanation=explanation,
                    evidence=all_evidence,
                    diagnostic=diag,
                )
                self.cache.set(clean_import, result)
                return result

            # Direct fallback heuristic: low confidence
            if source == MappingSource.HEURISTIC:
                selected = unique_candidates[0]
                expl = (
                    f"Direct heuristic assumed distribution name matches import name '{selected}'."
                )
                result = PackageMappingResult(
                    import_name=clean_import,
                    candidate_distributions=unique_candidates,
                    selected_distribution=selected,
                    mapping_source=source,
                    confidence=ConfidenceLevel.LOW,
                    confidence_score=0.4,
                    is_ambiguous=False,
                    explanation=expl,
                    evidence=all_evidence,
                    diagnostic=None,
                )
                self.cache.set(clean_import, result)
                return result

        # If completely unresolvable
        return PackageMappingResult(
            import_name=clean_import,
            candidate_distributions=[],
            selected_distribution=None,
            mapping_source=MappingSource.HEURISTIC,
            confidence=ConfidenceLevel.UNRESOLVED,
            confidence_score=0.0,
            is_ambiguous=False,
            explanation=f"No distribution found for import '{clean_import}'.",
            evidence=all_evidence,
            diagnostic=f"Unresolved distribution for import '{clean_import}'.",
        )

    def map_imports(self, import_names: Sequence[str]) -> list[PackageMappingResult]:
        """Map a collection of import names deterministically."""
        seen: set[str] = set()
        results: list[PackageMappingResult] = []

        for name in sorted(import_names):
            clean = name.strip()
            top = clean.lstrip(".").split(".")[0]
            if not top or top in seen:
                continue
            seen.add(top)
            results.append(self.map_import(top))

        return results

    def map_analysis(self, analysis: ImportAnalysisResult) -> PackageReport:
        """Enrich discovered external candidate imports from an ImportAnalysisResult."""
        candidate_names = analysis.unique_external_packages
        mapping_results = self.map_imports(list(candidate_names))

        unresolved: list[str] = []
        ambiguous: list[PackageMappingResult] = []
        diagnostics: list[str] = list(analysis.diagnostics)

        for res in mapping_results:
            if res.confidence == ConfidenceLevel.UNRESOLVED or not res.candidate_distributions:
                unresolved.append(res.import_name)
            if res.is_ambiguous:
                ambiguous.append(res)
                if res.diagnostic:
                    diagnostics.append(res.diagnostic)

        return PackageReport(
            analysis=analysis,
            mappings=mapping_results,
            unresolved_imports=sorted(unresolved),
            ambiguous_imports=ambiguous,
            diagnostics=diagnostics,
        )
