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

### ADR-010: Target Environment Modeling
- **Decision:** Explicit target environments are modeled via `TargetEnvironment` and `TargetPlatformProfile`, completely decoupled from the host runtime running PyDeps.
- **Dimensions Supported:** Python version (e.g. 3.9 through 3.14), operating system (Windows, Linux, macOS), CPU architecture (x86_64, ARM64, etc.), Python implementation (CPython, PyPy), ABI tags, Linux manylinux/musllinux policies, macOS deployment targets, and Windows platform tags.
- **Host Isolation Rule:** Never silently substitute the host machine's platform configuration for requested target environments. If insufficient information is provided by a profile to evaluate a platform-sensitive condition, report `unverified` rather than guessing or defaulting to host properties.

### ADR-011: Packaging Standards-Based Compatibility
- **Decision:** Drive all version constraints, marker evaluations, and wheel compatibility checks directly through canonical `packaging` primitives (`packaging.version.Version`, `packaging.specifiers.SpecifierSet`, `packaging.tags`, `packaging.markers.Marker`, `packaging.utils.parse_wheel_filename`).
- **Wheel Tag Derivation:** Never invoke `packaging.tags.sys_tags()` to evaluate foreign target platforms, as `sys_tags()` exclusively describes the host interpreter. Instead, generate target-compatible wheel tags using explicit target platform profiles parameterized by OS, CPU architecture, implementation, and target Python version.
- **Marker Evaluation Isolation:** Construct PEP 508 marker evaluation environments exclusively from the target platform profile. Marker variables not supplied by the target configuration are identified via AST inspection and reported as `unverified` rather than allowing fallback to the host's `default_environment()`.

### ADR-012: Static Compatibility Versus Runtime Verification
- **Decision:** Maintain a strict, unambiguous distinction between static compatibility and runtime buildability.
- **Prebuilt Wheel vs. Source Distribution:**
  - A release with a compatible prebuilt wheel (or pure-Python wheel) matching target tags and Python constraints is evaluated as `compatible`.
  - A release providing only source distributions (`sdist`) cannot be statically guaranteed to build or install, as source builds may require native compilers, C/Fortran/Rust toolchains, system libraries, or dynamic build-backend hooks. Therefore, sdist-only candidates evaluate to `unverified` with explicit diagnostic evidence indicating that runtime validation is required.
  - A release with conflicting Python constraints or incompatible wheels without sdists evaluates to `incompatible`.
- **Evidence Semantics:** Every evaluation yields auditable evidence including evaluated Python specifiers, candidate wheel tags, rejected wheel reasons, and marker evaluations. Missing metadata (such as an absent `Requires-Python` header) evaluates to `unverified` rather than being assumed compatible.

### ADR-013: Resolver Backend Abstraction
- **Decision:** Implement a dual-backend resolver architecture with `uv` as the high-performance primary resolver and standard `pip` (`pip install --dry-run --report`) as a limited fallback backend.
- **No Custom Backtracking:** Avoid maintaining a proprietary backtracking dependency solver. Instead, leverage modern standard-compliant package resolvers via subprocess execution.
- **Backend Limitations:**
  - `uv` provides universal project resolution (`uv lock`), multi-platform environment marker forks, native `uv.lock` generation, and pinned `requirements.txt` exports (`uv export`).
  - `pip` provides single-target or host-target dry-run resolution reporting. `pip` cannot generate a universal multi-environment lockfile (`uv.lock`) and cannot reliably resolve for foreign architectures without explicit foreign platform flags (`--python-version`, `--platform`, `--implementation`, `--abi`). Universal resolution requests to the pip backend are rejected with structured diagnostics.

### ADR-014: Universal Versus Per-Target Resolution
- **Decision:** Support two independent, clearly distinguished resolution modes:
  1. **Universal Resolution:** Resolves project dependencies into a complete, multi-environment lockfile (`uv.lock`) and pinned `requirements.txt` satisfying configured Python ranges and marker environments. Universal resolution resolves marker forks; it does not claim or prove that prebuilt native binary wheels exist on all platforms.
  2. **Per-Target Resolution:** Resolves dependencies independently for each discrete target profile (e.g., `windows-cp311-x86_64`, `linux-cp312-x86_64`), producing separate pinned requirement sets and dependency graphs for each target.

### ADR-015: Dependency Classification and Constraint Precedence
- **Decision:** Classify dependency candidates based on explicit source-level syntactic evidence:
  - Runtime imports from production source directories -> `runtime` (direct).
  - Imports discovered only in test files/directories (`tests/`, `test_*.py`) -> `dev`.
  - Imports discovered only within `if TYPE_CHECKING:` guards -> `type_checking`.
  - Guarded imports discovered inside `try/except ImportError:` -> `optional`.
  - Imports originating from Jupyter notebooks (`.ipynb`) -> `notebook`.
  - Dynamic imports (`__import__`, `importlib`) -> unresolved diagnostics.
