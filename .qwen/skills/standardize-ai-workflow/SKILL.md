---
name: standardize-ai-workflow
description: Standardize test/build/release workflows for AI agents using AGENTS.md + Makefile
source: auto-skill
extracted_at: '2026-06-05T03:32:42.906Z'
---

# Standardize AI Agent Workflows

When a project has scattered instructions across tool-specific files (CLAUDE.md, QWEN.md, etc.) or manual workflows that require repeated reminders, consolidate into AGENTS.md + Makefile.

## Key Insight: AGENTS.md is Universal

Both Claude Code and Qwen Code read `AGENTS.md` by default:
- **Claude Code**: Reads CLAUDE.md, AGENTS.md, QWEN.md
- **Qwen Code**: Reads QWEN.md (default), AGENTS.md, CLAUDE.md

Using `AGENTS.md` as the primary file means one source of truth for both tools.

## Migration Pattern

1. **Audit existing files**: Check for CLAUDE.md, QWEN.md, README sections with dev instructions
2. **Extract conventions**: Pull out testing requirements, git commit format, release steps
3. **Create AGENTS.md** with:
   - Quick reference table of make commands
   - MANDATORY workflows (testing before commits, release checklist)
   - Documentation maintenance rules
   - Links to detailed docs using `@path/to/file.md` syntax
4. **Delete tool-specific files** (CLAUDE.md, QWEN.md) if AGENTS.md covers everything
5. **Verify both tools load it**: Check footer context file count in Qwen Code, test in Claude Code

## Makefile Structure for Python Projects

```makefile
VENV    := $(HOME)/path/to/.venv
PYTEST  := $(VENV)/bin/pytest
PYTHON  := $(VENV)/bin/python
PIP     := $(VENV)/bin/pip

test:
	$(PYTEST) tests/ -v

test-unit:
	$(PYTEST) tests/ -v --ignore=tests/test_e2e.py

install:
	$(PIP) install -e .

build:
	$(PYTHON) -m build

release: build
	@echo "Checking version consistency..."
	@INIT_VER=$$($(PYTHON) -c "from pkg import __version__; print(__version__)"); \
	TOML_VER=$$($(PYTHON) -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"); \
	if [ "$$INIT_VER" != "$$TOML_VER" ]; then \
		echo "Version mismatch: __init__.py=$$INIT_VER pyproject.toml=$$TOML_VER"; \
		exit 1; \
	fi
	twine upload dist/*

version:
	@$(PYTHON) -c "from pkg import __version__; print(__version__)"
```

## AGENTS.md Template

```markdown
# project-name

## Development

| Command | Description |
|---------|-------------|
| `make test` | Run all automated tests |
| `make test-unit` | Unit tests only |
| `make build` | Build distribution |
| `make release` | Full release workflow |

### Testing Workflow (MANDATORY)
1. `make test` — must pass
2. [Any additional verification steps]
3. Record new test cases in docs/

### Release Workflow
1. Bump version in: pkg/__init__.py, pyproject.toml, this file
2. `make test`
3. `git commit -m "chore: bump version to X.Y.Z"`
4. `make release`
5. `git tag vX.Y.Z`

## Conventions

### Git Commits
Conventional Commits: `type(scope): subject`

### Documentation Maintenance
Every feature change MUST update relevant docs.

## Documentation Index
- @docs/architecture.md — project structure
- @docs/test-cases.md — test descriptions
```

## Verification Checklist

- [ ] `make test` passes all tests
- [ ] `make build` produces artifacts in dist/
- [ ] AI tools load AGENTS.md (check context file count)
- [ ] Version consistency check works in Makefile

## Common Pitfalls

- **Venv path**: Use absolute path with `$(HOME)` for portability
- **Missing tools**: Install build/twine in venv: `pip install build twine`
- **@ syntax**: Use `@path/to/file.md` in AGENTS.md to import other docs
- **Git ignore**: Ensure dist/ is in .gitignore before running make build
