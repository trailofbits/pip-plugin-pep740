"""The `pip-plugin-pep740` APIs."""

__version__ = "0.0.1"

from ._impl import plugin_type, pre_download, pre_extract

__all__ = ["plugin_type", "pre_extract", "pre_download"]
