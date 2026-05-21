# ttypal-ai

Serial port debug tool for humans and AI agents. PyPI package: `ttypal-ai`, CLI commands: `ttypal`.

## Project Structure

```
ttypal/                     # Python module
├── __init__.py
├── main.py                 # ttypal entry (interactive terminal)
├── config.py               # Board config (TOML, ~/.config/ttypal/boards/)
├── serial_conn.py          # pyserial wrapper with flock multi-instance prevention
├── terminal.py             # Interactive terminal (tty raw mode, Ctrl-T escape)
├── logger.py               # Timestamped logging with size-based rotation
├── socket_server.py        # Unix domain socket for external command injection
├── recorder.py             # Record raw RX/TX byte streams (JSONL format)
├── replay_backend.py       # Replay backend, replaces real serial for testing
├── cli_send.py             # ttypal-send command
├── cli_tail.py             # ttypal-tail command
└── cli_headless.py         # ttypal-daemon command (background daemon)

tests/
├── fixtures/               # .rec files recorded from real rockchip board
├── test_config.py          # Unit: config read/write
├── test_logger.py          # Unit: timestamp and rotation
├── test_recorder.py        # Unit: recording and ring buffer
├── test_replay.py          # Unit: replay backend
├── test_integration.py     # Integration: socket → serial → logger
├── test_ai_e2e.py          # E2E: AI sends command, verifies correct response
├── test_regression.py      # Regression: real device recording replay
└── record_fixtures.py      # Helper: record test data from board

skills/ttypal/SKILL.md      # Claude Code skill definition
.claude-plugin/plugin.json  # Claude Code plugin manifest
```

## Development

```bash
# Virtual environment (pytest lives here)
source ~/ttypal/.venv/bin/activate
pytest tests/ -v

# System-level editable install (daily CLI use)
pip install -e . --break-system-packages

# Release to PyPI
python -m build && twine upload dist/*
# twine is installed via pipx (isolated)
```

## Key Design Decisions

### Serial Port Locking
`serial_conn.py` uses flock on `/tmp/ttypal-<port>.lock` to prevent multiple instances from opening the same port. Lock auto-releases on process exit.

### send_wait Prompt Matching
`socket_server.py` `_wait_for_prompt_after_cmd()` logic:
1. Search the log file for the command echo text
2. Find the next prompt occurrence after the echo
3. Return everything in between

**Known issue:** If command output contains the prompt string (e.g. `#`), it truncates early. Use full prompt (e.g. `root@rockchip:/`) to mitigate.

### Capability Boundary
**No file transfer over serial.** Background prints (kernel messages, app logs) corrupt the data stream. Use TFTP/SCP for file transfer.

### Recording Format
JSONL, one event per line: `{"t": seconds, "dir": "rx"|"tx", "hex": "hexstring"}`

### Config Location
`~/.config/ttypal/boards/<name>.toml`, default timestamp format `%y%m%d %H:%M:%S.%f`

## Git Commit Convention

Conventional Commits: `type(scope): subject`

type: feat, fix, refactor, docs, style, perf, test, chore, ci
scope: serial, config, socket, cli, logger, record, test

## Test Board

- RK3562 EVB2 (Rockchip), Buildroot, aarch64
- Serial: /dev/ttyUSB1, 1500000 baud
- Config name: `1.5m`
- Board IP: 2.0.0.30 (TFTP server running)
- Main apps: inOne (audio DSP), ctrl_server, ptp4l

## Current Version

v0.1.0, published to PyPI (ttypal-ai)

## TODO

- send_wait prompt matching is fragile with output containing `#`
- Replay TX-triggered mode (currently plays RX sequentially, ignores input)
- CI/CD pipeline (GitHub Actions)
