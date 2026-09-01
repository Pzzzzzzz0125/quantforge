"""Package-level smoke tests."""

from importlib.metadata import version

import quantforge


def test_quantforge_import_exposes_version() -> None:
    """The installed package imports and exposes its initial version."""
    assert quantforge.__version__ == version("quantforge") == "0.1.0"
