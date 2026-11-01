# Changelog

All notable changes to **PyDeps Intelligence** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0a1] - 2026-11-01

### Added
- **Product Identity & Distribution:**
  - Distribution name: `pydeps-intelligence`.
  - Python package: `pydeps_intelligence`.
  - CLI entry point: `pydeps-intel`.
  - Official Apache License 2.0 (`LICENSE`) and `NOTICE` attribution.
- **Source Intelligence Engine (P1):**
  - AST-based static source scanner supporting `.py` files and Jupyter notebooks (`.ipynb`).
  - Strict classification into standard library, local modules, and external candidates without code execution.
- **Package Intelligence & PyPI Metadata (P2):**
  - Curated import-to-distribution mapping database (`cv2` -> `opencv-python`, `PIL` -> `Pillow`, `yaml` -> `PyYAML`, etc.).
  - Asynchronous PyPI client with disk-backed caching and offline mode support.
  - Ambiguity detection and customizable local overrides.
- **Cross-Platform Compatibility Matrix Engine (P3):**
  - Evidence-based compatibility evaluation against Python versions (3.8–3.13+), operating systems (Linux, Windows, macOS), CPU architectures, and Python implementations.
  - Static wheel tag and environment marker evaluation.
- **Dependency Resolution Engine (P4):**
  - Direct and transitive dependency graph resolution.
  - Multi-platform universal resolution and per-target resolution with `uv` and `pip` backends.
  - Conflict detection, extras handling, and reproducible lockfile export.
- **Runtime Validation & Environment Isolation Engine (P5):**
  - Multi-tier isolated execution (L1 installation, L2 import smoke tests, L3 authorized project tests).
  - Pluggable runners: Docker container runner, disposable local virtual environment runner, and remote runner.
  - Strict execution policy blocking unauthorized local execution by default.
- **Unified Reporting & Offline Dashboards (P6):**
  - Single-command diagnosis via `pydeps-intel diagnose`.
  - Schema-versioned JSON report output conforming to Draft 2020-12.
  - 100% self-contained, offline HTML dashboard with dark/light themes and SVG dependency graphs.
  - Differential report comparison engine (`pydeps-intel compare`) detecting configuration shifts and regressions.
- **Packaging & Release Infrastructure (P8):**
  - Clean wheel and source distribution packaging via PEP 517/518 (`build`).
  - PyPI metadata audit and twine verification.
  - GitHub Actions CI matrix testing (Python 3.10–3.13 on Linux, macOS, Windows) and Trusted Publishing workflow (OIDC).
