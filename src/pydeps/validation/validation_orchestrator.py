"""Orchestrator for multi-level isolated runtime dependency validation."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from pydeps.models.dependencies import ResolutionResult, ResolutionStatus
from pydeps.models.imports import ImportRecord, ImportType
from pydeps.models.project import TargetEnvironment
from pydeps.models.validation import (
    EnvironmentInfo,
    ExecutionPolicy,
    ValidationReport,
    ValidationRequest,
    ValidationStage,
    ValidationStageResult,
    ValidationStatus,
)
from pydeps.validation.environment_manager import EnvironmentManager
from pydeps.validation.report_generator import ReportGenerator
from pydeps.validation.runners.base import ExecutionRunner
from pydeps.validation.runners.docker_runner import DockerRunner
from pydeps.validation.runners.local_runner import LocalRunner
from pydeps.validation.runners.remote_runner import RemoteRunner


class ValidationOrchestrator:
    """Coordinates runtime validation stages (L1 install, L2 smoke imports, L3 tests)."""

    def __init__(self, scratch_dir: Path | str | None = None) -> None:
        self.scratch_dir = Path(scratch_dir) if scratch_dir else None

    def validate(
        self,
        request: ValidationRequest,
        resolution_result: ResolutionResult | None = None,
        discovered_imports: list[ImportRecord] | None = None,
    ) -> ValidationReport:
        """Execute validation plan according to request policies and level."""
        # 1. Determine target environment
        target = request.target_environment
        if resolution_result and resolution_result.target and not target:
            target = resolution_result.target

        # 2. Select runner
        runner = self._select_runner(request)
        capabilities = runner.get_capabilities()

        # 3. Verify runner can execute requested target
        can_run, reason = runner.can_execute(target)
        if not can_run:
            return ValidationReport(
                project_name=request.project_path.name,
                project_path=request.project_path,
                status=ValidationStatus.UNSUPPORTED,
                target_environment=target,
                runner_type=request.runner_type,
                isolation_level=capabilities.isolation_level,
                execution_policy=request.execution_policy,
                network_policy=request.network_policy,
                diagnostics=[
                    reason
                    or f"Runner '{request.runner_type}' cannot execute target {target.platform_tag}"
                ],
                cleanup_status="not_created",
            )

        # 4. Handle Dry Run (Inspect execution plan without code execution)
        if request.dry_run:
            return self._build_dry_run_report(
                request, target, capabilities.isolation_level, resolution_result
            )

        # 5. Check trust policy & authorization
        if request.runner_type == "local" and not request.allow_local_execution:
            if request.execution_policy in (
                ExecutionPolicy.STATIC_ONLY,
                ExecutionPolicy.ISOLATED_CONTAINER,
            ):
                diag = (
                    "Local code execution is blocked by trust policy (STATIC_ONLY). "
                    "A Python venv provides dependency isolation, not an OS security sandbox. "
                    "Use --allow-local-execution to authorize local execution or "
                    "use --runner docker."
                )
                return ValidationReport(
                    project_name=request.project_path.name,
                    project_path=request.project_path,
                    status=ValidationStatus.BLOCKED_BY_POLICY,
                    target_environment=target,
                    runner_type=request.runner_type,
                    isolation_level=capabilities.isolation_level,
                    execution_policy=request.execution_policy,
                    network_policy=request.network_policy,
                    diagnostics=[diag],
                    cleanup_status="not_created",
                )

        # 6. Check incoming resolution status
        if resolution_result and resolution_result.status in (
            ResolutionStatus.FAILURE,
            ResolutionStatus.CONFLICT,
        ):
            diag = (
                "Cannot perform runtime validation: dependency resolution failed "
                f"with status '{resolution_result.status.value}'."
            )
            return ValidationReport(
                project_name=request.project_path.name,
                project_path=request.project_path,
                status=ValidationStatus.FAILED,
                target_environment=target,
                runner_type=request.runner_type,
                isolation_level=capabilities.isolation_level,
                execution_policy=request.execution_policy,
                network_policy=request.network_policy,
                diagnostics=[diag],
                cleanup_status="not_created",
            )

        # 7. Execute stages inside EnvironmentManager
        with EnvironmentManager(base_scratch_dir=self.scratch_dir) as env_mgr:
            env_info: EnvironmentInfo | None = None
            stages: dict[str, ValidationStageResult] = {}
            installed_packages: dict[str, str] = {}
            overall_status = ValidationStatus.PASSED
            diagnostics: list[str] = []

            try:
                # Provision environment
                env_info = env_mgr.create_disposable_environment(
                    runner=runner,
                    target=target,
                    keep=request.keep_environment,
                )

                # =========================================================================
                # L1: Installation Validation
                # =========================================================================
                l1_res, installed_packages = self._execute_l1_installation(
                    runner=runner,
                    env_info=env_info,
                    resolution_result=resolution_result,
                    request=request,
                )
                stages["installation"] = l1_res

                if l1_res.status != ValidationStatus.PASSED:
                    overall_status = ValidationStatus.FAILED
                    diagnostics.extend(l1_res.errors)

                # =========================================================================
                # L2: Import Smoke Tests
                # =========================================================================
                if (
                    request.level in ("imports", "project-tests")
                    and l1_res.status == ValidationStatus.PASSED
                ):
                    l2_res = self._execute_l2_imports(
                        runner=runner,
                        env_info=env_info,
                        discovered_imports=discovered_imports,
                        installed_packages=installed_packages,
                        resolution_result=resolution_result,
                        timeout=request.timeout_seconds,
                    )
                    stages["import_test"] = l2_res
                    if l2_res.status != ValidationStatus.PASSED:
                        overall_status = ValidationStatus.FAILED

                # =========================================================================
                # L3: Project Test Execution
                # =========================================================================
                if request.level == "project-tests" and l1_res.status == ValidationStatus.PASSED:
                    l3_res = self._execute_l3_project_tests(
                        runner=runner,
                        env_info=env_info,
                        request=request,
                    )
                    stages["project_test"] = l3_res
                    if l3_res.status != ValidationStatus.PASSED:
                        overall_status = ValidationStatus.FAILED

            except Exception as exc:
                overall_status = ValidationStatus.FAILED
                diagnostics.append(f"Unexpected validation orchestration failure: {exc}")
            finally:
                cleanup_status = "cleaned"
                if request.keep_environment and env_info:
                    cleanup_status = f"preserved at {env_info.environment_path}"
                elif env_info:
                    env_mgr.cleanup_environment(runner, env_info)

            stage_statuses = {name: s.status for name, s in stages.items()}

            report = ValidationReport(
                project_name=request.project_path.name,
                project_path=request.project_path,
                status=overall_status,
                target_environment=target,
                runner_type=request.runner_type,
                isolation_level=capabilities.isolation_level,
                execution_policy=request.execution_policy,
                network_policy=request.network_policy,
                python_interpreter_version=env_info.python_version if env_info else None,
                installed_packages=installed_packages,
                stages=stages,
                stage_statuses=stage_statuses,
                diagnostics=diagnostics,
                resource_limits={
                    "timeout_seconds": request.timeout_seconds,
                    "memory_limit": request.memory_limit,
                    "cpu_limit": request.cpu_limit,
                },
                environment_info=env_info,
                cleanup_status=cleanup_status,
            )

            # Export reports if requested
            if request.output_directory:
                ReportGenerator.generate_all(report, request.output_directory)

            return report

    def _execute_l1_installation(
        self,
        runner: ExecutionRunner,
        env_info: EnvironmentInfo,
        resolution_result: ResolutionResult | None,
        request: ValidationRequest,
    ) -> tuple[ValidationStageResult, dict[str, str]]:
        """Run L1 package installation and pip check."""
        start_t = time.perf_counter()
        errors: list[str] = []

        # Determine requirements source
        req_file: Path | None = None
        packages: list[str] | None = None

        if resolution_result:
            # Check for per-target output first
            req_content = None
            if (
                resolution_result.per_target_results
                and env_info.operating_system.value in resolution_result.per_target_results
            ):
                req_content = resolution_result.per_target_results[
                    env_info.operating_system.value
                ].requirements_txt
            elif resolution_result.requirements_txt:
                req_content = resolution_result.requirements_txt

            if req_content:
                req_file = env_info.environment_path / "resolved_requirements.txt"
                req_file.write_text(req_content, encoding="utf-8")
            elif resolution_result.graph:
                packages = [
                    f"{pkg.name}=={pkg.version}"
                    for pkg in resolution_result.graph.packages.values()
                    if pkg.version
                ]

        exit_code, log_out, inventory = runner.install_dependencies(
            env_info=env_info,
            requirements_file=req_file,
            packages=packages,
            timeout=request.timeout_seconds,
            network=request.network_policy,
            allow_sdist=False,
        )

        status = ValidationStatus.PASSED if exit_code == 0 else ValidationStatus.FAILED
        if exit_code != 0:
            errors.append(f"Package installation failed with exit code {exit_code}")

        # Run pip check if install succeeded
        if status == ValidationStatus.PASSED:
            check_code, check_log = runner.run_pip_check(env_info, timeout=60)
            log_out += f"\n--- pip check ---\n{check_log}"
            if check_code != 0:
                errors.append(
                    f"Dependency consistency check (pip check) reported issues:\n{check_log}"
                )

        duration = round(time.perf_counter() - start_t, 3)
        return (
            ValidationStageResult(
                stage=ValidationStage.INSTALLATION,
                status=status,
                duration_seconds=duration,
                installed_packages=inventory,
                errors=errors,
                logs=log_out,
            ),
            inventory,
        )

    def _execute_l2_imports(
        self,
        runner: ExecutionRunner,
        env_info: EnvironmentInfo,
        discovered_imports: list[ImportRecord] | None,
        installed_packages: dict[str, str],
        resolution_result: ResolutionResult | None,
        timeout: int,
    ) -> ValidationStageResult:
        """Run L2 smoke import tests for candidate third-party modules."""
        start_t = time.perf_counter()
        import_results = []
        errors: list[str] = []

        # Find modules to test
        modules_to_test: dict[str, str | None] = {}

        if discovered_imports:
            for rec in discovered_imports:
                if rec.import_type == ImportType.THIRD_PARTY:
                    top_mod = rec.module_name.split(".")[0]
                    if top_mod and top_mod not in modules_to_test:
                        modules_to_test[top_mod] = rec.top_level_package

        # Also add direct packages from resolution result if not present
        if resolution_result and resolution_result.graph:
            for root_name in resolution_result.graph.roots:
                clean_name = root_name.replace("-", "_").lower()
                if clean_name not in modules_to_test:
                    modules_to_test[clean_name] = root_name

        if not modules_to_test:
            # Nothing to test
            return ValidationStageResult(
                stage=ValidationStage.IMPORT_TEST,
                status=ValidationStatus.SKIPPED,
                duration_seconds=0.0,
                logs="No external candidate imports found to test.",
            )

        all_passed = True
        log_lines: list[str] = []

        for mod_name, dist_name in sorted(modules_to_test.items()):
            res = runner.run_import_smoke_test(
                env_info=env_info,
                module_name=mod_name,
                distribution_name=dist_name,
                timeout=min(timeout, 30),
            )
            import_results.append(res)
            log_lines.append(f"Import {mod_name}: {res.status.value} ({res.duration_seconds}s)")

            if res.status != ValidationStatus.PASSED:
                all_passed = False
                err_msg = f"Failed to import '{mod_name}': {res.error_traceback or res.diagnostic}"
                errors.append(err_msg)
                log_lines.append(f"  {err_msg}")

        status = ValidationStatus.PASSED if all_passed else ValidationStatus.FAILED
        duration = round(time.perf_counter() - start_t, 3)
        return ValidationStageResult(
            stage=ValidationStage.IMPORT_TEST,
            status=status,
            duration_seconds=duration,
            import_results=import_results,
            errors=errors,
            logs="\n".join(log_lines),
        )

    def _execute_l3_project_tests(
        self,
        runner: ExecutionRunner,
        env_info: EnvironmentInfo,
        request: ValidationRequest,
    ) -> ValidationStageResult:
        """Run L3 project test suite if explicitly authorized."""
        start_t = time.perf_counter()

        if not request.allow_project_code:
            return ValidationStageResult(
                stage=ValidationStage.PROJECT_TEST,
                status=ValidationStatus.BLOCKED_BY_POLICY,
                duration_seconds=0.0,
                errors=[
                    "Project test execution requires explicit authorization (--allow-project-code)."
                ],
                logs="Skipped: Project test execution not authorized by user policy.",
            )

        res = runner.run_project_tests(
            env_info=env_info,
            project_path=request.project_path,
            command=request.project_test_command,
            timeout=request.timeout_seconds,
            network=request.network_policy,
        )

        duration = round(time.perf_counter() - start_t, 3)
        logs = f"=== STDOUT ===\n{res.stdout or ''}\n=== STDERR ===\n{res.stderr or ''}"

        return ValidationStageResult(
            stage=ValidationStage.PROJECT_TEST,
            status=res.status,
            duration_seconds=duration,
            test_result=res,
            errors=[res.error_message] if res.error_message else [],
            logs=logs,
        )

    def _select_runner(self, request: ValidationRequest) -> ExecutionRunner:
        """Instantiate the requested execution runner."""
        r_type = request.runner_type.lower()
        if r_type == "docker":
            return DockerRunner(
                memory_limit=request.memory_limit or "1g",
                cpu_limit=request.cpu_limit or "1.0",
            )
        if r_type == "remote":
            return RemoteRunner()
        return LocalRunner(allow_execution=request.allow_local_execution)

    def _build_dry_run_report(
        self,
        request: ValidationRequest,
        target: TargetEnvironment,
        isolation_level: str,
        resolution_result: ResolutionResult | None,
    ) -> ValidationReport:
        """Generate a simulation report of what validation would execute."""
        pkgs_to_install = []
        if resolution_result and resolution_result.graph:
            pkgs_to_install = sorted(
                f"{p.name}=={p.version}"
                for p in resolution_result.graph.packages.values()
                if p.version
            )

        plan: dict[str, Any] = {
            "target": target.platform_tag,
            "runner": request.runner_type,
            "isolation_level": isolation_level,
            "trust_policy": request.execution_policy.value,
            "network_policy": request.network_policy.value,
            "wheel_only": True,
            "allow_sdist": False,
            "packages_to_install": pkgs_to_install,
            "import_smoke_tests_enabled": request.level in ("imports", "project-tests"),
            "project_tests_enabled": request.level == "project-tests",
            "project_tests_authorized": request.allow_project_code,
            "test_command": request.project_test_command
            if request.level == "project-tests"
            else None,
            "timeout_seconds": request.timeout_seconds,
        }

        return ValidationReport(
            project_name=request.project_path.name,
            project_path=request.project_path,
            status=ValidationStatus.PASSED,
            target_environment=target,
            runner_type=request.runner_type,
            isolation_level=isolation_level,
            execution_policy=request.execution_policy,
            network_policy=request.network_policy,
            diagnostics=["Dry run simulated successfully. No code was executed."],
            cleanup_status="dry_run",
            dry_run_plan=plan,
        )
