# PyDeps Architecture Documentation

## 1. System Overview

PyDeps is a Python Dependency Intelligence Engine designed to analyze codebases, discover package imports, map imports to distributions, verify cross-platform and multi-Python version compatibility, resolve dependencies, and validate runtime safety in isolated environments.

```
+-------------------------------------------------------------------------------+
|                             Interfaces / Consumers                            |
|        CLI (Typer)          |      Python API       |    VS Code Extension    |
+-------------------------------------------------------------------------------+
                                         |
                                         v
+-------------------------------------------------------------------------------+
|                         PyDeps Engine Core (src/pydeps)                       |
|                                                                               |
|   +-----------------------+           +-----------------------------------+   |
|   |  Project Scanner      | --------> |  AST Import Analyzer              |   |
|   |  (Recursive / .ipynb) |           |  (Syntactic / Context Extraction) |   |
|   +-----------------------+           +-----------------------------------+   |
|               |                                         |                     |
|               v                                         v                     |
|   +-----------------------+           +-----------------------------------+   |
|   | Local Module Detector | <-------> | Stdlib Catalog (Per Target Ver)   |   |
|   +-----------------------+           +-----------------------------------+   |
|               \                                         /                     |
|                \                                       /                      |
|                 v                                     v                       |
|               +-------------------------------------------+                   |
|               |  Import Aggregator                        |                   |
|               |  (Categorization & Deduplication)         |                   |
|               +-------------------------------------------+                   |
|                                     |                                         |
|                                     v                                         |
|               +-------------------------------------------+                   |
|               |  Compatibility Engine & Resolvers (P2/P3) |                   |
|               +-------------------------------------------+                   |
+-------------------------------------------------------------------------------+
```

## 2. Core Architectural Principles

1. **Modular Architecture:** Distinct components for configuration, scanning, import analysis, classification, mapping, compatibility, resolution, and validation.
2. **Strong Typing & Predictable Data Contracts:** Pydantic v2 schemas govern all inputs and outputs.
3. **Independent and Testable Components:** High cohesion and unit test coverage across all modules without external side effects in test suites.
4. **No Unnecessary Abstractions:** Straightforward abstractions that match real workflows.
5. **No Hardcoded Package Compatibility Assumptions:** Decisions are grounded in PEP 508 environment markers, distribution tags (PEP 425), and verified repository metadata.
6. **Explainable Compatibility Decisions:** Every result pairs an explicit status with detailed evidence and reasons.
7. **Network Isolation:** Any remote operations (PyPI JSON API, wheel inspection) are encapsulated behind abstract service interfaces.
8. **Host-Independent Target Environments:** Target environments describe arbitrary target systems (OS, architecture, Python version, implementation) without coupling to the host system running PyDeps.
9. **Zero Code Execution during Static Analysis:** Codebases and Jupyter notebooks are analyzed purely via static token and AST inspection. Analyzed project code or setup scripts are never imported or executed in the host environment.

## 3. Key Architecture Decisions (ADRs)

### ADR-001: uv as Primary Resolution Backend
- **Decision:** Use `uv` as the default primary dependency resolution engine.
- **Rationale:** `uv` is exceptionally fast, strictly adheres to modern packaging standards (PEP 508, PEP 517/518, PEP 621), and provides deterministic resolution across target Python versions and platforms without requiring those target Python interpreters to be pre-installed on the host.
- **Alternatives Considered:** Resolvelib (requires custom PyPI provider and SAT solver integration) and pip-tools (slower, tightly coupled to host Python).

### ADR-002: pip as Secondary Resolution Backend
- **Decision:** Support `pip` as a fallback or secondary resolution backend.
- **Rationale:** While slower than `uv`, `pip` is universally present in Python environments and provides maximum compatibility for edge cases, legacy indices, or environments where installing external binaries is restricted.

### ADR-003: Isolated Runtime Validation Strategy
- **Decision:** Runtime validation will begin with disposable local environments (e.g. lightweight isolated virtual environments).
- **Future Backends:** The validation interface is decoupled to allow seamless extension to Docker containers and remote CI runners in subsequent milestones.
- **Safety Principle:** Runtime validation will never execute untrusted project code or arbitrary setup scripts in the developer's normal environment.

