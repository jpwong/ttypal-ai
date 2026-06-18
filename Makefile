VENV    := $(HOME)/ttypal/.venv
PYTEST  := $(VENV)/bin/pytest
PYTHON  := $(VENV)/bin/python
PIP     := $(VENV)/bin/pip
VERSION := $(shell $(PYTHON) -c "from ttypal import __version__; print(__version__)")
CSKILL_PATH := .agents/skills/ttypal

.PHONY: test test-unit test-e2e install build clean-dist check-version publish-cskill release version

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

clean-dist:
	rm -rf dist/*

check-version:
	@echo "Checking version consistency..."
	@INIT_VER=$$($(PYTHON) -c "from ttypal import __version__; print(__version__)"); \
	TOML_VER=$$($(PYTHON) -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"); \
	if [ "$$INIT_VER" != "$$TOML_VER" ]; then \
		echo "Version mismatch: __init__.py=$$INIT_VER pyproject.toml=$$TOML_VER"; \
		exit 1; \
	fi; \
	echo "Version $$INIT_VER OK"

publish-cskill:
	@BASE_TAG=$$(git describe --tags --abbrev=0 --match 'v*' HEAD^ 2>/dev/null || true); \
	CHANGED=0; \
	if [ -z "$$BASE_TAG" ]; then \
		echo "No previous version tag found; cskill will be published."; \
		CHANGED=1; \
	elif ! git diff --quiet "$$BASE_TAG"..HEAD -- $(CSKILL_PATH); then \
		echo "cskill changed since $$BASE_TAG."; \
		CHANGED=1; \
	fi; \
	if ! git diff --quiet -- $(CSKILL_PATH); then \
		echo "cskill has uncommitted changes."; \
		CHANGED=1; \
	fi; \
	if [ -n "$$(git ls-files --others --exclude-standard -- $(CSKILL_PATH))" ]; then \
		echo "cskill has untracked files."; \
		CHANGED=1; \
	fi; \
	if [ "$$CHANGED" = "0" ]; then \
		echo "cskill unchanged; skipping cskills publish."; \
	else \
		echo "Publishing cskill."; \
		echo y | cskills publish $(CSKILL_PATH); \
	fi

release: check-version clean-dist build
	twine upload dist/ttypal_ai-$(VERSION)*
	$(MAKE) publish-cskill

version:
	@$(PYTHON) -c "from ttypal import __version__; print(__version__)"
