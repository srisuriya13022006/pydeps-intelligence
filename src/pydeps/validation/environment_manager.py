"""Disposable environment lifecycle management and isolation tracking."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from pydeps.models.project import TargetEnvironment
from pydeps.models.validation import EnvironmentInfo
from pydeps.validation.runners.base import ExecutionRunner


class EnvironmentManager:
    """Manages the creation, tracking, and teardown of disposable validation environments."""

    def __init__(self, base_scratch_dir: Path | str | None = None) -> None:
        self.base_scratch_dir = (
            Path(base_scratch_dir)
            if base_scratch_dir
            else Path(tempfile.gettempdir()) / "pydeps_val"
        )
        self.base_scratch_dir.mkdir(parents=True, exist_ok=True)
        self._active_environments: list[tuple[ExecutionRunner, EnvironmentInfo]] = []

    def create_disposable_environment(
        self,
        runner: ExecutionRunner,
        target: TargetEnvironment,
        keep: bool = False,
    ) -> EnvironmentInfo:
        """Provision a clean, isolated environment using the given execution runner."""
        can_run, reason = runner.can_execute(target)
        if not can_run:
            raise RuntimeError(f"Runner cannot execute requested target: {reason}")

        env_info = runner.create_environment(
            target=target,
            base_dir=self.base_scratch_dir,
            disposable=not keep,
        )
        self._active_environments.append((runner, env_info))
        return env_info

    def cleanup_environment(self, runner: ExecutionRunner, env_info: EnvironmentInfo) -> bool:
        """Purge an individual environment if disposable."""
        success = runner.cleanup_environment(env_info)
        # Remove from active tracking if cleaned
        self._active_environments = [
            (r, e)
            for (r, e) in self._active_environments
            if e.environment_path != env_info.environment_path
        ]
        return success

    def cleanup_all(self) -> None:
        """Purge all tracked environments."""
        for runner, env_info in list(self._active_environments):
            if env_info.is_disposable and not env_info.is_cleaned_up:
                runner.cleanup_environment(env_info)
        self._active_environments.clear()

    def __enter__(self) -> EnvironmentManager:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.cleanup_all()
