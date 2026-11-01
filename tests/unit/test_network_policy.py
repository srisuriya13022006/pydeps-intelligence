"""Unit tests for NetworkPolicyController, safe environments, and credential sanitization."""

from __future__ import annotations

from pydeps_intelligence.models.validation import NetworkPolicy
from pydeps_intelligence.validation.network_policy import NetworkPolicyController


def test_safe_environment_strips_sensitive_variables(monkeypatch) -> None:
    """Safe environment must strip unallowlisted secret tokens and API keys."""
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "super_secret_aws_key_12345")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_1234567890abcdef1234567890abcdef12")
    monkeypatch.setenv("PYPI_PASSWORD", "pypi-AgEI1234567890123456789012345678901234567890")
    monkeypatch.setenv("CUSTOM_UNTRACKED_KEY", "should_not_leak")

    safe_env = NetworkPolicyController.get_safe_environment()
    assert "AWS_SECRET_ACCESS_KEY" not in safe_env
    assert "GITHUB_TOKEN" not in safe_env
    assert "PYPI_PASSWORD" not in safe_env
    assert "CUSTOM_UNTRACKED_KEY" not in safe_env
    assert "PATH" in safe_env


def test_sanitize_log_basic_auth() -> None:
    """Sanitizer must redact passwords embedded in URLs."""
    raw = "Downloading from https://myuser:secretpassword123@pypi.company.internal/simple/mypackage"
    sanitized = NetworkPolicyController.sanitize_log(raw)
    assert "secretpassword123" not in sanitized
    assert "https://myuser:[REDACTED]@pypi.company.internal" in sanitized


def test_sanitize_log_pypi_and_github_tokens() -> None:
    """Sanitizer must redact PyPI and GitHub personal access tokens."""
    raw = (
        "Token: pypi-AgEIBAAA1234567890abcdef1234567890abcdef1234567890 and "
        "GH: ghp_abcdef1234567890abcdef1234567890abcdef"
    )
    sanitized = NetworkPolicyController.sanitize_log(raw)
    assert "pypi-[REDACTED]" in sanitized
    assert "gh_[REDACTED]" in sanitized


def test_pip_network_args_policy() -> None:
    """Verify correct pip arguments for each network policy."""
    assert NetworkPolicyController.get_pip_network_args(NetworkPolicy.DISABLED) == ["--no-index"]
    assert NetworkPolicyController.get_pip_network_args(NetworkPolicy.PACKAGE_DOWNLOAD_ONLY) == []
    assert "--timeout" in NetworkPolicyController.get_pip_network_args(NetworkPolicy.CONTROLLED)