### ADR-004: Standard Artifacts & Lockfile Formats
- **Decision:** Do not invent a custom lockfile format. PyDeps will export standard, established formats:
  - `requirements.txt` (PEP 508 pinned requirements with hashes and environment markers).
  - Native `uv.lock` where appropriate for reproducible multi-platform lockfiles.
- **Rationale:** Eliminates tool friction and allows users to consume PyDeps outputs directly with existing packaging and deployment pipelines.

### ADR-005: Tri-State Compatibility Model
- **Decision:** Compatibility evaluation must explicitly distinguish three states:
  - `compatible`: Positive verification that the package and version are supported on the target environment (e.g., matching wheel tags, compatible `python_requires`, passing markers).
  - `incompatible`: Definite evidence of incompatibility (e.g., unsupported Python version specifier, incompatible platform markers, known conflicting constraints).
  - `unverified`: Absence of sufficient conclusive evidence (e.g., pure sdist without declared wheels, missing metadata, or uncontactable registries).
- **Rationale:** Treating unknown status as compatible leads to broken environments, while treating unknown as incompatible creates false alarms. Explicit tri-state transparency enables confident human and automated triage.

### ADR-006: Pure Static AST Analysis (Zero Code Execution)
- **Decision:** All source analysis in the engine is performed statically using Python's `ast` parser and JSON cell extraction for Jupyter notebooks.
- **Rationale:** Analyzing untrusted repositories must never execute top-level statements, side-effects, dynamic code, or setup scripts.
- **Dynamic Imports:** Statically resolvable literal dynamic imports (`__import__("pkg")`, `importlib.import_module("pkg")`) are recorded with lower confidence, while non-literal dynamic invocations produce diagnostic warnings rather than attempting dynamic evaluation.

### ADR-007: Target-Version Decoupled Standard Library Catalogs
- **Decision:** Standard-library classification is driven by a standalone `StdlibCatalog` parameterized by the target Python version (`target_python_version`), rather than relying exclusively on the running interpreter's `sys.stdlib_module_names`.
- **Rationale:** A developer running PyDeps on Python 3.11 analyzing a legacy Python 3.8 or future Python 3.13 project must see standard library determinations accurate for that specific target runtime (e.g. `distutils` removed in 3.12, `tomllib` added in 3.11, `zoneinfo` added in 3.9). When a version cannot be conclusively verified, the module is classified as `unverified` with diagnostics rather than guessed.

### ADR-008: Multi-Provider Evidence-Based Distribution Mapping
- **Decision:** Import-to-distribution resolution uses a prioritized multi-provider chain (`OverrideMappingProvider` -> `DatabaseMappingProvider` -> `InstalledEnvironmentMappingProvider` -> `DirectHeuristicMappingProvider`).
- **Rationale:** Import names rarely map 1:1 to distribution package names (e.g. `cv2` -> `opencv-python`, `PIL` -> `Pillow`, `yaml` -> `PyYAML`). Local environment inspection (`importlib.metadata.packages_distributions()`) is advisory evidence rather than definitive ground truth because the target project may not be installed in the environment executing PyDeps.
- **Ambiguity Rule:** When an import maps to multiple distinct distributions (e.g. `cv2`, `crypto`), `PackageMappingResult` reports `is_ambiguous=True` with `selected_distribution=None` and requires explicit user override; it never silently guesses.

### ADR-009: PyPI Metadata Ingestion and Offline-First Two-Tier Caching
- **Decision:** PyPI metadata retrieval is mediated by `MetadataProvider` combining an in-memory cache and a persistent JSON cache (`pydeps_metadata_v1.json`) with configurable TTL and strict offline mode.
- **Safety Principles:**
  - Standard library and local project modules are never queried against PyPI.
  - Package names are strictly validated against `^[A-Za-z0-9][A-Za-z0-9._-]*[A-Za-z0-9]$` to prevent URL path injection.
  - PyPI client employs bounded exponential backoff retries (maximum 3 attempts) for HTTP 429 and transient 5xx errors; it never retries indefinitely.
  - Dependency metadata (`Requires-Dist`) is parsed into PEP 508 `packaging.requirements.Requirement` representations without premature local environment marker evaluation.

## 4. Component Layout

