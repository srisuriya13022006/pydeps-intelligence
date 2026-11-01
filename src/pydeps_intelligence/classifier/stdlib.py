"""Target-version aware Python Standard Library Catalog."""

from __future__ import annotations

import sys
from collections.abc import Mapping

# Base standard library modules available across Python 3.7+
BASE_STDLIB_MODULES: frozenset[str] = frozenset(
    {
        "__future__",
        "abc",
        "aifc",
        "antigravity",
        "argparse",
        "array",
        "ast",
        "asynchat",
        "asyncio",
        "asyncore",
        "atexit",
        "audioop",
        "base64",
        "bdb",
        "binascii",
        "binhex",
        "bisect",
        "builtins",
        "bz2",
        "cProfile",
        "calendar",
        "cgi",
        "cgitb",
        "chunk",
        "cmath",
        "cmd",
        "code",
        "codecs",
        "codeop",
        "collections",
        "colorsys",
        "compileall",
        "concurrent",
        "configparser",
        "contextlib",
        "contextvars",
        "copy",
        "copyreg",
        "crypt",
        "csv",
        "ctypes",
        "curses",
        "dataclasses",
        "datetime",
        "dbm",
        "decimal",
        "difflib",
        "dis",
        "distutils",
        "doctest",
        "dummy_threading",
        "email",
        "encodings",
        "ensurepip",
        "enum",
        "errno",
        "faulthandler",
        "fcntl",
        "filecmp",
        "fileinput",
        "fnmatch",
        "formatter",
        "fpectl",
        "fractions",
        "ftplib",
        "functools",
        "gc",
        "genericpath",
        "getopt",
        "getpass",
        "gettext",
        "glob",
        "grp",
        "gzip",
        "hashlib",
        "heapq",
        "hmac",
        "html",
        "http",
        "idlelib",
        "imaplib",
        "imghdr",
        "imp",
        "importlib",
        "inspect",
        "io",
        "ipaddress",
        "itertools",
        "json",
        "keyword",
        "lib2to3",
        "linecache",
        "locale",
        "logging",
        "lzma",
        "macpath",
        "mailbox",
        "mailcap",
        "marshal",
        "math",
        "mimetypes",
        "mmap",
        "modulefinder",
        "msilib",
        "msvcrt",
        "multiprocessing",
        "netrc",
        "nis",
        "nntplib",
        "nt",
        "ntpath",
        "numbers",
        "operator",
        "optparse",
        "os",
        "ossaudiodev",
        "parser",
        "pathlib",
        "pdb",
        "pickle",
        "pickletools",
        "pipes",
        "pkgutil",
        "platform",
        "plistlib",
        "poplib",
        "posix",
        "posixpath",
        "pprint",
        "profile",
        "pstats",
        "pty",
        "pwd",
        "py_compile",
        "pyclbr",
        "pydoc",
        "queue",
        "quopri",
        "random",
        "re",
        "readline",
        "reprlib",
        "resource",
        "rlcompleter",
        "runpy",
        "sched",
        "secrets",
        "select",
        "selectors",
        "shelve",
        "shlex",
        "shutil",
        "signal",
        "site",
        "smtpd",
        "smtplib",
        "sndhdr",
        "socket",
        "socketserver",
        "spwd",
        "sqlite3",
        "sre_compile",
        "sre_constants",
        "sre_parse",
        "ssl",
        "stat",
        "statistics",
        "string",
        "stringprep",
        "struct",
        "subprocess",
        "sunau",
        "symbol",
        "symtable",
        "sys",
        "sysconfig",
        "syslog",
        "tabnanny",
        "tarfile",
        "telnetlib",
        "tempfile",
        "termios",
        "test",
        "textwrap",
        "this",
        "threading",
        "time",
        "timeit",
        "tkinter",
        "token",
        "tokenize",
        "trace",
        "traceback",
        "tracemalloc",
        "tty",
        "turtle",
        "turtledemo",
        "types",
        "typing",
        "unicodedata",
        "unittest",
        "urllib",
        "uu",
        "uuid",
        "venv",
        "warnings",
        "wave",
        "weakref",
        "webbrowser",
        "winreg",
        "winsound",
        "wsgiref",
        "xdrlib",
        "xml",
        "xmlrpc",
        "zipapp",
        "zipfile",
        "zipimport",
        "zlib",
        "_thread",
    }
)

