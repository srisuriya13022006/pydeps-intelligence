# PyDeps Intelligence

[![PyPI Version](https://img.shields.io/pypi/v/pydeps-intelligence.svg)](https://pypi.org/project/pydeps-intelligence/)
[![Python Versions](https://img.shields.io/pypi/pyversions/pydeps-intelligence.svg)](https://pypi.org/project/pydeps-intelligence/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

**PyDeps Intelligence** is a comprehensive, deterministic Python dependency intelligence engine. It statically analyzes source repositories, discovers imports, maps modules to canonical PyPI packages, evaluates cross-platform compatibility across operating systems and Python versions, resolves dependency constraint graphs, and safely validates environments inside isolated runners.

---

## The Problem

Modern Python projects struggle with opaque, fragile dependency lifecycles:
- **Undeclared Imports:** Developers import external packages in code that are omitted from `pyproject.toml` or `requirements.txt`.
- **Import vs. Distribution Ambiguity:** Code imports `cv2`, `PIL`, or `yaml`, which do not match their canonical PyPI distribution names (`opencv-python`, `Pillow`, `PyYAML`).
- **Cross-Platform Incompatibilities:** A package installs cleanly on macOS x86_64, but wheel artifacts or C-extensions fail on Windows or Linux ARM64.
- **Transitive Conflicts:** Resolvers fail late or silently introduce incompatible transitive constraints.
- **Execution Risks:** Testing dependencies often triggers arbitrary setup scripts (`setup.py`) or untrusted module execution directly on the developer's workstation.

PyDeps Intelligence solves these issues by unifying static AST inspection, curated mapping databases, deterministic compatibility matrix evaluation, multi-backend dependency resolution, and policy-governed runtime validation.

---

## Key Capabilities

1. **Deterministic Source Intelligence (AST)**: Recursively scans `.py` files and Jupyter notebooks (`.ipynb`) without executing user code. Classifies imports into standard library, local project modules, and external candidates.
2. **Package Intelligence & PyPI Mapping**: Bridges import names to PyPI distributions using curated disambiguation heuristics, confidence tiers, and local override configuration.
3. **Cross-Platform Compatibility Matrix**: Statically evaluates package releases against target combinations of Python versions (3.8–3.13+), operating systems (Linux, macOS, Windows), CPU architectures (x86_64, aarch64, arm64), and Python implementations (CPython, PyPy).
4. **Dependency Resolution Engine**: Supports multi-platform universal resolution and per-target resolution with backends including `uv` and `pip`, detecting conflicts, extras, and environment markers.
5. **Environment Isolation & Safe Runtime Validation**: Multi-tier validation (L1: package installation, L2: import smoke tests, L3: authorized project test suites) with sandboxed runners (`docker`, disposable local virtual environments, and remote execution stubs). Untrusted execution is strictly blocked by default.
6. **Unified Diagnosis & Offline Dashboards**: Exports comprehensive, schema-versioned JSON reports (`report.json`) and 100% self-contained, offline HTML dashboards with interactive dark/light modes, SVG dependency graphs, and developer guidance.
7. **Report Regression Comparison**: Diffs diagnostic runs across Git branches or CI pipelines to catch compatibility regressions, version drifts, and newly introduced conflicts.

---

## Installation

Install PyDeps Intelligence from PyPI:

```bash
pip install pydeps-intelligence
```

For development and testing:

```bash
pip install pydeps-intelligence[dev]
```

Verify the installation:

```bash
pydeps-intel --help
```

---

## Quick Start

### 1. Unified Diagnosis Pipeline

Diagnose any Python project root with a single command:

```bash
pydeps-intel diagnose ./my-project
```

Generate self-contained HTML and JSON reports:

```bash
pydeps-intel diagnose ./my-project --output ./pydeps-output
```

Run in 100% offline mode using local caches:

```bash
pydeps-intel diagnose ./my-project --offline
```

Stream pure, machine-readable JSON to stdout:

```bash
pydeps-intel diagnose ./my-project --json > report.json
```

---

## Command-Line Usage

### Source Scanning & Import Analysis

```bash
# Discover Python source files, notebooks, and metadata files
pydeps-intel scan ./my-project

# Extract and classify all imports (stdlib, local, external)
pydeps-intel analyze ./my-project
```

### Package Intelligence & Metadata

```bash
# Map discovered imports to PyPI distribution names
pydeps-intel map ./my-project

# Fetch and inspect release metadata from PyPI
pydeps-intel metadata httpx
```

### Compatibility Matrix

```bash
# Evaluate package compatibility across target platforms
pydeps-intel compatibility requests --target linux-x86_64-cpython-py3.11 --target win_amd64-cpython-py3.12
```

### Dependency Resolution

```bash
# Universal resolution across all platforms
pydeps-intel resolve ./my-project --mode universal --strategy latest-compatible

# Export reproducible requirements lockfile
pydeps-intel resolve ./my-project --output-file requirements.lock
```

### Runtime Validation

```bash
# Perform disposable virtualenv installation smoke test (requires explicit authorization)
pydeps-intel validate ./my-project --runner local --level install --allow-local-execution

# Run validation in Docker container
pydeps-intel validate ./my-project --runner docker --level imports
```

### Report Operations & Comparisons

```bash
# Render offline HTML dashboard from an existing JSON report
pydeps-intel report ./pydeps-output/report.json --output ./pydeps-output/index.html

# Detect regressions and configuration shifts between runs
pydeps-intel compare baseline-report.json candidate-report.json
```

---

## Python API

You can embed PyDeps Intelligence directly into your Python tools, linters, or CI scripts:

```python
from pydeps_intelligence import PyDeps, TargetEnvironment, OperatingSystem, Architecture

# Initialize engine coordinator
engine = PyDeps(project_path=".")

# Run end-to-end diagnosis
report = engine.diagnose(
    universal=True,
    backend="uv",
    strategy="latest-compatible",
    offline=False,
)

print(f"Pipeline Status:    {report.pipeline_status.value}")
print(f"Dependency Health:  {report.dependency_health_status.value}")
print(f"Validation Status:  {report.runtime_validation_status.value}")

for rec in report.recommendations:
    print(f"[{rec.severity.value.upper()}] {rec.title}: {rec.description}")
```

---

## Configuration

PyDeps Intelligence can be configured via `pyproject.toml` (`[tool.pydeps_intelligence]`) or a dedicated `pydeps-intel.toml` file:

```toml
[tool.pydeps_intelligence]
target_python_versions = ["3.10", "3.11", "3.12"]
target_operating_systems = ["linux", "windows", "macos"]
target_architectures = ["x86_64", "arm64"]
validate_runtime = false
output_directory = "./pydeps-output"
excluded_directories = [".git", ".venv", "tests/fixtures"]

[tool.pydeps_intelligence.overrides]
# Explicit overrides for custom or internal packages
my_custom_module = "my-internal-distribution"
```

---

## Supported Environments

- **Host Environment (to execute PyDeps Intelligence):**
  - Python 3.10, 3.11, 3.12, 3.13+
  - Linux (glibc & musl), macOS (Intel & Apple Silicon), Windows (x86_64, ARM64)
- **Target Analysis (projects analyzed by PyDeps Intelligence):**
  - Python 3.8, 3.9, 3.10, 3.11, 3.12, 3.13+

---

## Execution Safety & Sandboxing

A Python virtual environment isolates dependencies, **not** system resources. To protect developer systems:
- Static analysis never imports or executes scanned code.
- Network operations are restricted and honor offline mode.
- Local runtime execution requires the explicit `--allow-local-execution` flag.
- Containerized execution via Docker provides isolation when validating untrusted third-party code.

---

## Contributing

We welcome contributions! To set up a development workspace:

```bash
git clone https://github.com/your-org/pydeps-intelligence.git
cd pydeps-intelligence
python -m venv .venv
source .venv/bin/activate  # Or .venv\Scripts\activate on Windows
pip install -e ".[dev]"

# Run tests and linters
pytest -q
ruff check .
ruff format --check .
```

---

## License

PyDeps Intelligence is distributed under the terms of the [Apache License, Version 2.0](LICENSE).
Copyright 2026 sri suriya.
