"""Global pytest fixtures and environment configuration."""

from __future__ import annotations

import os

# Disable ANSI coloring and interactive pagers during automated test runs
os.environ["NO_COLOR"] = "1"
os.environ["TERM"] = "dumb"