```
PyDeps/
├── src/
│   └── pydeps/
│       ├── __init__.py           # Package version and top-level public API exports
│       ├── _version.py           # Single source of truth for version string
│       ├── facade.py             # High-level PyDeps orchestrator class
│       ├── py.typed              # PEP 561 typing marker
│       ├── config.py             # Project configuration loader & validator
│       ├── exceptions.py         # PyDeps domain exception hierarchy
│       ├── models/
│       │   ├── __init__.py       # Unified model namespace exports
│       │   ├── project.py        # ProjectConfig, TargetEnvironment, and core enums
│       │   ├── structure.py      # ProjectStructure model for scan results
│       │   ├── imports.py        # ImportRecord, PackageMapping, ImportContext
│       │   ├── mapping.py        # PackageMappingResult, ConfidenceLevel, PackageReport
│       │   ├── analysis.py       # ImportAnalysisResult aggregate findings
│       │   ├── dependencies.py   # Dependency, ResolutionResult
│       │   ├── compatibility.py  # CompatibilityResult, CompatibilityStatus
│       │   ├── validation.py     # ValidationResult, ValidationStatus
│       │   └── report.py         # AnalysisReport aggregate model
│       ├── scanner/
│       │   ├── __init__.py
│       │   └── scanner.py        # Recursive ProjectScanner and notebook extractor
│       ├── analyzer/
│       │   ├── __init__.py
│       │   ├── ast_visitor.py    # ASTImportVisitor for syntactic import contexts
│       │   └── analyzer.py       # ImportAnalyzer engine
│       ├── classifier/
│       │   ├── __init__.py
│       │   ├── stdlib.py         # Target-version aware StdlibCatalog
│       │   └── local.py          # LocalModuleDetector (src-layout & relative imports)
│       ├── aggregator/
│       │   ├── __init__.py
│       │   └── aggregator.py     # ImportAggregator for categorized results
│       ├── registry/
│       │   ├── __init__.py       # Registry exports
│       │   ├── package_mapper.py # PackageMapper orchestrating mapping providers
│       │   ├── mapping_database.py # Bundled curated import-to-distribution table
│       │   ├── mapping_provider.py # Base and specialized mapping evidence providers
│       │   ├── mapping_overrides.py# User-configured mapping overrides manager
│       │   └── mapping_cache.py  # In-memory and disk cache for mapped distributions
│       ├── metadata/
│       │   ├── __init__.py       # Metadata exports
│       │   ├── metadata_models.py# ReleaseArtifact, PackageRelease, MetadataResult
│       │   ├── metadata_parser.py# PEP 508 requires_dist and wheel artifact parser
│       │   ├── metadata_cache.py # Two-tier in-memory & persistent disk cache with TTL
│       │   ├── pypi_client.py    # HTTPX client with retries, backoff, and validation
│       │   ├── metadata_provider.py # High-level metadata service coordinating client and cache
│       │   └── release_metadata.py# Release files and wheel platform tags helper
│       └── cli/
│           ├── __init__.py
│           └── main.py           # Typer CLI application (scan, analyze, map, metadata)
├── tests/
│   ├── unit/
│   │   ├── test_config.py        # Config parsing, validation, and defaults
│   │   ├── test_models.py        # Model serialization, enums, constraints
│   │   ├── test_scanner.py       # ProjectScanner discovery and exclusion tests
│   │   ├── test_analyzer.py      # AST analysis, contexts, and dynamic imports
│   │   ├── test_classifier.py    # StdlibCatalog version deltas and local module detection
│   │   ├── test_aggregator.py    # Aggregator categorization and deduplication
│   │   ├── test_mapping.py       # Import-to-distribution mappings, ambiguity, overrides
│   │   ├── test_metadata_cache.py# Cache eviction, TTL, disk persistence, offline mode
│   │   └── test_metadata_parser.py# PEP 508 Requires-Dist parsing, artifacts, wheel tags
│   └── integration/
│       ├── test_cli.py           # CLI invocation (scan, analyze, map, metadata, errors)
│       ├── test_facade.py        # High-level PyDeps facade end-to-end flow
│       ├── test_metadata_provider.py # MetadataProvider mocked PyPI integration & caching
│       ├── test_pipeline.py      # End-to-end multi-package pipeline execution
│       └── test_pypi_client.py   # PyPIClient HTTP status, rate limit, and retry handling
├── docs/
│   └── architecture.md           # This architecture documentation
├── pyproject.toml                # Project metadata, dependencies, tool configs
├── README.md                     # Overview, quickstart, and development guide
└── .gitignore                    # Standard Python/IDE exclusions
```