# Delta adjustments per minor Python version
VERSION_DELTAS: Mapping[tuple[int, int], tuple[set[str], set[str]]] = {
    # format: (added_modules, removed_modules)
    (3, 7): (set(), set()),
    (3, 8): (set(), set()),
    (3, 9): ({"zoneinfo", "graphlib"}, {"fpectl", "macpath"}),
    (3, 10): (set(), {"formatter"}),
    (3, 11): ({"tomllib"}, {"binhex"}),
    (3, 12): (set(), {"asynchat", "asyncore", "distutils", "imp", "smtpd"}),
    (3, 13): (
        set(),
        {
            "aifc",
            "audioop",
            "cgi",
            "cgitb",
            "chunk",
            "crypt",
            "imghdr",
            "mailcap",
            "msilib",
            "nis",
            "nntplib",
            "pipes",
            "sndhdr",
            "spwd",
            "sunau",
            "telnetlib",
            "uu",
            "xdrlib",
            "lib2to3",
        },
    ),
    (3, 14): ({"annotationlib"}, set()),
}


class StdlibCatalog:
    """Standard library module catalog aware of per-version Python inventories.

    Documented Update Procedure:
    --------------------------
    1. For existing releases, Python stdlib module inventories are derived from:
       - `sys.stdlib_module_names` introduced in Python 3.10 (PEP 594 and PEP 621).
       - Python's standard library documentation indices for Python 3.7 through 3.9.
    2. To add or update support for a new Python version:
       - Add a new minor tuple entry `(3, X)` to `VERSION_DELTAS` defining newly
         introduced standard modules and deprecated/removed batteries.
    3. The catalog computes inventories deterministically without requiring interpreters
       of the target version to be present on the host.
    """

    def __init__(self) -> None:
        self._cache: dict[tuple[int, int], frozenset[str]] = {}
        self._build_inventories()

    def _build_inventories(self) -> None:
        """Precompute stdlib sets for known (3, minor) versions."""
        running = set(BASE_STDLIB_MODULES)
        for (major, minor), (added, removed) in sorted(VERSION_DELTAS.items()):
            running.update(added)
            running.difference_update(removed)
            self._cache[(major, minor)] = frozenset(running)

    def parse_version_tuple(self, version_str: str | None) -> tuple[int, int] | None:
        """Extract (major, minor) tuple from a version string."""
        if not version_str:
            return (sys.version_info.major, sys.version_info.minor)
        parts = version_str.strip().split(".")
        if len(parts) >= 2:
            try:
                return (int(parts[0]), int(parts[1]))
            except ValueError:
                return None
        elif len(parts) == 1:
            try:
                return (int(parts[0]), 0)
            except ValueError:
                return None
        return None

    def get_stdlib_modules(self, target_python_version: str | None = None) -> frozenset[str] | None:
        """Return the complete set of standard library modules for a target Python version.

        Returns None if the version is uncataloged or invalid.
        """
        ver = self.parse_version_tuple(target_python_version)
        if ver is None:
            return None
        if ver in self._cache:
            return self._cache[ver]

        # For unknown Python 3 versions, interpolate or return unverified
        if ver[0] == 3 and 7 <= ver[1] <= 14:
            return self._cache.get(ver)

        return None

    def is_stdlib(
        self,
        module_name: str,
        target_python_version: str | None = None,
    ) -> bool | None:
        """Check whether a module belongs to the Python standard library.

        Returns:
            True: Definitively standard library for target version.
            False: Definitively not standard library for target version.
            None: Unverified (e.g. unsupported target version or unrecognized).
        """
        top_level = module_name.split(".")[0].strip()
        if not top_level:
            return False

        modules = self.get_stdlib_modules(target_python_version)
        if modules is None:
            # Fall back to host interpreter if version matches host, else unverified
            host_ver = (sys.version_info.major, sys.version_info.minor)
            target_ver = self.parse_version_tuple(target_python_version)
            if target_ver == host_ver:
                if hasattr(sys, "stdlib_module_names"):
                    return top_level in sys.stdlib_module_names
            return None

        return top_level in modules
