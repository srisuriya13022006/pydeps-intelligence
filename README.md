# PyDeps

> A Python Dependency Intelligence Engine

PyDeps analyzes Python projects, discovers dependencies, evaluates compatibility across multiple Python versions and operating systems, resolves dependency constraints, validates dependencies inside isolated environments, and generates reproducible dependency files.

## Product Vision

PyDeps serves as a unified core engine for dependency intelligence, designed to power:
- **Core Engine:** Python package (`pydeps`) providing data contracts, static analysis, compatibility checking, and resolution.
- **Command-Line Interface:** Standalone CLI (`pydeps`) for developer workflows and CI/CD pipelines.
- **IDE Extensions:** Direct integration into editor environments (e.g., VS Code extension).

PyDeps runs on Python 3.10+ while independently supporting analysis of target projects that run on older Python versions.

## Architectural Principles

1. **Modular Architecture:** Clear separation of responsibilities between scanning, mapping, compatibility, resolution, and validation.
2. **Strong Typing & Predictable Contracts:** Pydantic v2 models define explicit schemas for all internal and external communication.
3. **Independent & Testable Components:** High cohesion, loose coupling, comprehensive unit and integration tests.
4. **No Unnecessary Abstractions:** Direct, clean interfaces without speculative over-engineering.
5. **No Hardcoded Compatibility Assumptions:** Dynamic evaluation using package metadata, PyPI wheel tags, and environment markers.
6. **Explainable Decisions:** Every compatibility and resolution outcome is backed by auditable evidence and clear reasons.
7. **Isolated Network Operations:** Network accesses are isolated behind dedicated service interfaces.
8. **Safe Runtime Validation:** Untrusted project code is never executed in the developer's host environment.

## Quick Start (P0)

### Installation

PyDeps requires Python 3.10 or later:

```bash
# Clone the repository
git clone https://github.com/your-org/PyDeps.git
cd PyDeps

# Create and activate a virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install in editable mode with development dependencies
pip install -e ".[dev]"
```

### CLI Usage

```bash
# Display general help
pydeps --help

# Check version
pydeps --version
```

### Development & Testing

```bash
# Run test suite
pytest

# Run linter
ruff check .
```

## License

MIT
