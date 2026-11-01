"""Classification package for categorizing standard-library and project-local modules."""

from pydeps_intelligence.classifier.local import LocalModuleDetector
from pydeps_intelligence.classifier.stdlib import BASE_STDLIB_MODULES, StdlibCatalog

__all__ = ["BASE_STDLIB_MODULES", "LocalModuleDetector", "StdlibCatalog"]
