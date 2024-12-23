"""The `pip-plugin-pep740` implementation."""

from __future__ import annotations

from json import JSONDecodeError

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


def _get_provenance_url(filename: str, index_host: str) -> str | None:
    if filename.endswith(".tar.gz"):
        name, _ = parse_sdist_filename(filename)
    elif filename.endswith(".whl"):
        name, _, _, _ = parse_wheel_filename(filename)
    else:
        # Unexpected file, ignore
        return None

    simple_index_package_url = (
        builder.URIBuilder()
        .add_scheme("https")
        .add_host(index_host)
        .add_path(f"simple/{name}/")
        .geturl()
    )
    try:
        r = requests.get(
            url=simple_index_package_url,
            headers={"Accept": "application/vnd.pypi.simple.v1+json"},
            timeout=5,
        )
        r.raise_for_status()
    except requests.RequestException as e:
        msg = f"Error accessing PyPI simple API: {e}"
        raise ValueError(msg) from e

    try:
        package_json = r.json()
    except JSONDecodeError as e:
        msg = f"Invalid PyPI simple index JSON response: {e}"
        raise ValueError(msg) from e

    matching_artifacts = [f for f in package_json["files"] if f["filename"] == filename]
    if len(matching_artifacts) == 0:
        msg = f"Could not find file {filename} using the simple API at {index_host}"
        raise ValueError(msg)

    artifact_info = matching_artifacts[0]
    provenance_url: str | None = artifact_info.get("provenance")
    return provenance_url


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

    provenance_url = _get_provenance_url(filename=filename, index_host=index_host)
    if provenance_url is None:
        # Can't verify artifacts uploaded without attestations
        return None
    try:
        r = requests.get(
            url=provenance_url,
            headers={"Accept": "application/vnd.pypi.integrity.v1+json"},
            timeout=5,
        )
        r.raise_for_status()
    except requests.RequestException as e:
        msg = f"Error downloading provenance file: {e}"
        raise ValueError(msg) from e

    try:
        return Provenance.model_validate(r.json())
    except JSONDecodeError as e:
        msg = f"Invalid provenance JSON: {e}"
        raise ValueError(msg) from e
    except ValidationError as e:
        msg = f"Invalid provenance: {e}"
        raise ValueError(msg) from e


def provided_hooks() -> list[str]:
    """Return the hooks we want to register."""
    return ["pre_download"]


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
