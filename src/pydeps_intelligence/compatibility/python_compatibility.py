"""Python version compatibility evaluator using packaging SpecifierSet."""

from __future__ import annotations

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from pydeps_intelligence.models.compatibility import CompatibilityStatus


class PythonVersionEvaluation:
    """Detailed evaluation result for Python version constraints."""

    def __init__(
        self,
        status: CompatibilityStatus,
        target_version: str,
        requires_python: str | None,
        reason: str,
        is_compatible: bool | None,
        diagnostic: str | None = None,
    ) -> None:
        self.status = status
        self.target_version = target_version
        self.requires_python = requires_python
        self.reason = reason
        self.is_compatible = is_compatible
        self.diagnostic = diagnostic

    def __repr__(self) -> str:
        return (
            f"PythonVersionEvaluation(status={self.status.value}, "
            f"target={self.target_version}, requires={self.requires_python})"
        )


def evaluate_python_version(
    requires_python: str | None,
    target_python_version: str | Version,
    prereleases: bool = True,
) -> PythonVersionEvaluation:
    """Evaluate a Requires-Python constraint string against a target Python version.

    Missing metadata is explicitly treated as UNVERIFIED rather than assumed compatible.
    """
    # 1. Parse target version
    if isinstance(target_python_version, Version):
        target_ver = target_python_version
        target_str = str(target_ver)
    else:
        target_str = str(target_python_version).strip()
        try:
            target_ver = Version(target_str)
        except InvalidVersion as exc:
            return PythonVersionEvaluation(
                status=CompatibilityStatus.UNVERIFIED,
                target_version=target_str,
                requires_python=requires_python,
                reason=f"Target Python version '{target_str}' is invalid: {exc}",
                is_compatible=None,
                diagnostic=f"Invalid target Python version '{target_str}'",
            )

    # 2. Check for missing Requires-Python metadata
    if requires_python is None or not str(requires_python).strip():
        return PythonVersionEvaluation(
            status=CompatibilityStatus.UNVERIFIED,
            target_version=target_str,
            requires_python=None,
            reason="No Requires-Python specifier declared in release metadata.",
            is_compatible=None,
            diagnostic="Missing Requires-Python metadata; compatibility unverified statically.",
        )

    clean_spec = str(requires_python).strip()

    # 3. Parse SpecifierSet
    try:
        spec_set = SpecifierSet(clean_spec, prereleases=prereleases)
    except InvalidSpecifier as exc:
        return PythonVersionEvaluation(
            status=CompatibilityStatus.UNVERIFIED,
            target_version=target_str,
            requires_python=clean_spec,
            reason=f"Malformed Requires-Python constraint in metadata: '{clean_spec}' ({exc})",
            is_compatible=None,
            diagnostic=f"Invalid Requires-Python specifier '{clean_spec}'",
        )

    # 4. Check membership
    try:
        is_match = spec_set.contains(target_ver, prereleases=prereleases)
    except Exception as exc:
        return PythonVersionEvaluation(
            status=CompatibilityStatus.UNVERIFIED,
            target_version=target_str,
            requires_python=clean_spec,
            reason=(
                f"Error evaluating Python specifier '{clean_spec}' against '{target_str}': {exc}"
            ),
            is_compatible=None,
            diagnostic=str(exc),
        )

    if is_match:
        return PythonVersionEvaluation(
            status=CompatibilityStatus.COMPATIBLE,
            target_version=target_str,
            requires_python=clean_spec,
            reason=f"Target Python {target_str} satisfies constraint '{clean_spec}'.",
            is_compatible=True,
            diagnostic=None,
        )
    else:
        return PythonVersionEvaluation(
            status=CompatibilityStatus.INCOMPATIBLE,
            target_version=target_str,
            requires_python=clean_spec,
            reason=f"Target Python {target_str} does not satisfy constraint '{clean_spec}'.",
            is_compatible=False,
            diagnostic=None,
        )
