"""Hardened Docker container runner for Linux target environments."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

from pydeps.models.project import (
    Architecture,
    OperatingSystem,
    PythonImplementation,
    TargetEnvironment,
)
from pydeps.models.validation import (
    EnvironmentInfo,
    ImportTestResult,
    NetworkPolicy,
    ProjectTestResult,
    RunnerCapabilities,
    ValidationStatus,
)
from pydeps.validation.network_policy import NetworkPolicyController
from pydeps.validation.runners.base import ExecutionRunner


class DockerRunner(ExecutionRunner):
    """Executes validation inside isolated, hardened Linux Docker containers."""

    def __init__(
        self,
        docker_executable: str = "docker",
        memory_limit: str = "1g",
        cpu_limit: str = "1.0",
        pids_limit: int = 100,
    ) -> None:
        self.docker_bin = docker_executable
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self.pids_limit = pids_limit
        self._available: bool | None = None
        self._availability_reason: str | None = None

    def is_docker_available(self) -> tuple[bool, str | None]:
        """Verify that docker CLI is on PATH and the daemon is reachable."""
        if self._available is not None:
            return (self._available, self._availability_reason)

        if not shutil.which(self.docker_bin):
            self._available = False
            self._availability_reason = "Docker executable is not found on PATH."
            return (False, self._availability_reason)

        try:
            res = subprocess.run(
                [self.docker_bin, "info"],
                capture_output=True,
                text=True,
                timeout=10,
                shell=False,
            )
            if res.returncode != 0:
                self._available = False
                self._availability_reason = (
                    f"Docker daemon is not responding: {res.stderr.strip() or res.stdout.strip()}"
                )
                return (False, self._availability_reason)

            self._available = True
            self._availability_reason = None
            return (True, None)
        except subprocess.TimeoutExpired:
            self._available = False
            self._availability_reason = "Docker daemon check timed out after 10 seconds."
            return (False, self._availability_reason)
        except Exception as exc:
            self._available = False
            self._availability_reason = f"Docker check failed: {exc}"
            return (False, self._availability_reason)

    def get_capabilities(self) -> RunnerCapabilities:
        """Report container capabilities and isolation characteristics."""
        avail, reason = self.is_docker_available()
        return RunnerCapabilities(
            runner_type="docker",
            supported_operating_systems=[OperatingSystem.LINUX],
            supported_architectures=[Architecture.X86_64, Architecture.ARM64],
            supported_python_versions=["3.9", "3.10", "3.11", "3.12", "3.13", "3.14"],
            supported_implementations=[PythonImplementation.CPYTHON, PythonImplementation.PYPY],
            isolation_level="hardened_container",
            supported_network_policies=[
                NetworkPolicy.DISABLED,
                NetworkPolicy.PACKAGE_DOWNLOAD_ONLY,
                NetworkPolicy.CONTROLLED,
                NetworkPolicy.UNRESTRICTED,
            ],
            is_available=avail,
            unavailable_reason=reason,
        )

    def can_execute(self, target: TargetEnvironment) -> tuple[bool, str | None]:
        """Ensure target is Linux and Docker is operational."""
        if target.operating_system != OperatingSystem.LINUX:
            msg = (
                "Docker runner only supports Linux target environments. "
                f"Cannot validate {target.operating_system.value} target."
            )
            return (False, msg)

        avail, reason = self.is_docker_available()
        if not avail:
            return (False, f"Docker runner unavailable: {reason}")

        return (True, None)

    def create_environment(
        self,
        target: TargetEnvironment,
        base_dir: Path,
        disposable: bool = True,
    ) -> EnvironmentInfo:
        """Initialize workspace directory for the container environment."""
        can_run, reason = self.can_execute(target)
        if not can_run:
            raise RuntimeError(f"Cannot create Docker environment: {reason}")

        env_dir = base_dir / f"docker_env_{target.python_version}_{int(time.time() * 1000)}"
        env_dir.mkdir(parents=True, exist_ok=True)

        return EnvironmentInfo(
            environment_path=env_dir,
            python_executable=Path("python3"),
            python_version=target.python_version,
            operating_system=target.operating_system,
            architecture=target.architecture,
            implementation=target.implementation,
            is_disposable=disposable,
        )

    def _build_hardened_run_args(
        self,
        target: TargetEnvironment,
        network: NetworkPolicy,
        project_path: Path | None = None,
        env_dir: Path | None = None,
    ) -> list[str]:
        """Construct secure, hardened docker execution arguments."""
        image = f"python:{target.python_version}-slim"

        args = [
            self.docker_bin,
            "run",
            "--rm",
            "--security-opt=no-new-privileges",
            "--cap-drop=ALL",
            "--pids-limit",
            str(self.pids_limit),
            "--memory",
            self.memory_limit,
            "--cpus",
            self.cpu_limit,
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=512m",
        ]

        # Network enforcement
        if network == NetworkPolicy.DISABLED:
            args.extend(["--network", "none"])

        # Read-only source mounting
        if project_path:
            clean_proj = str(project_path.resolve()).replace("\\", "/")
            args.extend(["-v", f"{clean_proj}:/workspace:ro", "-w", "/workspace"])

        # Read-write isolated environment directory
        if env_dir:
            clean_env = str(env_dir.resolve()).replace("\\", "/")
            args.extend(["-v", f"{clean_env}:/env:rw"])

        args.append(image)
        return args

    def install_dependencies(
        self,
        env_info: EnvironmentInfo,
        requirements_file: Path | None = None,
        packages: list[str] | None = None,
        timeout: int = 300,
        network: NetworkPolicy = NetworkPolicy.PACKAGE_DOWNLOAD_ONLY,
        allow_sdist: bool = False,
    ) -> tuple[int, str, dict[str, str]]:
        """Install dependencies inside a container and copy/record inventory."""
        target = TargetEnvironment(
            python_version=env_info.python_version,
            operating_system=env_info.operating_system,
            architecture=env_info.architecture,
            implementation=env_info.implementation,
        )

        base_args = self._build_hardened_run_args(
            target=target,
            network=network,
            env_dir=env_info.environment_path,
        )

        install_cmd = ["pip", "install", "--no-input"]
        if not allow_sdist:
            install_cmd.append("--only-binary=:all:")

        install_cmd.extend(NetworkPolicyController.get_pip_network_args(network))

        if requirements_file:
            req_name = requirements_file.name
            dest_req = env_info.environment_path / req_name
            shutil.copy2(requirements_file, dest_req)
            install_cmd.extend(["-r", f"/env/{req_name}"])
        elif packages:
            install_cmd.extend(packages)
        else:
            return (0, "No packages to install.", {})

        # Query installed json after install
        full_sh_cmd = " ".join(install_cmd) + " && pip list --format=json > /env/installed.json"
        exec_cmd = [*base_args, "sh", "-c", full_sh_cmd]

        try:
            res = subprocess.run(
                exec_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
            )
            sanitized = NetworkPolicyController.sanitize_log(f"{res.stdout}\n{res.stderr}")

            inventory: dict[str, str] = {}
            installed_json_path = env_info.environment_path / "installed.json"
            if installed_json_path.is_file():
                try:
                    data = json.loads(installed_json_path.read_text(encoding="utf-8"))
                    inventory = {item["name"].lower(): item["version"] for item in data}
                except Exception:
                    pass

            return (res.returncode, sanitized, inventory)
        except subprocess.TimeoutExpired:
            return (124, f"Docker container installation timed out after {timeout} seconds.", {})
        except Exception as exc:
            return (1, f"Docker container execution failed: {exc}", {})

    def run_pip_check(
        self,
        env_info: EnvironmentInfo,
        timeout: int = 60,
    ) -> tuple[int, str]:
        """Run pip check inside the container environment."""
        target = TargetEnvironment(
            python_version=env_info.python_version,
            operating_system=env_info.operating_system,
            architecture=env_info.architecture,
            implementation=env_info.implementation,
        )
        base_args = self._build_hardened_run_args(
            target=target,
            network=NetworkPolicy.DISABLED,
            env_dir=env_info.environment_path,
        )
        cmd = [*base_args, "pip", "check"]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=False)
            return (
                res.returncode,
                NetworkPolicyController.sanitize_log(f"{res.stdout}\n{res.stderr}"),
            )
        except subprocess.TimeoutExpired:
            return (124, f"Container pip check timed out after {timeout} seconds.")
        except Exception as exc:
            return (1, f"Container pip check error: {exc}")

    def run_import_smoke_test(
        self,
        env_info: EnvironmentInfo,
        module_name: str,
        distribution_name: str | None = None,
        timeout: int = 30,
    ) -> ImportTestResult:
        """Run isolated import smoke test in a container."""
        start_t = time.perf_counter()
        target = TargetEnvironment(
            python_version=env_info.python_version,
            operating_system=env_info.operating_system,
            architecture=env_info.architecture,
            implementation=env_info.implementation,
        )
        base_args = self._build_hardened_run_args(
            target=target,
            network=NetworkPolicy.DISABLED,
            env_dir=env_info.environment_path,
        )
        code = f"import {module_name}"
        cmd = [*base_args, "python3", "-c", code]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=False)
            duration = round(time.perf_counter() - start_t, 3)
            sanitized_stdout = NetworkPolicyController.sanitize_log(res.stdout)
            sanitized_stderr = NetworkPolicyController.sanitize_log(res.stderr)

            if res.returncode == 0:
                return ImportTestResult(
                    module_name=module_name,
                    distribution_name=distribution_name,
                    status=ValidationStatus.PASSED,
                    exit_code=0,
                    duration_seconds=duration,
                    stdout=sanitized_stdout,
                    stderr=sanitized_stderr,
                )

            diagnostic = "import_error"
            if "ModuleNotFoundError" in sanitized_stderr:
                diagnostic = "module_not_found"

            return ImportTestResult(
                module_name=module_name,
                distribution_name=distribution_name,
                status=ValidationStatus.FAILED,
                exit_code=res.returncode,
                duration_seconds=duration,
                error_traceback=sanitized_stderr,
                stdout=sanitized_stdout,
                stderr=sanitized_stderr,
                diagnostic=diagnostic,
            )
        except subprocess.TimeoutExpired:
            duration = round(time.perf_counter() - start_t, 3)
            return ImportTestResult(
                module_name=module_name,
                distribution_name=distribution_name,
                status=ValidationStatus.TIMED_OUT,
                exit_code=124,
                duration_seconds=duration,
                error_traceback=f"Container import test timed out after {timeout} seconds",
                diagnostic="timed_out",
            )
        except Exception as exc:
            duration = round(time.perf_counter() - start_t, 3)
            return ImportTestResult(
                module_name=module_name,
                distribution_name=distribution_name,
                status=ValidationStatus.FAILED,
                exit_code=1,
                duration_seconds=duration,
                error_traceback=str(exc),
                diagnostic="system_error",
            )

    def run_project_tests(
        self,
        env_info: EnvironmentInfo,
        project_path: Path,
        command: list[str],
        timeout: int = 300,
        network: NetworkPolicy = NetworkPolicy.DISABLED,
    ) -> ProjectTestResult:
        """Execute project tests inside the hardened container with read-only project mount."""
        start_t = time.perf_counter()
        target = TargetEnvironment(
            python_version=env_info.python_version,
            operating_system=env_info.operating_system,
            architecture=env_info.architecture,
            implementation=env_info.implementation,
        )
        base_args = self._build_hardened_run_args(
            target=target,
            network=network,
            project_path=project_path,
            env_dir=env_info.environment_path,
        )
        cmd = [*base_args, *command]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=False)
            duration = round(time.perf_counter() - start_t, 3)
            sanitized_stdout = NetworkPolicyController.sanitize_log(res.stdout)
            sanitized_stderr = NetworkPolicyController.sanitize_log(res.stderr)

            status = ValidationStatus.PASSED if res.returncode == 0 else ValidationStatus.FAILED
            return ProjectTestResult(
                command=command,
                status=status,
                exit_code=res.returncode,
                duration_seconds=duration,
                stdout=sanitized_stdout,
                stderr=sanitized_stderr,
                error_message=None
                if res.returncode == 0
                else f"Test run exited with code {res.returncode}",
            )
        except subprocess.TimeoutExpired:
            duration = round(time.perf_counter() - start_t, 3)
            return ProjectTestResult(
                command=command,
                status=ValidationStatus.TIMED_OUT,
                exit_code=124,
                duration_seconds=duration,
                error_message=f"Project test run timed out after {timeout} seconds",
            )
        except Exception as exc:
            duration = round(time.perf_counter() - start_t, 3)
            return ProjectTestResult(
                command=command,
                status=ValidationStatus.FAILED,
                exit_code=1,
                duration_seconds=duration,
                error_message=f"Project test runner failed: {exc}",
            )

    def cleanup_environment(self, env_info: EnvironmentInfo) -> bool:
        """Purge temporary container working directory."""
        if not env_info.is_disposable or env_info.is_cleaned_up:
            return True

        path = env_info.environment_path
        if not path.exists():
            env_info.is_cleaned_up = True
            return True

        try:
            shutil.rmtree(path, ignore_errors=True)
            env_info.is_cleaned_up = True
            return True
        except Exception:
            return False