- **Mapping Safety:** HIGH-confidence unambiguous mappings are automatically considered for candidate generation. Ambiguous mappings (e.g. `cv2` mapping to both `opencv-python` and `opencv-python-headless`) are NEVER automatically selected.
- **Constraint Precedence:** Static project constraints discovered in `pyproject.toml`, `requirements.txt`, `constraints.txt`, or `setup.cfg` take absolute precedence over unconstrained import candidates. Existing declarations are never silently overwritten.

### ADR-016: Resolver Execution and Security Isolation
- **Decision:** Subprocess execution for dependency resolution is strictly isolated and guarded:
  - Subprocesses are executed exclusively within disposable temporary directories (`ResolutionWorkspace`) containing synthetic manifests; user repository files are never modified without explicit consent.
  - Subprocess commands are executed with explicit argument vectors (`shell=False`), working directories, and enforced timeouts.
  - Subprocess commands and error outputs are sanitized to avoid leaking sensitive registry credentials into log files or user reports.
  - Untrusted code execution is prevented: `setup.py` is never run statically, and resolution passes `--no-build` or `--only-binary=:all:` to avoid executing arbitrary third-party build hooks during resolution.

### ADR-017: Disposable Runtime Environment Lifecycle
- **Context:** Validating dependency resolution requires testing installation and imports without polluting the host Python environment or leaking test artifacts across executions.
- **Decision:** All validation workflows create short-lived, disposable environments tracked via `EnvironmentManager`. Environments are created with isolated prefixes, tracked in context managers, and unconditionally cleaned up upon completion or interruption (unless explicitly requested to be retained via `--keep-environment`).
- **Dependency Isolation vs. OS Security Isolation:** A Python virtual environment (`venv`) provides filesystem separation and package namespace isolation only; it is **NOT** an operating-system security sandbox. Code running inside a virtual environment has full user-level permissions to access the host filesystem, network, and process space. Therefore, untrusted code execution must never be permitted on the host under the false assumption that a venv provides security containment.

### ADR-018: Trust-Aware Execution Policy
- **Context:** Python package installation and module importing can execute arbitrary code (e.g., in `setup.py`, build backends, or package `__init__.py`).
- **Decision:** PyDeps enforces a four-tier explicit trust policy:
  1. `static_only`: Default policy when execution authorization is absent. No subprocess execution or package installation is performed.
  2. `trusted_local`: Local execution on the host system permitted only with explicit user authorization (`--allow-local-execution`). Requires separate authorization for running project tests (`--allow-project-code`).
  3. `isolated_container`: Hardened container execution using Docker with dropped privileges, read-only root/source mounts, restricted tmpfs, resource limits, and network isolation.
  4. `remote_runner`: Structured interface for remote CI/CD execution environments.
- **Principle of Least Privilege:** Source distributions (`sdist`) are disallowed by default during installation validation (`--only-binary=:all:`) to avoid running unvetted build backend code on the host. Project test suites require distinct, opt-in permission.

### ADR-019: Cross-Platform Runtime Runner Capabilities
- **Context:** Dependency resolution can be calculated statically for foreign architectures and operating systems, but runtime execution must only run on compatible systems.
- **Decision:** Validation runners implement the `ExecutionRunner` protocol and declare precise platform capabilities (`supported_os`, `supported_arch`, `isolation_level`, `network_support`).
- **Zero-False-Claims Guarantee:** A runner must strictly reject targets it cannot natively execute. The local runner will never claim validation of foreign OS or CPU architectures. The Docker runner executes Linux container targets only and will reject Windows or macOS targets rather than substituting Linux.

### ADR-020: Runtime Validation Levels and Evidence
- **Context:** Users require progressive validation confidence ranging from package installation to full functional verification.
- **Decision:** Validation is structured into three progressive, independently evaluated stages:
  - **L1 (Installation):** Verifies interpreter availability, creates a disposable environment, installs exact resolved versions (wheel-first), runs `pip check` consistency verification, and captures installed package inventories.
  - **L2 (Import Smoke Tests):** Tests third-party imports in isolated, per-package subprocesses to catch import-time syntax errors, missing C extensions, or incompatible shared libraries.
  - **L3 (Project Test Execution):** Executes user-approved project test commands (e.g., `pytest`) under strict timeouts, resource limits, safe environment variable allowlists, and disabled network access.
