"""Abstract base interface and protocols for execution runners."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pydeps.models.project import TargetEnvironment
from pydeps.models.validation import (
    EnvironmentInfo,
    ImportTestResult,
    NetworkPolicy,
    ProjectTestResult,
    RunnerCapabilities,
)


class ExecutionRunner(ABC):
    """Abstract contract for an environment execution runner."""

    @abstractmethod
    def get_capabilities(self) -> RunnerCapabilities:
        """Report runner capabilities, supported targets, and availability status."""
        ...

    @abstractmethod
    def can_execute(self, target: TargetEnvironment) -> tuple[bool, str | None]:
        """Check whether the runner can execute in the requested target environment.

        Returns (can_run, reason_if_cannot).
        """
        ...

    @abstractmethod
    def create_environment(
        self,
        target: TargetEnvironment,
        base_dir: Path,
        disposable: bool = True,
    ) -> EnvironmentInfo:
        """Create an isolated, disposable execution environment matching the target."""
        ...

    @abstractmethod
    def install_dependencies(
        self,
        env_info: EnvironmentInfo,
        requirements_file: Path | None = None,
        packages: list[str] | None = None,
        timeout: int = 300,
        network: NetworkPolicy = NetworkPolicy.PACKAGE_DOWNLOAD_ONLY,
        allow_sdist: bool = False,
    ) -> tuple[int, str, dict[str, str]]:
        """Install resolved dependencies into the environment.

        Returns (exit_code, log_output, installed_packages_inventory).
        """
        ...

    @abstractmethod
    def run_pip_check(
        self,
        env_info: EnvironmentInfo,
        timeout: int = 60,
    ) -> tuple[int, str]:
        """Run pip check or equivalent dependency consistency check.

        Returns (exit_code, output_log).
        """
        ...

    @abstractmethod
    def run_import_smoke_test(
        self,
        env_info: EnvironmentInfo,
        module_name: str,
        distribution_name: str | None = None,
        timeout: int = 30,
    ) -> ImportTestResult:
        """Execute a smoke test importing a single module in an isolated subprocess."""
        ...

    @abstractmethod
    def run_project_tests(
        self,
        env_info: EnvironmentInfo,
        project_path: Path,
        command: list[str],
        timeout: int = 300,
        network: NetworkPolicy = NetworkPolicy.DISABLED,
    ) -> ProjectTestResult:
        """Execute user-authorized project tests in the environment."""
        ...

    @abstractmethod
    def cleanup_environment(self, env_info: EnvironmentInfo) -> bool:
        """Tear down and purge the disposable environment."""
        ...
