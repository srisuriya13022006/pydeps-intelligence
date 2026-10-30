"""Classification package for categorizing standard-library and project-local modules."""

from pydeps.classifier.local import LocalModuleDetector
from pydeps.classifier.stdlib import BASE_STDLIB_MODULES, StdlibCatalog

__all__ = ["BASE_STDLIB_MODULES", "LocalModuleDetector", "StdlibCatalog"]
