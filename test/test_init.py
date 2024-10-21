"""Tests for the module's init."""

import pip_plugin_pep740


def test_version() -> None:
    version = getattr(pip_plugin_pep740, "__version__", None)
    assert version is not None
    assert isinstance(version, str)
