# ttypal-ai

PyPI: `ttypal-ai` | CLI: `ttypal`, `ttypal-send`, `ttypal-tail`, `ttypal-daemon`, `ttypal-xfer`

## Development

| Command | Description |
|---------|-------------|
| `make test` | Run all automated tests |
| `make test-unit` | Unit tests only (fast, no subprocess/CLI tests) |
| `make test-e2e` | CLI e2e tests only |
| `make install` | Editable install in venv |
| `make build` | Build distribution packages (sdist + wheel) |
| `make release` | Full release: version check → build → PyPI upload → cskills publish |
| `make version` | Print current version |

### Testing Workflow (MANDATORY before any commit)

1. **`make test`** — all tests must pass
2. **Real machine regression** — ask user if hardware testing is possible; if yes, run relevant cases from @docs/manual-test-cases.md
3. **Record new test cases** — when bugs or edge cases are discovered, add them to @docs/test-cases.md or @docs/manual-test-cases.md

### Release Workflow

1. Bump version in three places:
   - `ttypal/__init__.py` — `__version__ = "X.Y.Z"`
   - `pyproject.toml` — `version = "X.Y.Z"`
   - This file — Current Version section below
2. `make test` — all tests pass
3. `git add -A && git commit -m "chore: bump version to X.Y.Z"`
4. `make release` — build, upload to PyPI, publish cskills
5. `git tag vX.Y.Z && git push --tags`

## Conventions

### Git Commits

Conventional Commits format: `type(scope): subject`

- **type**: feat, fix, refactor, docs, style, perf, test, chore, ci
- **scope**: serial, config, socket, cli, logger, record, test, xfer, session, macro

### Documentation Maintenance

Every feature change MUST include a documentation scan:

1. Scan repo for docs referencing the changed functionality
2. Update all affected: README.md, AGENTS.md, `.claude/skills/ttypal/SKILL.md`, `docs/*.md`
3. New test cases → update @docs/test-cases.md
4. New manual test scenarios → update @docs/manual-test-cases.md

## Documentation Index

- @docs/architecture.md — project structure, design decisions, known issues
- @docs/test-cases.md — automated test case descriptions (38 cases)
- @docs/manual-test-cases.md — real machine test cases for regression
- @docs/zmodem-bench.md — ZMODEM performance report
- @docs/linux.md — Linux installation guide
- @docs/macos.md — macOS installation guide
- @.claude/skills/ttypal/SKILL.md — AI skill definition for serial port operations

## Current Version

v0.4.5
