"""Tests for the plugin implementation."""

import json
from pathlib import Path

import pytest
import requests
import requests_mock
from pypi_attestations import Distribution

import pip_plugin_pep740

PACKAGE_NAME = "abi3info"
DIST_FILE_1 = Path("test/assets/abi3info-2024.10.8-py3-none-any.whl")
PROVENANCE_FILE_1 = Path("test/assets/abi3info-2024.10.8-py3-none-any.whl.provenance")

DIST_FILE_2 = Path("test/assets/abi3info-2024.10.3-py3-none-any.whl")
PROVENANCE_FILE_2 = Path("test/assets/abi3info-2024.10.3-py3-none-any.whl.provenance")

DIST_FILE_3 = Path("test/assets/abi3info-2024.10.8.tar.gz")
PROVENANCE_FILE_3 = Path("test/assets/abi3info-2024.10.8.tar.gz.provenance")

with DIST_FILE_1.open("rb") as f:
    DIST_DIGEST_1 = Distribution.from_file(DIST_FILE_1).digest

with DIST_FILE_2.open("rb") as f:
    DIST_DIGEST_2 = Distribution.from_file(DIST_FILE_2).digest

with DIST_FILE_3.open("rb") as f:
    DIST_DIGEST_3 = Distribution.from_file(DIST_FILE_3).digest


