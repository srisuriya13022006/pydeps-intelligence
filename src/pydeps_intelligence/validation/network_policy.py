"""Network policy enforcement, environment variable filtering, and log credential sanitization."""

from __future__ import annotations

import os
import re

from pydeps_intelligence.models.validation import NetworkPolicy

SAFE_ENV_ALLOWLIST = {
    # System execution fundamentals
    "PATH",
    "SYSTEMROOT",
    "SYSTEMDRIVE",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
    "TEMP",
    "TMP",
    "TMPDIR",
    "USERPROFILE",
    "HOME",
    "TERM",
    "LANG",
    "LC_ALL",
    "TZ",
    # Python runtime variables
    "PYTHONIOENCODING",
    "PYTHONUNBUFFERED",
    "PYTHONUTF8",
    "PYTHONWARNINGS",
    "VIRTUAL_ENV",
}

# Redaction patterns for logs
SECRET_PATTERNS = [
    # Basic auth in URLs: https://user:pass@host
    (re.compile(r"://([^:/@\s]+):([^@\s]+)@"), r"://\1:[REDACTED]@"),
    # Bearer / token authentication headers
    (re.compile(r"(?i)(authorization:\s*(?:bearer|token)\s+)[^\s\r\n]+"), r"\1[REDACTED]"),
    # PyPI upload / download tokens (pypi-AgEI...)
    (re.compile(r"pypi-[A-Za-z0-9_\-]{40,}"), "pypi-[REDACTED]"),
    # GitHub personal access tokens
    (re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,}"), "gh_[REDACTED]"),
    # Generic api keys or password assignments in key=value pairs
    (
        re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*=\s*['\"]?[^\s'\",]+['\"]?"),
        r"\1=[REDACTED]",
    ),
]


class NetworkPolicyController:
    """Controls network permissions, environment variable sanitation, and credential redaction."""

    @staticmethod
    def get_safe_environment(
        extra_vars: dict[str, str] | None = None,
        custom_allowlist: set[str] | None = None,
    ) -> dict[str, str]:
        """Construct an isolated environment dict inheriting only allowlisted host variables."""
        allowlist = (custom_allowlist or set()) | SAFE_ENV_ALLOWLIST
        clean_env: dict[str, str] = {}

        for key, val in os.environ.items():
            if key.upper() in allowlist:
                clean_env[key] = val

        if extra_vars:
            for k, v in extra_vars.items():
                clean_env[k] = v

        return clean_env

    @staticmethod
    def sanitize_log(text: str | None) -> str:
        """Redact tokens, credentials, and basic-auth credentials from logs."""
        if not text:
            return ""

        redacted = text
        for pattern, replacement in SECRET_PATTERNS:
            redacted = pattern.sub(replacement, redacted)

        return redacted

    @staticmethod
    def get_pip_network_args(policy: NetworkPolicy) -> list[str]:
        """Return CLI arguments enforcing the given network policy for pip commands."""
        if policy == NetworkPolicy.DISABLED:
            return ["--no-index"]
        if policy == NetworkPolicy.PACKAGE_DOWNLOAD_ONLY:
            return []
        if policy == NetworkPolicy.CONTROLLED:
            return ["--timeout", "15", "--retries", "1"]
        return []
