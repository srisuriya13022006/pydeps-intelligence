"""Local subprocess execution runner for natively supported platforms."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path

from pydeps_intelligence.models.project import (
    Architecture,
    OperatingSystem,
    PythonImplementation,
    TargetEnvironment,
)
from pydeps_intelligence.models.validation import (
    EnvironmentInfo,
    ImportTestResult,
    NetworkPolicy,
    ProjectTestResult,
    RunnerCapabilities,
    ValidationStatus,
)
from pydeps_intelligence.validation.interpreter_discovery import InterpreterDiscovery
from pydeps_intelligence.validation.network_policy import NetworkPolicyController
from pydeps_intelligence.validation.runners.base import ExecutionRunner


class LocalRunner(ExecutionRunner):
    """Executes validation inside isolated local virtual environments."""

    def __init__(
        self,
        interpreter_discovery: InterpreterDiscovery | None = None,
        allow_execution: bool = False,
    ) -> None:
        self.discovery = interpreter_discovery or InterpreterDiscovery()
        self.allow_execution = allow_execution

    def get_capabilities(self) -> RunnerCapabilities:
        """Report host capabilities and discoverable Python interpreters."""
        host_os = self._detect_host_os()
        host_arch = self._detect_host_arch()

        discovered = self.discovery.discover_all()
        versions = sorted({f"{d.major}.{d.minor}" for d in discovered})
        impls = list({d.implementation for d in discovered}) or [PythonImplementation.CPYTHON]

        return RunnerCapabilities(
            runner_type="local",
            supported_operating_systems=[host_os],
            supported_architectures=[host_arch],
            supported_python_versions=versions,
            supported_implementations=impls,
            isolation_level="host_venv",
            supported_network_policies=[
                NetworkPolicy.DISABLED,
                NetworkPolicy.PACKAGE_DOWNLOAD_ONLY,
                NetworkPolicy.CONTROLLED,
                NetworkPolicy.UNRESTRICTED,
            ],
            is_available=True,
            unavailable_reason=None,
        )

    def can_execute(self, target: TargetEnvironment) -> tuple[bool, str | None]:
        """Verify whether target matches host platform and a compatible interpreter exists."""
        host_os = self._detect_host_os()
        if target.operating_system != host_os:
            msg = (
                f"Target OS '{target.operating_system.value}' cannot be executed "
                f"on local host '{host_os.value}'."
            )
            return (False, msg)

        host_arch = self._detect_host_arch()
        if target.architecture != host_arch:
            msg = (
                f"Target architecture '{target.architecture.value}' cannot be executed "
                f"on local host '{host_arch.value}'."
            )
            return (False, msg)

        interp = self.discovery.find_matching_interpreter(target)
        if not interp:
            msg = (
                f"No installed Python interpreter found for version {target.python_version} "
                f"({target.implementation.value})."
            )
            return (False, msg)

        return (True, None)

    def create_environment(
        self,
        target: TargetEnvironment,
        base_dir: Path,
        disposable: bool = True,
    ) -> EnvironmentInfo:
        """Create an isolated venv using the matching host interpreter."""
        interp = self.discovery.find_matching_interpreter(target)
        if not interp:
            raise RuntimeError(f"Cannot create environment: no interpreter for target {target}")

        ts = int(time.time() * 1000)
        env_dir = base_dir / f"venv_{target.operating_system.value}_{target.python_version}_{ts}"
        env_dir.mkdir(parents=True, exist_ok=True)

        # Create venv
        cmd = [str(interp.executable), "-m", "venv", "--clear", str(env_dir)]
        safe_env = NetworkPolicyController.get_safe_environment()
        res = subprocess.run(cmd, capture_output=True, text=True, env=safe_env, timeout=120)
        if res.returncode != 0:
            raise RuntimeError(f"Failed to create virtual environment: {res.stderr or res.stdout}")

        # Locate python binary
        py_bin = env_dir / (
            "Scripts/python.exe"
            if target.operating_system == OperatingSystem.WINDOWS
            else "bin/python"
        )
        if not py_bin.is_file():
            # Fallback check
            py_bin_alt = env_dir / "bin/python3"
            if py_bin_alt.is_file():
                py_bin = py_bin_alt
            else:
                raise FileNotFoundError(f"Python executable not found in created venv: {py_bin}")

        return EnvironmentInfo(
            environment_path=env_dir,
            python_executable=py_bin,
            python_version=interp.version_str,
            operating_system=target.operating_system,
            architecture=target.architecture,
            implementation=target.implementation,
            is_disposable=disposable,
        )

    def install_dependencies(
        self,
        env_info: EnvironmentInfo,
        requirements_file: Path | None = None,
        packages: list[str] | None = None,
        timeout: int = 300,
        network: NetworkPolicy = NetworkPolicy.PACKAGE_DOWNLOAD_ONLY,
        allow_sdist: bool = False,
    ) -> tuple[int, str, dict[str, str]]:
        """Install dependencies into the venv using pip."""
        cmd = [str(env_info.python_executable), "-m", "pip", "install", "--no-input"]

        if not allow_sdist:
            cmd.append("--only-binary=:all:")

        cmd.extend(NetworkPolicyController.get_pip_network_args(network))

        if requirements_file:
            cmd.extend(["-r", str(requirements_file)])
        elif packages:
            cmd.extend(packages)
        else:
            return (0, "No packages or requirements specified to install.", {})

        safe_env = NetworkPolicyController.get_safe_environment(
            {"VIRTUAL_ENV": str(env_info.environment_path)}
        )

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=safe_env,
                timeout=timeout,
            )
            raw_log = f"{res.stdout}\n{res.stderr}"
            sanitized = NetworkPolicyController.sanitize_log(raw_log)

            installed_inventory: dict[str, str] = {}
            if res.returncode == 0:
                installed_inventory = self._get_installed_inventory(env_info)

            return (res.returncode, sanitized, installed_inventory)
        except subprocess.TimeoutExpired:
            return (124, f"Installation timed out after {timeout} seconds.", {})
        except Exception as exc:
            return (1, f"Installation failed with unexpected error: {exc}", {})

    def run_pip_check(
        self,
        env_info: EnvironmentInfo,
        timeout: int = 60,
    ) -> tuple[int, str]:
        """Verify dependency consistency with pip check."""
        cmd = [str(env_info.python_executable), "-m", "pip", "check"]
        safe_env = NetworkPolicyController.get_safe_environment(
            {"VIRTUAL_ENV": str(env_info.environment_path)}
        )

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, env=safe_env, timeout=timeout)
            raw_log = f"{res.stdout}\n{res.stderr}"
            return (res.returncode, NetworkPolicyController.sanitize_log(raw_log))
        except subprocess.TimeoutExpired:
            return (124, f"pip check timed out after {timeout} seconds.")
        except Exception as exc:
            return (1, f"pip check execution error: {exc}")

    def run_import_smoke_test(
        self,
        env_info: EnvironmentInfo,
        module_name: str,
        distribution_name: str | None = None,
        timeout: int = 30,
    ) -> ImportTestResult:
        """Attempt to import a package in an isolated subprocess."""
        start_t = time.perf_counter()
        code = f"import {module_name}"
        cmd = [str(env_info.python_executable), "-c", code]
        safe_env = NetworkPolicyController.get_safe_environment(
            {"VIRTUAL_ENV": str(env_info.environment_path)}
        )

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, env=safe_env, timeout=timeout)
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

            # Classify failure
            diagnostic = "import_error"
            if "ModuleNotFoundError" in sanitized_stderr:
                diagnostic = "module_not_found"
            elif "ImportError" in sanitized_stderr:
                diagnostic = "import_error"

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
                error_traceback=f"Import test timed out after {timeout} seconds",
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
        """Run project tests in the environment."""
        start_t = time.perf_counter()

        # Prepend venv python if running a module (e.g. ['pytest'])
        cmd = list(command)
        if cmd and cmd[0] in ("pytest", "unittest", "python"):
            if cmd[0] in ("pytest", "unittest"):
                cmd = [str(env_info.python_executable), "-m", *cmd]
            elif cmd[0] == "python":
                cmd[0] = str(env_info.python_executable)

        # Enforce network isolation in local subprocess if disabled
        path_sep = ";" if platform.system() == "Windows" else ":"
        custom_path = f"{env_info.python_executable.parent}{path_sep}{os.environ.get('PATH', '')}"
        safe_env = NetworkPolicyController.get_safe_environment(
            {
                "VIRTUAL_ENV": str(env_info.environment_path),
                "PATH": custom_path,
            }
        )

        try:
            res = subprocess.run(
                cmd,
                cwd=str(project_path),
                capture_output=True,
                text=True,
                env=safe_env,
                timeout=timeout,
            )
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
                error_message=f"Project test execution timed out after {timeout} seconds",
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
        """Purge the disposable environment directory."""
        if not env_info.is_disposable or env_info.is_cleaned_up:
            return True

        path = env_info.environment_path
        if not path.exists():
            env_info.is_cleaned_up = True
            return True

        # Retry logic for Windows file locking
        for _ in range(3):
            try:
                shutil.rmtree(path, ignore_errors=False)
                env_info.is_cleaned_up = True
                return True
            except Exception:
                time.sleep(0.3)

        try:
            shutil.rmtree(path, ignore_errors=True)
            env_info.is_cleaned_up = True
            return True
        except Exception:
            return False

    def _get_installed_inventory(self, env_info: EnvironmentInfo) -> dict[str, str]:
        """Query installed packages using pip list --format=json."""
        cmd = [str(env_info.python_executable), "-m", "pip", "list", "--format=json"]
        safe_env = NetworkPolicyController.get_safe_environment(
            {"VIRTUAL_ENV": str(env_info.environment_path)}
        )
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, env=safe_env, timeout=30)
            if res.returncode == 0:
                data = json.loads(res.stdout)
                return {item["name"].lower(): item["version"] for item in data}
        except Exception:
            pass
        return {}

    @staticmethod
    def _detect_host_os() -> OperatingSystem:
        sys_os = platform.system().lower()
        if "windows" in sys_os or sys_os == "nt":
            return OperatingSystem.WINDOWS
        if "linux" in sys_os:
            return OperatingSystem.LINUX
        if "darwin" in sys_os:
            return OperatingSystem.MACOS
        return OperatingSystem.LINUX

    @staticmethod
    def _detect_host_arch() -> Architecture:
        machine = platform.machine().lower()
        if machine in ("amd64", "x86_64", "x64"):
            return Architecture.X86_64
        if machine in ("arm64", "aarch64"):
            return Architecture.ARM64
        if machine in ("x86", "i386", "i686"):
            return Architecture.X86
        return Architecture.X86_64