- **Evidence Preservation:** Every validation stage preserves execution status (`passed`, `failed`, `partial`, `skipped`, `unsupported`, `unverified`, `timed_out`, `blocked_by_policy`), command logs, sanitized diagnostics, and duration. Results are exported to machine-readable JSON, HTML dashboards, and sanitized log files.

### ADR-021: Unified Diagnostic Pipeline and Partial Results
- **Context:** Developers need a cohesive command (`pydeps diagnose`) that sequentially executes scanning, import extraction, package mapping, metadata retrieval, cross-platform compatibility matrix evaluation, dependency resolution, optional runtime validation, and report export without halting completely if an intermediate stage fails or warnings occur.
- **Decision:** `PyDeps.diagnose()` coordinates all pipeline stages with per-stage timing, exception isolation, and structured diagnostics preservation. If any stage encounters an issue (e.g., PyPI rate limit, ambiguous mapping, or resolver conflict), the pipeline retains all prior stage artifacts, marks the affected stage status (`failed`, `partial`, `blocked_by_policy`), and continues downstream reporting. Missing or failed stages are never converted into false successes.

### ADR-022: Self-Contained Offline Dashboard Architecture
- **Context:** Enterprise security policies and air-gapped CI/CD environments prohibit external CDN downloads, tracking pixels, or remote analytics scripts when inspecting reports. Furthermore, untrusted project strings could lead to stored XSS vulnerabilities.
- **Decision:** The HTML dashboard (`index.html`) is 100% self-contained and offline-capable:
  - System font fallbacks and embedded modern SVG/CSS styling provide premium dark/light mode visuals with zero external font or script CDN requests.
  - All project strings, package names, version constraints, and error messages are strictly escaped using standard HTML escaping before injection.
  - Dependency graphs and compatibility matrices are rendered through declarative SVG and responsive HTML tables without executing untrusted external scripts.

