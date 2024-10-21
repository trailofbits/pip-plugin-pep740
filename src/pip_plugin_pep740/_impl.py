"""The `pip-plugin-pep740` implementation."""

from __future__ import annotations

from json import JSONDecodeError
from typing import TYPE_CHECKING, Literal

import requests
from packaging.utils import parse_sdist_filename, parse_wheel_filename
from pydantic import ValidationError
from pypi_attestations import (
    AttestationBundle,
    AttestationError,
    Distribution,
    GitHubPublisher,
    GitLabPublisher,
    Provenance,
)
from rfc3986 import builder
from sigstore.verify import Verifier, policy

if TYPE_CHECKING:
    from pathlib import Path  # pragma: no cover

PluginType = Literal["dist-inspector"]


def _get_provenance(filename: str) -> Provenance | None:
    """Download the provenance for a given distribution."""
    if filename.endswith(".tar.gz"):
        name, version = parse_sdist_filename(filename)
    elif filename.endswith(".whl"):
        name, version, _, _ = parse_wheel_filename(filename)
    else:
        # Unexpected file, ignore
        return None

    # This currently only works when installing packages from PyPI
    # In order to make it general, we need to get the provenance URL from the index API instead
    # of hardcoding the URL. This can be done once
    # https://github.com/pypi/warehouse/pull/16801 is merged
    provenance_url = (
        builder.URIBuilder()
        .add_scheme("https")
        .add_host("pypi.org")
        .add_path(f"integrity/{name}/{version}/{filename}/provenance")
        .geturl()
    )
    try:
        r = requests.get(url=provenance_url, params={"Accept": "application/json"}, timeout=5)
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


def _get_verification_policy(bundle: AttestationBundle) -> policy.VerificationPolicy:
    """Construct a verification policy from the Trusted Publisher in the bundle."""
    publisher = bundle.publisher
    if isinstance(publisher, GitHubPublisher):
        issuer = "https://token.actions.githubusercontent.com"
        repository = f"https://github.com/{publisher.repository}"
    elif isinstance(publisher, GitLabPublisher):
        issuer = "https://gitlab.com"
        repository = f"https://gitlab.com/{publisher.repository}"

    return policy.AllOf(
        [
            policy.OIDCIssuerV2(issuer),
            policy.OIDCSourceRepositoryURI(repository),
        ]
    )


def plugin_type() -> PluginType:
    """Return the plugin type."""
    return "dist-inspector"


def pre_download(url: str, filename: str, digest: str) -> None:  # noqa: ARG001
    """Inspect the file about to be downloaded by pip.

    This hook is called right before pip downloads a distribution
    file. It doesn't return anything, and it can only raise `ValueError`
    to signal to pip that the operation should be aborted.
    """
    provenance = _get_provenance(filename)
    if not provenance:
        return
    distribution = Distribution(name=filename, digest=digest)
    verifier = Verifier.production()
    for bundle in provenance.attestation_bundles:
        # Each bundle has their own trusted publisher information, so each
        # needs its own verification policy.
        policy = _get_verification_policy(bundle)
        try:
            for a in bundle.attestations:
                a.verify(verifier=verifier, policy=policy, dist=distribution)
        except AttestationError as e:
            msg = f"Provenance failed verification: {e}"
            raise ValueError(msg) from e
    return


def pre_extract(dist: Path) -> None:  # noqa: ARG001
    """Check before extraction."""
    return
