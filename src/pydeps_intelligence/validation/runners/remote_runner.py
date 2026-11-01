"""Remote CI runner interface for cloud/native CI execution."""

from __future__ import annotations

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
from pydeps_intelligence.validation.runners.base import ExecutionRunner


class RemoteRunner(ExecutionRunner):
    """Interface for dispatching runtime validation to remote native CI runners."""

    def __init__(self, provider: str | None = None, api_endpoint: str | None = None) -> None:
        self.provider = provider
        self.api_endpoint = api_endpoint

    def get_capabilities(self) -> RunnerCapabilities:
        """Report remote CI execution capabilities."""
        is_configured = bool(self.provider and self.api_endpoint)
        reason = (
            None
            if is_configured
            else "Remote runner provider is not configured. Real CI execution integration required."
        )

        return RunnerCapabilities(
            runner_type="remote",
            supported_operating_systems=[
                OperatingSystem.LINUX,
                OperatingSystem.WINDOWS,
                OperatingSystem.MACOS,
            ],
            supported_architectures=[Architecture.X86_64, Architecture.ARM64],
            supported_python_versions=["3.9", "3.10", "3.11", "3.12", "3.13", "3.14"],
            supported_implementations=[PythonImplementation.CPYTHON, PythonImplementation.PYPY],
            isolation_level="remote_ci_worker",
            supported_network_policies=[
                NetworkPolicy.DISABLED,
                NetworkPolicy.CONTROLLED,
                NetworkPolicy.UNRESTRICTED,
            ],
            is_available=is_configured,
            unavailable_reason=reason,
        )

    def can_execute(self, target: TargetEnvironment) -> tuple[bool, str | None]:
        """Check if remote provider is configured to run."""
        caps = self.get_capabilities()
        if not caps.is_available:
            return (False, caps.unavailable_reason)
        return (True, None)

    def create_environment(
        self,
        target: TargetEnvironment,
        base_dir: Path,
        disposable: bool = True,
    ) -> EnvironmentInfo:
        raise NotImplementedError("Remote execution provider is not configured.")

    def install_dependencies(
        self,
        env_info: EnvironmentInfo,
        requirements_file: Path | None = None,
        packages: list[str] | None = None,
        timeout: int = 300,
        network: NetworkPolicy = NetworkPolicy.PACKAGE_DOWNLOAD_ONLY,
        allow_sdist: bool = False,
    ) -> tuple[int, str, dict[str, str]]:
        raise NotImplementedError("Remote execution provider is not configured.")

    def run_pip_check(
        self,
        env_info: EnvironmentInfo,
        timeout: int = 60,
    ) -> tuple[int, str]:
        raise NotImplementedError("Remote execution provider is not configured.")

    def run_import_smoke_test(
        self,
        env_info: EnvironmentInfo,
        module_name: str,
        distribution_name: str | None = None,
        timeout: int = 30,
    ) -> ImportTestResult:
        return ImportTestResult(
            module_name=module_name,
            distribution_name=distribution_name,
            status=ValidationStatus.UNSUPPORTED,
            diagnostic="remote_runner_not_configured",
        )

    def run_project_tests(
        self,
        env_info: EnvironmentInfo,
        project_path: Path,
        command: list[str],
        timeout: int = 300,
        network: NetworkPolicy = NetworkPolicy.DISABLED,
    ) -> ProjectTestResult:
        return ProjectTestResult(
            command=command,
            status=ValidationStatus.UNSUPPORTED,
            error_message="Remote execution provider is not configured.",
        )

    def cleanup_environment(self, env_info: EnvironmentInfo) -> bool:
        return True
