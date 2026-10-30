# PyDeps Architecture Documentation

## 1. System Overview

PyDeps is a Python Dependency Intelligence Engine designed to analyze codebases, discover package imports, map imports to distributions, verify cross-platform and multi-Python version compatibility, resolve dependencies, and validate runtime safety in isolated environments.

```
+-------------------------------------------------------------------+
|                        Interfaces / Consumers                     |
|        CLI (Typer)     |   Python API   |   VS Code Extension     |
+-------------------------------------------------------------------+
                                  |
                                  v
+-------------------------------------------------------------------+
|                     PyDeps Engine Core (src/pydeps)               |
|                                                                   |
|   +-------------------+       +-------------------------------+   |
|   |  Project Scanner  | ----> |  Import Extraction & Mapping  |   |
|   +-------------------+       +-------------------------------+   |
|                                               |                   |
|                                               v                   |
|   +-------------------+       +-------------------------------+   |
|   |  Resolver Service | <---> |  Compatibility Engine         |   |
|   +-------------------+       +-------------------------------+   |
|             |                                 |                   |
|             v                                 v                   |
|   +-------------------+       +-------------------------------+   |
|   | Export Generation |       |  Runtime Validation Service   |   |
|   +-------------------+       +-------------------------------+   |
+-------------------------------------------------------------------+
```

## 2. Core Architectural Principles

1. **Modular Architecture:** Distinct components for configuration, scanning, mapping, compatibility, resolution, and validation.
2. **Strong Typing & Predictable Data Contracts:** Pydantic v2 schemas govern all inputs and outputs.
3. **Independent and Testable Components:** High cohesion and unit test coverage across all modules without external side effects in test suites.
4. **No Unnecessary Abstractions:** Straightforward abstractions that match real workflows.
5. **No Hardcoded Package Compatibility Assumptions:** Decisions are grounded in PEP 508 environment markers, distribution tags (PEP 425), and verified repository metadata.
6. **Explainable Compatibility Decisions:** Every result pairs an explicit status with detailed evidence and reasons.
7. **Network Isolation:** Any remote operations (PyPI JSON API, wheel inspection) are encapsulated behind abstract service interfaces.
8. **Host-Independent Target Environments:** Target environments describe arbitrary target systems (OS, architecture, Python version, implementation) without coupling to the host system running PyDeps.

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

## 4. Component Layout

```
PyDeps/
├── src/
│   └── pydeps/
│       ├── __init__.py           # Package version and top-level exports
│       ├── py.typed              # PEP 561 typing marker
│       ├── config.py             # Project configuration loader & validator
│       ├── exceptions.py         # PyDeps domain exception hierarchy
│       ├── models/
│       │   ├── __init__.py       # Unified model namespace exports
│       │   ├── project.py        # ProjectConfig, TargetEnvironment, and core enums
│       │   ├── imports.py        # ImportRecord, PackageMapping
│       │   ├── dependencies.py   # Dependency, ResolutionResult
│       │   ├── compatibility.py  # CompatibilityResult, CompatibilityStatus
│       │   ├── validation.py     # ValidationResult, ValidationStatus
│       │   └── report.py         # AnalysisReport aggregate model
│       └── cli/
│           ├── __init__.py
│           └── main.py           # Typer CLI application entry point
├── tests/
│   ├── unit/
│   │   ├── test_config.py        # Config parsing, validation, and defaults
│   │   └── test_models.py        # Model serialization, enums, constraints
│   └── integration/
│       └── test_cli.py           # CLI invocation, --help, --version
├── docs/
│   └── architecture.md           # This document
├── pyproject.toml                # Project metadata, dependencies, tool configs
├── README.md                     # Overview, quickstart, and development guide
└── .gitignore                    # Standard Python/IDE exclusions
```
