"""Collector of existing project dependency declarations and constraints."""

from __future__ import annotations

import configparser
import re
from pathlib import Path
from typing import Any

import tomllib
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

from pydeps_intelligence.models.dependencies import Dependency, DependencyType, ResolutionDiagnostic


def parse_pep508_line(
    line: str, dep_type: DependencyType = DependencyType.DIRECT
) -> Dependency | None:
    """Parse a single line into a Dependency object using packaging.requirements.Requirement."""
    stripped = line.strip()
    # Strip comments and ignore empty lines or flags
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("-") or stripped.startswith("--"):
        return None

    # Handle inline comments
    clean_line = re.split(r"\s+#", stripped)[0].strip()
    if not clean_line:
        return None

    try:
        req = Requirement(clean_line)
        version_spec = str(req.specifier) if req.specifier else None
        marker_str = str(req.marker) if req.marker else None
        extras = frozenset(req.extras) if req.extras else frozenset()

        return Dependency(
            name=canonicalize_name(req.name),
            version_specifier=version_spec,
            extras=extras,
            environment_marker=marker_str,
            dependency_type=dep_type,
        )
    except InvalidRequirement:
        return None


class ConstraintCollector:
    """Discovers and parses static project dependency declarations without code execution."""

    def __init__(self, project_path: Path | str) -> None:
        self.project_path = Path(project_path)

    def collect_from_pyproject_toml(
        self, pyproject_path: Path
    ) -> tuple[list[Dependency], list[ResolutionDiagnostic]]:
        """Parse static dependencies from pyproject.toml."""
        dependencies: list[Dependency] = []
        diagnostics: list[ResolutionDiagnostic] = []

        if not pyproject_path.exists():
            return dependencies, diagnostics

        try:
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
        except Exception as exc:
            diagnostics.append(
                ResolutionDiagnostic(
                    message=f"Failed to read pyproject.toml: {exc}",
                    level="error",
                    source="constraint_collector",
                )
            )
            return dependencies, diagnostics

        # 1. Standard PEP 621 [project.dependencies]
        project_table = data.get("project", {})
        if "dependencies" in project_table:
            raw_deps = project_table.get("dependencies", [])
            if isinstance(raw_deps, list):
                for item in raw_deps:
                    if isinstance(item, str):
                        dep = parse_pep508_line(item, DependencyType.DIRECT)
                        if dep:
                            dependencies.append(dep)

        # 2. PEP 621 [project.optional-dependencies]
        if "optional-dependencies" in project_table:
            opt_table = project_table.get("optional-dependencies", {})
            if isinstance(opt_table, dict):
                for extra_name, req_list in opt_table.items():
                    if isinstance(req_list, list):
                        for item in req_list:
                            if isinstance(item, str):
                                dep_type = (
                                    DependencyType.DEV
                                    if extra_name.lower() in ("dev", "test", "testing")
                                    else DependencyType.OPTIONAL
                                )
                                dep = parse_pep508_line(item, dep_type)
                                if dep:
                                    dependencies.append(dep)

        # 3. PEP 735 [dependency-groups]
        dep_groups = data.get("dependency-groups", {})
        if isinstance(dep_groups, dict):
            for group_name, req_list in dep_groups.items():
                if isinstance(req_list, list):
                    for item in req_list:
                        if isinstance(item, str):
                            dep_type = (
                                DependencyType.DEV
                                if group_name.lower() in ("dev", "test", "testing")
                                else DependencyType.OPTIONAL
                            )
                            dep = parse_pep508_line(item, dep_type)
                            if dep:
                                dependencies.append(dep)

        # 4. Poetry [tool.poetry.dependencies]
        poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
        if isinstance(poetry_deps, dict):
            for pkg, spec in poetry_deps.items():
                if pkg.lower() == "python":
                    continue
                if isinstance(spec, str):
                    dep = parse_pep508_line(f"{pkg} {spec}", DependencyType.DIRECT)
                    if dep:
                        dependencies.append(dep)
                elif isinstance(spec, dict) and "version" in spec:
                    dep = parse_pep508_line(f"{pkg} {spec['version']}", DependencyType.DIRECT)
                    if dep:
                        dependencies.append(dep)

        return dependencies, diagnostics

    def collect_from_requirements_file(
        self, req_path: Path, dep_type: DependencyType = DependencyType.DIRECT
    ) -> tuple[list[Dependency], list[ResolutionDiagnostic]]:
        """Parse dependencies from requirements.txt or constraints.txt."""
        dependencies: list[Dependency] = []
        diagnostics: list[ResolutionDiagnostic] = []

        if not req_path.exists():
            return dependencies, diagnostics

        try:
            with open(req_path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            for line in lines:
                stripped = line.strip()
                if stripped.startswith("-r ") or stripped.startswith("--requirement "):
                    inc_file = stripped.split(None, 1)[1].strip()
                    inc_path = req_path.parent / inc_file
                    sub_deps, sub_diags = self.collect_from_requirements_file(inc_path, dep_type)
                    dependencies.extend(sub_deps)
                    diagnostics.extend(sub_diags)
                else:
                    dep = parse_pep508_line(line, dep_type)
                    if dep:
                        dependencies.append(dep)
        except Exception as exc:
            diagnostics.append(
                ResolutionDiagnostic(
                    message=f"Failed to parse requirements file '{req_path.name}': {exc}",
                    level="error",
                    source="constraint_collector",
                )
            )

        return dependencies, diagnostics

    def collect_from_setup_cfg(
        self, cfg_path: Path
    ) -> tuple[list[Dependency], list[ResolutionDiagnostic]]:
        """Statically parse dependencies from setup.cfg without executing any code."""
        dependencies: list[Dependency] = []
        diagnostics: list[ResolutionDiagnostic] = []

        if not cfg_path.exists():
            return dependencies, diagnostics

        try:
            parser = configparser.ConfigParser()
            parser.read(cfg_path, encoding="utf-8")

            if parser.has_section("options"):
                if parser.has_option("options", "install_requires"):
                    raw = parser.get("options", "install_requires")
                    for line in raw.splitlines():
                        dep = parse_pep508_line(line, DependencyType.DIRECT)
                        if dep:
                            dependencies.append(dep)

            if parser.has_section("options.extras_require"):
                for extra_name, raw in parser.items("options.extras_require"):
                    dep_type = (
                        DependencyType.DEV
                        if extra_name.lower() in ("dev", "test")
                        else DependencyType.OPTIONAL
                    )
                    for line in raw.splitlines():
                        dep = parse_pep508_line(line, dep_type)
                        if dep:
                            dependencies.append(dep)
        except Exception as exc:
            diagnostics.append(
                ResolutionDiagnostic(
                    message=f"Failed to parse setup.cfg: {exc}",
                    level="error",
                    source="constraint_collector",
                )
            )

        return dependencies, diagnostics

    def collect_all_constraints(self) -> dict[str, Any]:
        """Scan project root for all standard dependency declaration files."""
        all_dependencies: dict[str, Dependency] = {}
        all_diagnostics: list[ResolutionDiagnostic] = []

        # 1. pyproject.toml
        pyproject = self.project_path / "pyproject.toml"
        deps, diags = self.collect_from_pyproject_toml(pyproject)
        for d in deps:
            all_dependencies[d.name] = d
        all_diagnostics.extend(diags)

        # 2. requirements.txt
        req_txt = self.project_path / "requirements.txt"
        deps, diags = self.collect_from_requirements_file(req_txt, DependencyType.DIRECT)
        for d in deps:
            if d.name not in all_dependencies:
                all_dependencies[d.name] = d
        all_diagnostics.extend(diags)

        # 3. requirements-dev.txt
        req_dev = self.project_path / "requirements-dev.txt"
        deps, diags = self.collect_from_requirements_file(req_dev, DependencyType.DEV)
        for d in deps:
            if d.name not in all_dependencies:
                all_dependencies[d.name] = d
        all_diagnostics.extend(diags)

        # 4. constraints.txt
        constraints_txt = self.project_path / "constraints.txt"
        deps, diags = self.collect_from_requirements_file(constraints_txt, DependencyType.DIRECT)
        for d in deps:
            if d.name not in all_dependencies:
                all_dependencies[d.name] = d
        all_diagnostics.extend(diags)

        # 5. setup.cfg
        setup_cfg = self.project_path / "setup.cfg"
        deps, diags = self.collect_from_setup_cfg(setup_cfg)
        for d in deps:
            if d.name not in all_dependencies:
                all_dependencies[d.name] = d
        all_diagnostics.extend(diags)

        return {
            "dependencies": list(all_dependencies.values()),
            "by_name": all_dependencies,
            "diagnostics": all_diagnostics,
        }
