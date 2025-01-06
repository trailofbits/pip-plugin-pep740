"""The `pip-plugin-pep740` APIs."""

__version__ = "0.0.1"

from ._impl import pre_download, provided_hooks

__all__ = ["pre_download", "provided_hooks"]
