# ttypal-ai

PyPI: `ttypal-ai` | CLI: `ttypal`, `ttypal-send`, `ttypal-tail`, `ttypal-daemon`, `ttypal-xfer`

## Development

```bash
source ~/ttypal/.venv/bin/activate && pytest tests/ -v   # test
pip install -e . --break-system-packages                  # install
python -m build && twine upload dist/*                    # release (twine via pipx)
```

## Conventions

### Git Commits
Conventional Commits: `type(scope): subject`

type: feat, fix, refactor, docs, style, perf, test, chore, ci
scope: serial, config, socket, cli, logger, record, test, xfer

### Documentation Maintenance
Every feature change MUST include a documentation scan:
1. Scan repo for docs referencing the changed functionality
2. Update all affected: CLAUDE.md, README.md, .claude/skills/ttypal/SKILL.md, docs/*.md
3. New test cases → update docs/test-cases.md
4. New manual test scenarios → update docs/manual-test-cases.md

## Documentation Index

- [docs/architecture.md](docs/architecture.md) — project structure, design decisions, known issues
- [docs/test-cases.md](docs/test-cases.md) — test case descriptions (38 cases)
- [docs/manual-test-cases.md](docs/manual-test-cases.md) — real machine test cases for regression
- [docs/zmodem-bench.md](docs/zmodem-bench.md) — ZMODEM performance report (1.5M baud)
- [docs/linux.md](docs/linux.md) — Linux installation guide
- [docs/windows-wsl.md](docs/windows-wsl.md) — Windows installation guide (WSL2 + usbipd-win)
- [docs/macos.md](docs/macos.md) — macOS installation guide
- [.claude/skills/ttypal/SKILL.md](.claude/skills/ttypal/SKILL.md) — Claude Code skill definition

## Current Version

v0.3.0