class TestPlugin:
    def test_plugin_type(self) -> None:
        assert pip_plugin_pep740.plugin_type() == "dist-inspector"

    @pytest.mark.parametrize(
        ("filename", "provenance_file", "digest"),
        [
            (DIST_FILE_1.name, PROVENANCE_FILE_1, DIST_DIGEST_1),
            (DIST_FILE_3.name, PROVENANCE_FILE_3, DIST_DIGEST_3),
        ],
    )
    def test_pre_download_valid_provenance(
        self, filename: str, provenance_file: Path, digest: str
    ) -> None:
        with requests_mock.Mocker(real_http=True) as m:
            m.get(
                f"https://test.pypi.org/simple/{PACKAGE_NAME}/",
                text=f'{{"files": [{{"filename": "{filename}", "provenance": "https://provenance_url"}}]}}',
            )
            m.get(
                f"https://pypi.org/simple/{PACKAGE_NAME}/",
                text=f'{{"files": [{{"filename": "{filename}", "provenance": "https://provenance_url"}}]}}',
            )
            m.get(
                "https://provenance_url",
                text=provenance_file.read_text(),
            )
            pip_plugin_pep740.pre_download(
                url="https://files.pythonhosted.org/some_path",
                filename=filename,
                digest=digest,
            )
            # TestPyPI URLs should also work
            pip_plugin_pep740.pre_download(
                url="https://test-files.pythonhosted.org/some_path",
                filename=filename,
                digest=digest,
            )

    def test_pre_download_invalid_filename(self) -> None:
        assert (
            pip_plugin_pep740.pre_download(
                url="https://files.pythonhosted.org/some_path",
                filename="not_a_dist.docx",
                digest="digest",
            )
            is None
        )

    def test_pre_download_no_provenance_found(self) -> None:
        with requests_mock.Mocker(real_http=True) as m:
            m.get(
                f"https://pypi.org/simple/{PACKAGE_NAME}/",
                text=f'{{"files": [{{"filename": "{DIST_FILE_1.name}"}}]}}',
            )
            assert (
                pip_plugin_pep740.pre_download(
                    url="https://files.pythonhosted.org/some_path",
                    filename=DIST_FILE_1.name,
                    digest=DIST_DIGEST_1,
                )
                is None
            )

    def test_pre_download_index_http_error(self) -> None:
        with requests_mock.Mocker(real_http=True) as m:
            m.get(
                f"https://pypi.org/simple/{PACKAGE_NAME}/",
                status_code=403,
            )
            with pytest.raises(ValueError, match="403 Client Error"):
                pip_plugin_pep740.pre_download(
                    url="https://files.pythonhosted.org/some_path",
                    filename=DIST_FILE_1.name,
                    digest=DIST_DIGEST_1,
                )

    def test_pre_download_index_timeout(self) -> None:
        with requests_mock.Mocker(real_http=True) as m:
            m.get(
                f"https://pypi.org/simple/{PACKAGE_NAME}/",
                exc=requests.exceptions.ConnectTimeout,
            )
            with pytest.raises(ValueError, match="Error accessing PyPI simple API"):
                pip_plugin_pep740.pre_download(
                    url="https://files.pythonhosted.org/some_path",
                    filename=DIST_FILE_1.name,
                    digest=DIST_DIGEST_1,
                )

    def test_pre_download_provenance_download_error(self) -> None:
        with requests_mock.Mocker(real_http=True) as m:
            m.get(
                f"https://pypi.org/simple/{PACKAGE_NAME}/",
                text=f'{{"files": [{{"filename": "{DIST_FILE_1.name}", "provenance": "https://provenance_url"}}]}}',
            )
            m.get(
                "https://provenance_url",
                status_code=403,
            )
            with pytest.raises(ValueError, match="403 Client Error"):
                pip_plugin_pep740.pre_download(
                    url="https://files.pythonhosted.org/some_path",
                    filename=DIST_FILE_1.name,
                    digest=DIST_DIGEST_1,
                )

    def test_pre_download_not_pypi_url(self) -> None:
        assert (
            pip_plugin_pep740.pre_download(
                url="https://notpypi.org",
                filename=DIST_FILE_1.name,
                digest=DIST_DIGEST_1,
            )
            is None
        )

    def test_pre_download_provenance_timeout(self) -> None:
        with requests_mock.Mocker(real_http=True) as m:
            m.get(
                f"https://pypi.org/simple/{PACKAGE_NAME}/",
                text=f'{{"files": [{{"filename": "{DIST_FILE_1.name}", "provenance": "https://provenance_url"}}]}}',
            )
            m.get(
                "https://provenance_url",
                exc=requests.exceptions.ConnectTimeout,
            )
            with pytest.raises(ValueError, match="Error downloading provenance file"):
                pip_plugin_pep740.pre_download(
                    url="https://files.pythonhosted.org/some_path",
                    filename=DIST_FILE_1.name,
                    digest=DIST_DIGEST_1,
                )

    def test_pre_download_invalid_provenance(self) -> None:
        with requests_mock.Mocker(real_http=True) as m:
            m.get(
                f"https://pypi.org/simple/{PACKAGE_NAME}/",
                text=f'{{"files": [{{"filename": "{DIST_FILE_1.name}", "provenance": "https://provenance_url"}}]}}',
            )
            m.get(
                "https://provenance_url",
                text=PROVENANCE_FILE_2.read_text(),
            )
            with pytest.raises(
                ValueError,
                match="subject does not match distribution name",
            ):
                pip_plugin_pep740.pre_download(
                    url="https://files.pythonhosted.org/some_path",
                    filename=DIST_FILE_1.name,
                    digest=DIST_DIGEST_1,
                )

    def test_pre_download_invalid_index_json(self) -> None:
        with requests_mock.Mocker(real_http=True) as m:
            m.get(f"https://pypi.org/simple/{PACKAGE_NAME}/", text="invalidjson")
            with pytest.raises(
                ValueError,
                match="Invalid PyPI simple index JSON response",
            ):
                pip_plugin_pep740.pre_download(
                    url="https://files.pythonhosted.org/some_path",
                    filename=DIST_FILE_1.name,
                    digest=DIST_DIGEST_1,
                )

    def test_pre_download_missing_package_from_index_json(self) -> None:
        with requests_mock.Mocker(real_http=True) as m:
            m.get(
                f"https://pypi.org/simple/{PACKAGE_NAME}/",
                text=f'{{"files": [{{"filename": "{DIST_FILE_2.name}", "provenance": "https://provenance_url"}}]}}',
            )
            with pytest.raises(
                ValueError,
                match=f"Could not find file {DIST_FILE_1.name} using the simple API at pypi.org",
            ):
                pip_plugin_pep740.pre_download(
                    url="https://files.pythonhosted.org/some_path",
                    filename=DIST_FILE_1.name,
                    digest=DIST_DIGEST_1,
                )

    def test_pre_download_invalid_provenance_json(self) -> None:
        with requests_mock.Mocker(real_http=True) as m:
            m.get(
                f"https://pypi.org/simple/{PACKAGE_NAME}/",
                text=f'{{"files": [{{"filename": "{DIST_FILE_1.name}", "provenance": "https://provenance_url"}}]}}',
            )
            m.get(
                "https://provenance_url",
                text="invalidjson",
            )
            with pytest.raises(
                ValueError,
                match="Invalid provenance JSON",
            ):
                pip_plugin_pep740.pre_download(
                    url="https://files.pythonhosted.org/some_path",
                    filename=DIST_FILE_1.name,
                    digest=DIST_DIGEST_1,
                )

    def test_pre_download_malformed_provenance_valid_json(self) -> None:
        provenance = json.loads(PROVENANCE_FILE_1.read_text())
        provenance["attestation_bundles"] = "invalid"
        with requests_mock.Mocker(real_http=True) as m:
            m.get(
                f"https://pypi.org/simple/{PACKAGE_NAME}/",
                text=f'{{"files": [{{"filename": "{DIST_FILE_1.name}", "provenance": "https://provenance_url"}}]}}',
            )
            m.get(
                "https://provenance_url",
                text=json.dumps(provenance),
            )
            with pytest.raises(
                ValueError,
                match="Invalid provenance: 1 validation error for Provenance",
            ):
                pip_plugin_pep740.pre_download(
                    url="https://files.pythonhosted.org/some_path",
                    filename=DIST_FILE_1.name,
                    digest=DIST_DIGEST_1,
                )

    def test_pre_extract(self) -> None:
        assert pip_plugin_pep740.pre_extract(dist=Path("filename")) is None
