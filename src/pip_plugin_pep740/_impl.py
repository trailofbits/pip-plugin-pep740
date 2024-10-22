"""The `pip-plugin-pep740` implementation."""

from __future__ import annotations

from json import JSONDecodeError
from typing import TYPE_CHECKING, Literal

import requests
import rfc3986
from packaging.utils import parse_sdist_filename, parse_wheel_filename
from pydantic import ValidationError
from pypi_attestations import (
    AttestationError,
    Distribution,
    Provenance,
)
from rfc3986 import builder

if TYPE_CHECKING:
    from pathlib import Path  # pragma: no cover

PluginType = Literal["dist-inspector"]


def _get_provenance(filename: str, url: str) -> Provenance | None:
    """Download the provenance for a given distribution."""
    url_authority = rfc3986.api.uri_reference(url).authority
    # Only PyPI and TestPyPI currently support PEP-740
    if url_authority == "files.pythonhosted.org":
        index_host = "pypi.org"
    elif url_authority == "test-files.pythonhosted.org":
        index_host = "test.pypi.org"
    else:
        return None

    if filename.endswith(".tar.gz"):
        name, version = parse_sdist_filename(filename)
    elif filename.endswith(".whl"):
        name, version, _, _ = parse_wheel_filename(filename)
    else:
        # Unexpected file, ignore
        return None

    provenance_url = (
        builder.URIBuilder()
        .add_scheme("https")
        .add_host(index_host)
        .add_path(f"integrity/{name}/{version}/{filename}/provenance")
        .geturl()
    )
    try:
        r = requests.get(
            url=provenance_url,
            params={"Accept": "application/vnd.pypi.integrity.v1+json"},
            timeout=5,
        )
        r.raise_for_status()
    except requests.HTTPError as e:
        # If there is no provenance available, continue
        if e.response.status_code == requests.codes.not_found:
            return None
        raise ValueError(e) from e
    except requests.RequestException as e:
        msg = f"Error downloading provenance file: {e}"
        raise ValueError(msg) from e

    try:
        return Provenance.model_validate(r.json())
    except ValidationError as e:
        msg = f"Invalid provenance: {e}"
        raise ValueError(msg) from e
    except JSONDecodeError as e:
        msg = f"Invalid provenance JSON: {e}"
        raise ValueError(msg) from e


def plugin_type() -> PluginType:
    """Return the plugin type."""
    return "dist-inspector"


def pre_download(url: str, filename: str, digest: str) -> None:
    """Inspect the file about to be downloaded by pip.

    This hook is called right before pip downloads a distribution
    file. It doesn't return anything, and it can only raise `ValueError`
    to signal to pip that the operation should be aborted.
    """
    provenance = _get_provenance(filename=filename, url=url)
    if not provenance:
        return
    distribution = Distribution(name=filename, digest=digest)
    try:
        for bundle in provenance.attestation_bundles:
            for a in bundle.attestations:
                a.verify(bundle.publisher, dist=distribution)
    except AttestationError as e:
        msg = f"Provenance failed verification: {e}"
        raise ValueError(msg) from e
    return


def pre_extract(dist: Path) -> None:  # noqa: ARG001
    """Check before extraction."""
    return
