# Pip plugin pep740

<!--- BADGES: START --->
[![CI](https://github.com/facutuesca/pip-plugin-pep740/actions/workflows/tests.yml/badge.svg)](https://github.com/facutuesca/pip-plugin-pep740/actions/workflows/tests.yml)
[![PyPI version](https://badge.fury.io/py/pip-plugin-pep740.svg)](https://pypi.org/project/pip-plugin-pep740)
[![Packaging status](https://repology.org/badge/tiny-repos/python:pip-plugin-pep740.svg)](https://repology.org/project/python:pip-plugin-pep740/versions)
<!--- BADGES: END --->

An implementation of a "dist-inspector" [pip](https://pypi.org/project/pip/) plugin 
that verifies PEP-740 attestations before installing a package, and
aborts the installation if verification fails
(as discussed on the pip [issue tracker](https://github.com/pypa/pip/issues/12766)).
