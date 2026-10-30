"""Unit tests for PyPI metadata parser and requirement extraction."""

from __future__ import annotations

from pydeps.metadata.metadata_parser import (
    parse_pypi_release,
    parse_requirement_entry,
    parse_wheel_platform_tags,
)


def test_parse_requirement_entry_variants() -> None:
    """Test parsing various PEP 508 requirement formats."""
    # Standard pinned
    dep1, err1 = parse_requirement_entry("requests>=2.28.0, <3.0")
    assert err1 is None
    assert dep1 is not None
    assert dep1.name == "requests"
    assert dep1.version_specifier == "<3.0,>=2.28.0"

    # Extras
    dep2, err2 = parse_requirement_entry("pydantic[email,fast] >= 2.0")
    assert err2 is None
    assert dep2 is not None
    assert dep2.name == "pydantic"
    assert "email" in dep2.extras
    assert "fast" in dep2.extras

    # Environment markers
    dep3, err3 = parse_requirement_entry('importlib-metadata>=0.12; python_version < "3.8"')
    assert err3 is None
    assert dep3 is not None
    assert dep3.name == "importlib-metadata"
    assert dep3.environment_marker == 'python_version < "3.8"'

    # Extras + markers
    dep4, err4 = parse_requirement_entry('PySocks!=1.5.7,>=1.5.6; extra == "socks"')
    assert err4 is None
    assert dep4 is not None
    assert dep4.name == "pysocks"
    assert dep4.environment_marker == 'extra == "socks"'

    # Malformed requirement
    dep_bad, err_bad = parse_requirement_entry("not a valid requirement !!!")
    assert dep_bad is None
    assert err_bad is not None
    assert "Malformed requirement string" in err_bad


def test_parse_wheel_platform_tags() -> None:
    """Test extracting platform tags from wheel filenames."""
    # Universal wheel
    tags1 = parse_wheel_platform_tags("requests-2.31.0-py3-none-any.whl")
    assert tags1 == ["any"]

    # Windows 64-bit
    tags2 = parse_wheel_platform_tags("numpy-1.26.0-cp311-cp311-win_amd64.whl")
    assert tags2 == ["win_amd64"]

    # Multi-platform manylinux
    tags3 = parse_wheel_platform_tags(
        "cryptography-41.0.0-cp37-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
    )
    assert "manylinux_2_17_x86_64" in tags3
    assert "manylinux2014_x86_64" in tags3

    # Source dist (non-wheel)
    tags_sdist = parse_wheel_platform_tags("requests-2.31.0.tar.gz")
    assert tags_sdist == []


def test_parse_pypi_release_payload() -> None:
    """Test full parsing of PyPI JSON release payload into PackageRelease model."""
    raw_payload = {
        "info": {
            "name": "Flask",
            "version": "3.0.0",
            "summary": "A simple framework for building complex web applications.",
            "requires_python": ">=3.8",
            "requires_dist": [
                "Werkzeug>=3.0.0",
                "Jinja2>=3.1.2",
                "itsdangerous>=2.1.2",
                "click>=8.1.3",
                'blinker>=1.6.2; extra == "async"',
            ],
            "provides_extra": ["async", "dotenv"],
            "yanked": False,
            "yanked_reason": None,
            "project_urls": {
                "Documentation": "https://flask.palletsprojects.com/",
            },
        },
        "urls": [
            {
                "filename": "flask-3.0.0-py3-none-any.whl",
                "packagetype": "bdist_wheel",
                "python_version": "py3",
                "requires_python": ">=3.8",
                "size": 99650,
                "upload_time_iso_8601": "2023-09-30T17:00:00Z",
                "digests": {"sha256": "abcdef1234567890"},
                "yanked": False,
            },
            {
                "filename": "flask-3.0.0.tar.gz",
                "packagetype": "sdist",
                "python_version": "source",
                "requires_python": ">=3.8",
                "size": 650000,
                "upload_time_iso_8601": "2023-09-30T16:55:00Z",
                "digests": {"sha256": "fedcba0987654321"},
                "yanked": False,
            },
        ],
    }

    release, diags = parse_pypi_release(raw_payload)
    assert len(diags) == 0
    assert release.distribution_name == "flask"
    assert release.version == "3.0.0"
    assert release.requires_python == ">=3.8"
    assert len(release.requires_dist) == 5
    assert len(release.release_files) == 2
    assert release.provides_extra == ["async", "dotenv"]
    assert release.yanked is False

    dep_names = [d.name for d in release.requires_dist]
    assert "werkzeug" in dep_names
    assert "jinja2" in dep_names
    assert "click" in dep_names
    assert "blinker" in dep_names

    blinker_dep = next(d for d in release.requires_dist if d.name == "blinker")
    assert blinker_dep.environment_marker == 'extra == "async"'


def test_parse_yanked_release() -> None:
    """Test parsing a release flagged as yanked with an explicit reason."""
    raw_payload = {
        "info": {
            "name": "broken-package",
            "version": "1.0.1",
            "yanked": True,
            "yanked_reason": "Critical regression in auth logic",
        },
        "urls": [],
    }

    release, _ = parse_pypi_release(raw_payload)
    assert release.yanked is True
    assert release.yanked_reason == "Critical regression in auth logic"
