"""Wheel compatibility evaluation using packaging tags and wheel filename parsing."""

from __future__ import annotations

from packaging.tags import Tag
from packaging.utils import InvalidWheelFilename, parse_wheel_filename
from packaging.version import Version

from pydeps_intelligence.compatibility.python_compatibility import evaluate_python_version


class WheelEvaluation:
    """Evaluation result for an individual wheel archive against a target platform."""

    def __init__(
        self,
        filename: str,
        is_compatible: bool,
        matching_tags: list[Tag],
        wheel_tags: list[Tag],
        reason: str,
        requires_python_compatible: bool | None = None,
        is_invalid: bool = False,
    ) -> None:
        self.filename = filename
        self.is_compatible = is_compatible
        self.matching_tags = matching_tags
        self.wheel_tags = wheel_tags
        self.reason = reason
        self.requires_python_compatible = requires_python_compatible
        self.is_invalid = is_invalid

    def __repr__(self) -> str:
        return f"WheelEvaluation(filename={self.filename}, compatible={self.is_compatible})"


def evaluate_wheel_filename(
    filename: str,
    supported_tags: frozenset[Tag] | set[Tag],
    target_python_version: str | Version | None = None,
    artifact_requires_python: str | None = None,
) -> WheelEvaluation:
    """Evaluate if wheel filename is compatible with target supported tags and constraints."""
    clean_name = filename.strip()

    # 1. Parse wheel filename
    try:
        _, _, _, tags = parse_wheel_filename(clean_name)
    except InvalidWheelFilename as exc:
        return WheelEvaluation(
            filename=clean_name,
            is_compatible=False,
            matching_tags=[],
            wheel_tags=[],
            reason=f"Invalid wheel filename syntax: {exc}",
            requires_python_compatible=None,
            is_invalid=True,
        )

    wheel_tags_list = sorted(list(tags), key=str)

    # 2. Check tag intersection with target-supported tags
    matching = tags.intersection(supported_tags)
    matching_list = sorted(list(matching), key=str)

    if not matching:
        return WheelEvaluation(
            filename=clean_name,
            is_compatible=False,
            matching_tags=[],
            wheel_tags=wheel_tags_list,
            reason=f"No wheel tags match target platform tags: {clean_name}",
            requires_python_compatible=None,
            is_invalid=False,
        )

    # 3. Check artifact-level requires_python if present
    py_compat = True
    if artifact_requires_python and target_python_version:
        py_eval = evaluate_python_version(artifact_requires_python, target_python_version)
        py_compat = bool(py_eval.is_compatible)
        if not py_compat:
            return WheelEvaluation(
                filename=clean_name,
                is_compatible=False,
                matching_tags=matching_list,
                wheel_tags=wheel_tags_list,
                reason=(
                    f"Wheel platform tags match, but constraint '{artifact_requires_python}' "
                    f"is not satisfied by target Python {target_python_version}."
                ),
                requires_python_compatible=False,
                is_invalid=False,
            )

    matched_str = ", ".join(str(t) for t in matching_list[:3])
    return WheelEvaluation(
        filename=clean_name,
        is_compatible=True,
        matching_tags=matching_list,
        wheel_tags=wheel_tags_list,
        reason=f"Wheel is compatible; matching tag(s): {matched_str}",
        requires_python_compatible=py_compat,
        is_invalid=False,
    )
