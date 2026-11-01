"""Curated database of top-level Python import names to PyPI distribution names."""

from __future__ import annotations

from packaging.utils import canonicalize_name

# Curated mapping table: top-level import name (lowercase) -> list of distribution names
# When a single import name has multiple providing distributions, all candidates are listed.
CURATED_IMPORT_MAPPINGS: dict[str, list[str]] = {
    # Ambiguous mappings (1 to many)
    "cv2": [
        "opencv-python",
        "opencv-contrib-python",
        "opencv-python-headless",
        "opencv-contrib-python-headless",
    ],
    "crypto": [
        "pycryptodome",
        "pycrypto",
    ],
    "telegram": [
        "python-telegram-bot",
        "telepot",
    ],
    "ldap": [
        "python-ldap",
        "ldap3",
    ],
    "kafka": [
        "kafka-python",
        "confluent-kafka",
    ],
    # 1 to 1 mappings where import != distribution name
    "sklearn": ["scikit-learn"],
    "pil": ["Pillow"],
    "yaml": ["PyYAML"],
    "bs4": ["beautifulsoup4"],
    "dotenv": ["python-dotenv"],
    "dateutil": ["python-dateutil"],
    "jwt": ["PyJWT"],
    "serial": ["pyserial"],
    "magic": ["python-magic"],
    "git": ["GitPython"],
    "google.protobuf": ["protobuf"],
    "protobuf": ["protobuf"],
    "sqlalchemy": ["SQLAlchemy"],
    "openssl": ["pyOpenSSL"],
    "websocket": ["websocket-client"],
    "usb": ["pyusb"],
    "wx": ["wxPython"],
    "fitz": ["PyMuPDF"],
    "opengl": ["PyOpenGL"],
    "bio": ["biopython"],
    "docx": ["python-docx"],
    "pptx": ["python-pptx"],
    "attr": ["attrs"],
    "playwright": ["playwright"],
    "jinja2": ["Jinja2"],
    "werkzeug": ["Werkzeug"],
    "markupsafe": ["MarkupSafe"],
    "dns": ["dnspython"],
    "multipart": ["python-multipart"],
    "jose": ["python-jose"],
    "socketio": ["python-socketio"],
    "engineio": ["python-engineio"],
    "slugify": ["python-slugify"],
    "pydantic_core": ["pydantic-core"],
    "pydantic_settings": ["pydantic-settings"],
    "typing_extensions": ["typing-extensions"],
    "pkg_resources": ["setuptools"],
    # Canonical direct mappings (frequently used)
    "requests": ["requests"],
    "httpx": ["httpx"],
    "aiohttp": ["aiohttp"],
    "pydantic": ["pydantic"],
    "numpy": ["numpy"],
    "pandas": ["pandas"],
    "scipy": ["scipy"],
    "torch": ["torch"],
    "pytest": ["pytest"],
    "click": ["click"],
    "typer": ["typer"],
    "fastapi": ["fastapi"],
    "uvicorn": ["uvicorn"],
    "starlette": ["starlette"],
    "tqdm": ["tqdm"],
    "rich": ["rich"],
    "matplotlib": ["matplotlib"],
    "seaborn": ["seaborn"],
    "redis": ["redis"],
    "celery": ["celery"],
    "flask": ["Flask"],
    "django": ["Django"],
    "packaging": ["packaging"],
    "setuptools": ["setuptools"],
    "wheel": ["wheel"],
    "coverage": ["coverage"],
    "black": ["black"],
    "ruff": ["ruff"],
    "mypy": ["mypy"],
    "boto3": ["boto3"],
    "botocore": ["botocore"],
    "fsspec": ["fsspec"],
    "pytz": ["pytz"],
    "urllib3": ["urllib3"],
    "certifi": ["certifi"],
    "idna": ["idna"],
    "charset_normalizer": ["charset-normalizer"],
}


class MappingDatabase:
    """Provides lookup over curated import-to-distribution mappings."""

    def __init__(self, custom_table: dict[str, list[str]] | None = None) -> None:
        self._table: dict[str, list[str]] = {}
        for imp, dists in CURATED_IMPORT_MAPPINGS.items():
            self._table[imp.lower()] = [canonicalize_name(d) for d in dists]

        if custom_table:
            for imp, dists in custom_table.items():
                self._table[imp.lower()] = [canonicalize_name(d) for d in dists]

    def get_candidates(self, import_name: str) -> list[str]:
        """Return candidate distribution names for an imported top-level name."""
        key = import_name.strip().lower()
        if key in self._table:
            return list(self._table[key])

        # Also check dotted prefix (e.g. 'google.protobuf' -> check 'google.protobuf')
        parts = key.split(".")
        if len(parts) > 1 and parts[0] in self._table:
            return list(self._table[parts[0]])

        return []

    def is_known(self, import_name: str) -> bool:
        """Return True if the import name has a curated mapping."""
        key = import_name.strip().lower()
        return key in self._table or (len(key.split(".")) > 1 and key.split(".")[0] in self._table)
