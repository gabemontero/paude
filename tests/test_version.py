"""Test version information."""

import re

from paude import __version__


def test_version_format():
    """Verify version is a valid semver string."""
    # Match major.minor.patch with optional PEP 440 pre-release suffix (e.g. rc1, a1, b2)
    pattern = r"^\d+\.\d+\.\d+([a-zA-Z]+\d+)?$"
    assert re.match(pattern, __version__), f"Invalid version format: {__version__}"
