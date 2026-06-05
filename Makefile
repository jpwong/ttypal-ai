VENV    := $(HOME)/ttypal/.venv
PYTEST  := $(VENV)/bin/pytest
PYTHON  := $(VENV)/bin/python
PIP     := $(VENV)/bin/pip

.PHONY: test test-unit test-e2e install build release version

test:
	$(PYTEST) tests/ -v

test-unit:
	$(PYTEST) tests/ -v \
		--ignore=tests/test_cli_e2e.py \
		--ignore=tests/test_regression.py \
		--ignore=tests/test_ai_e2e.py

test-e2e:
	$(PYTEST) tests/test_cli_e2e.py -v

install:
	$(PIP) install -e .

build:
	$(PYTHON) -m build

release: build
	@echo "Checking version consistency..."
	@INIT_VER=$$($(PYTHON) -c "from ttypal import __version__; print(__version__)"); \
	TOML_VER=$$($(PYTHON) -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"); \
	if [ "$$INIT_VER" != "$$TOML_VER" ]; then \
		echo "Version mismatch: __init__.py=$$INIT_VER pyproject.toml=$$TOML_VER"; \
		exit 1; \
	fi; \
	echo "Version $$INIT_VER OK"
	twine upload dist/*
	echo y | cskills publish .claude/skills/ttypal

version:
	@$(PYTHON) -c "from ttypal import __version__; print(__version__)"
