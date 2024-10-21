SHELL := /bin/bash

PY_IMPORT = pip_plugin_pep740

ALL_PY_SRCS := $(shell find src -name '*.py') \
	$(shell find test -name '*.py')

# Optionally overriden by the user, if they're using a virtual environment manager.
VENV ?= env

# On Windows, venv scripts/shims are under `Scripts` instead of `bin`.
VENV_BIN := $(VENV)/bin
ifeq ($(OS),Windows_NT)
	VENV_BIN := $(VENV)/Scripts
endif

# Optionally overridden by the user in the `release` target.
BUMP_ARGS :=

# Optionally overridden by the user in the `test` target.
TESTS :=

# Optionally overridden by the user/CI, to limit the installation to a specific
# subset of development dependencies.
INSTALL_EXTRA := dev

# If the user selects a specific test pattern to run, set `pytest` to fail fast
# and only run tests that match the pattern.
# Otherwise, run all tests and enable coverage assertions, since we expect
# complete test coverage.
ifneq ($(TESTS),)
	TEST_ARGS := -x -k $(TESTS)
	COV_ARGS :=
else
	TEST_ARGS :=
	COV_ARGS := --fail-under 100
endif

.PHONY: all
all:
	@echo "Run my targets individually!"

.PHONY: dev
dev: $(VENV)/pyvenv.cfg

$(VENV)/pyvenv.cfg: pyproject.toml
	uv venv $(VENV)
	@. $(VENV_BIN)/activate && uv pip install -e '.[$(INSTALL_EXTRA)]' --prerelease=allow

.PHONY: lint
lint: $(VENV)/pyvenv.cfg
	. $(VENV_BIN)/activate && \
		ruff format --check && \
		ruff check && \
		mypy
	. $(VENV_BIN)/activate && \
		interrogate -c pyproject.toml .

.PHONY: reformat
reformat:
	. $(VENV_BIN)/activate && \
	    ruff format && \
		ruff check --fix

.PHONY: test tests
test tests: $(VENV)/pyvenv.cfg
	. $(VENV_BIN)/activate && \
		pytest --cov=$(PY_IMPORT) $(T) $(TEST_ARGS) && \
		python -m coverage report -m $(COV_ARGS)

.PHONY: doc
doc: $(VENV)/pyvenv.cfg
	. $(VENV_BIN)/activate && \
		pdoc -o html $(PY_IMPORT)

.PHONY: package
package: $(VENV)/pyvenv.cfg
	uvx --from build pyproject-build --installer uv

.PHONY: edit
edit:
	$(EDITOR) $(ALL_PY_SRCS)