### ADR-023: Versioned Diagnostic Schema and Regression Comparison
- **Context:** Automation tooling, CI pipelines, and developers comparing reports across Git branches need a stable, versioned schema and deterministic delta analysis.
- **Decision:** All JSON reports adhere to versioned schema `1.0.0` (`DiagnosticReport`). The `pydeps compare` engine compares two reports to surface newly discovered imports, removed imports, package mapping shifts, version changes, new conflicts, and compatibility regressions. Crucially, the comparator distinguishes actual code regressions from differences caused by changed target environments or analysis configurations.

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
│       │   ├── dependencies.py   # Dependency, ResolutionRequest, ResolutionResult, ResolvedDependencyGraph
│       │   ├── compatibility.py  # CompatibilityResult, Matrix, TargetPlatformProfile
│       │   ├── validation.py     # ValidationResult, ValidationStatus, ValidationReport, RunnerCapabilities
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
│       ├── compatibility/
│       │   ├── __init__.py       # Compatibility engine public exports
│       │   ├── platform_profiles.py # TargetPlatformProfile and target wheel tag generation
│       │   ├── python_compatibility.py # Requires-Python specifier evaluator
│       │   ├── marker_evaluator.py # PEP 508 isolated environment marker evaluator
│       │   ├── wheel_compatibility.py # Wheel filename parser & tag intersection evaluator
│       │   ├── artifact_evaluator.py # Wheel vs sdist candidate evaluation
│       │   ├── compatibility_engine.py # Release-level compatibility engine orchestrator
│       │   └── compatibility_matrix.py # Multi-target, multi-package matrix builder
│       ├── resolver/
│       │   ├── __init__.py       # Resolver public exports
│       │   ├── dependency_classifier.py # Grouping imports into runtime, dev, type-checking, etc.
│       │   ├── constraint_collector.py # Static parsing of pyproject.toml, requirements, constraints
│       │   ├── resolution_strategy.py # Strategy mapping to resolver flags
│       │   ├── resolution_workspace.py # Isolated temporary resolution workspace
│       │   ├── conflict_analyzer.py # Structured conflict and diagnostic extraction
│       │   ├── uv_backend.py     # Primary uv subprocess backend (uv lock, uv pip compile)
│       │   ├── pip_backend.py    # Fallback pip subprocess backend (pip install --dry-run --report)
│       │   ├── lockfile_exporter.py # Safe disk exporter for uv.lock, requirements.txt, resolution.json
│       │   ├── dependency_resolver.py # Unified resolver backend execution engine
│       │   └── resolution_orchestrator.py # End-to-end resolution pipeline coordinator
│       ├── validation/
│       │   ├── __init__.py       # Validation public exports
│       │   ├── network_policy.py # Network isolation, environment allowlist, and credential redaction
│       │   ├── interpreter_discovery.py # Python interpreter discovery and compatibility inspection
│       │   ├── environment_manager.py # Disposable environment lifecycle and cleanup manager
│       │   ├── report_generator.py # JSON, HTML report, and sanitized log generation
│       │   ├── validation_orchestrator.py # Multi-stage validation coordinator
│       │   └── runners/
│       │       ├── __init__.py   # Runner exports
│       │       ├── base.py       # ExecutionRunner protocol/abstract base class
│       │       ├── local_runner.py # Subprocess local virtual environment runner
│       │       ├── docker_runner.py # Hardened Linux container runner
│       │       └── remote_runner.py # Remote CI runner interface
│       ├── reporting/
│       │   ├── __init__.py       # Reporting module exports
│       │   ├── report_schema.py  # Versioned DiagnosticReport and section schemas
│       │   ├── report_builder.py # Evidence-backed report builder and recommendations
│       │   ├── json_renderer.py  # JSON serialization and stage artifact exporter
│       │   ├── html_renderer.py  # Self-contained offline HTML dashboard renderer
│       │   └── report_comparison.py # Multi-report regression and delta comparator
│       └── cli/
│           ├── __init__.py
│           └── main.py           # Typer CLI application (diagnose, report, compare, scan, analyze, map, etc.)
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
│   │   ├── test_metadata_parser.py# PEP 508 Requires-Dist parsing, artifacts, wheel tags
│   │   ├── test_platform_profiles.py # Platform profiles, wheel tags, and marker envs
│   │   ├── test_python_compatibility.py # Requires-Python boundaries, compound specifiers
│   │   ├── test_marker_evaluator.py # PEP 508 marker evaluations and missing field detection
│   │   ├── test_wheel_compatibility.py # Wheel tag matching (universal, abi3, manylinux, musl)
│   │   ├── test_artifact_evaluator.py # Artifact evaluator, wheel vs sdist, yanked warnings
│   │   ├── test_dependency_classifier.py # Import classification, overrides, and ambiguity safety
│   │   ├── test_constraint_collector.py # Static constraint collection from manifests
│   │   ├── test_resolution_strategy.py # Strategy mapping to uv and pip flags
│   │   ├── test_conflict_analyzer.py # Normalization of resolver conflicts and diagnostics
│   │   ├── test_runner_interface.py # Runner capabilities and foreign platform rejection
│   │   ├── test_interpreter_discovery.py # Python interpreter discovery and compatibility
│   │   ├── test_environment_manager.py # Disposable environment lifecycle and cleanup
│   │   ├── test_network_policy.py # Safe environment allowlist, secret redaction, pip flags
│   │   ├── test_validation_orchestrator.py # Validation orchestrator dry-run, execution, stages
│   │   ├── test_report_schema.py # Versioned JSON report schema and StageStatus validation
│   │   ├── test_report_builder.py # Evidence-backed recommendations and partial stage handling
│   │   ├── test_report_comparison.py # Report delta and regression detection
│   │   └── test_html_renderer.py # Self-contained HTML dashboard, themes, and XSS sanitization
│   └── integration/
│       ├── test_cli.py           # CLI invocation (scan, analyze, map, metadata, errors)
│       ├── test_cli_compatibility.py # CLI compatibility command tests
│       ├── test_cli_resolve.py   # CLI resolve command tests (universal, per-target, json)
│       ├── test_cli_validate.py  # CLI validate command tests (dry-run, json, levels)
│       ├── test_cli_diagnose.py  # CLI diagnose, report, compare, exit codes, pure JSON stdout
│       ├── test_facade.py        # High-level PyDeps facade end-to-end flow
│       ├── test_metadata_provider.py # MetadataProvider mocked PyPI integration & caching
│       ├── test_pipeline.py      # End-to-end multi-package pipeline execution
│       ├── test_pypi_client.py   # PyPIClient HTTP status, rate limit, and retry handling
│       ├── test_compatibility_matrix.py # Multi-target compatibility matrix and JSON serialization
│       ├── test_uv_backend.py    # uv subprocess backend execution and lockfile parsing
│       ├── test_pip_backend.py   # pip fallback dry-run resolution and foreign platform flags
│       ├── test_resolver_e2e.py  # End-to-end resolution flows (Flask, ML, conflicting, markers)
│       ├── test_local_runner.py  # LocalRunner execution, installation, and cleanup
│       ├── test_docker_runner.py # DockerRunner argument hardening and platform rejection
│       └── test_validation_security.py # Security authorization, secret redaction, and sdist safety
├── docs/
│   └── architecture.md           # This architecture documentation
├── pyproject.toml                # Project metadata, dependencies, tool configs
├── README.md                     # Overview, quickstart, and development guide
└── .gitignore                    # Standard Python/IDE exclusions
```

