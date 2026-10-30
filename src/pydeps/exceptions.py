"""PyDeps exception hierarchy.

All custom exceptions raised by PyDeps inherit from PyDepsError.
"""

from __future__ import annotations


class PyDepsError(Exception):
    """Base exception for all PyDeps errors."""

    def __init__(self, message: str, *args: object) -> None:
        self.message = message
        super().__init__(message, *args)


class ConfigError(PyDepsError):
    """Raised when project configuration is missing, malformed, or invalid."""


class TargetEnvironmentError(PyDepsError):
    """Raised when a target environment specification is unsupported or invalid."""


class ResolutionError(PyDepsError):
    """Raised when dependency resolution fails or encounters unsolvable conflicts."""


class CompatibilityError(PyDepsError):
    """Raised when compatibility analysis cannot be evaluated or encounters invalid input."""


class EnvironmentValidationError(PyDepsError):
    """Raised when isolated runtime environment validation encounters a failure."""
