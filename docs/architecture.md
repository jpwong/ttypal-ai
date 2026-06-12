# ttypal-ai 架构与设计

Serial port debug tool for humans and AI agents. PyPI package: `ttypal-ai`, CLI commands: `ttypal`.

## Project Structure

```
ttypal/                     # Python module
├── __init__.py
├── main.py                 # ttypal entry (interactive terminal)
├── config.py               # Board config (TOML, ~/.config/ttypal/boards/)
├── session.py              # Session metadata (/tmp/ttypal-*.session)
├── serial_conn.py          # pyserial wrapper with flock + pause/resume
├── terminal.py             # Interactive terminal (tty raw mode, Ctrl-T escape)
├── logger.py               # Logging with session marker, optional timestamps, rotation
├── socket_server.py        # Unix domain socket for command injection + ZMODEM transfer
├── recorder.py             # Record raw RX/TX byte streams (JSONL format)
├── replay_backend.py       # Replay backend, replaces real serial for testing
├── cli_send.py             # ttypal-send command
├── cli_tail.py             # ttypal-tail command (cross-file, session-bounded)
├── cli_xfer.py             # ttypal-xfer command (ZMODEM file transfer)
├── cli_headless.py         # ttypal-daemon command (background daemon)
├── macro.py                # F1-F12 macro recording and playback
├── xmodem_transfer.py      # XMODEM transfer (deprecated, kept for reference)
└── zmodem_transfer.py      # ZMODEM transfer via lrzsz bridge

tests/
├── fixtures/               # .rec files recorded from real rockchip board
├── test_config.py          # Unit: config read/write
├── test_logger.py          # Unit: timestamp, rotation, session marker
├── test_recorder.py        # Unit: recording and ring buffer
├── test_replay.py          # Unit: replay backend
├── test_tail.py            # Unit: tail cross-file, session boundary, daemon detection
├── test_macro.py           # Unit: macro load, playback, recording, save
├── test_integration.py     # Integration: socket → serial → logger
├── test_ai_e2e.py          # E2E: AI sends command, verifies correct response
├── test_regression.py      # Regression: real device recording replay
└── record_fixtures.py      # Helper: record test data from board

docs/
├── architecture.md         # This file
├── zmodem-bench.md         # ZMODEM performance test report
└── test-cases.md           # Test case documentation

.claude/skills/ttypal/SKILL.md  # Claude Code skill definition
```

## Key Design Decisions

### Board vs Session
Two distinct concepts:
- **Board (Profile)**: `-b/--board` — a saved TOML config describing how to connect to a type of board (baudrate, prompt, macros). Stored in `~/.config/ttypal/boards/`.
- **Session**: `-S/--session` — a running instance, identified by name. Determines socket/pid/log paths. Stored in `/tmp/ttypal-*.session`.

When `-S` is omitted, session name defaults to board name. Client tools (`ttypal-send`, `ttypal-tail`, `ttypal-xfer`) can find sessions by `-S name` directly or by `-b board` (scans session files for matching profile).

### Serial Port Locking
`serial_conn.py` uses flock on `/tmp/ttypal-<port>.lock` to prevent multiple instances from opening the same port. Lock auto-releases on process exit. The lock file may remain in `/tmp`; this is normal because the active lock is tied to the open file descriptor, not the pathname. For multi-user use, ttypal can acquire the flock through a read-only descriptor if another user owns the leftover lock file; writing the PID into the lock file is best-effort only.

### Serial Port Pause/Resume
`serial_conn.py` supports `pause()` / `resume()` to temporarily stop the reader thread from consuming serial data. Used by ZMODEM transfer to exclusively access the serial port during file transfer.

### send_wait Prompt Matching
`socket_server.py` `_wait_for_prompt_after_cmd()` logic:
1. Search the log file for the command echo text
2. Find the next prompt occurrence after the echo
3. Return everything in between

**Known issue:** If command output contains the prompt string (e.g. `#`), it truncates early. Use full prompt (e.g. `root@rockchip:/`) to mitigate.

### File Transfer (ZMODEM)
`zmodem_transfer.py` bridges host-side `lrzsz` (`sz`/`rz`) with the serial port for ZMODEM file transfer. The host needs `lrzsz` installed, the device needs `rz`/`sz` (BusyBox or lrzsz).

Transfer flow: pause reader → flush serial buffer → send `rz`/`sz` command to device → fork lrzsz process → bridge stdio ↔ serial → resume reader.

CLI: `ttypal-xfer --put <file>` / `ttypal-xfer --get <remote_file>`

### Logger Session Marker
Each Logger instance generates a unique `session_id`. Every new log file starts with `## ttypal-session: <session_id>`. This enables `ttypal-tail` to read across rotated log files without crossing session boundaries.

### Logger Timestamps
Timestamps are optional. Set `timestamp_format=""` in config to disable. When enabled, each line is prefixed with `[timestamp]`. Session markers use a distinct prefix (`## ttypal-session:`) that won't collide with log content regardless of timestamp setting.

### Recording Format
JSONL, one event per line: `{"t": seconds, "dir": "rx"|"tx", "hex": "hexstring"}`

### Config Location
`~/.config/ttypal/boards/<name>.toml`, default timestamp format `%y%m%d %H:%M:%S.%f`

## Test Board

- RK3562 EVB2 (Rockchip), Buildroot, aarch64
- Serial: /dev/ttyUSB1, 1500000 baud
- Config name: `1.5m`
- Board IP: 2.0.0.30 (TFTP server running)
- Main apps: inOne (audio DSP), ctrl_server, ptp4l

## TODO

- send_wait prompt matching is fragile with output containing `#`
- Replay TX-triggered mode (currently plays RX sequentially, ignores input)
- CI/CD pipeline (GitHub Actions)
- **已知问题 (RK平台 FIQ Debugger):** ZMODEM 传输中文件数据或协议帧均可能触发 FIQ debugger，目前无有效软件规避方法。文件越大触发概率越高，<100KB 基本可靠，大文件请用网络传输或关闭 FIQ debugger (`no_fiq_debugger`)
