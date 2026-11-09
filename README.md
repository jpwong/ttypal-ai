# ttypal

Serial port debug tool designed for both humans and AI agents.

## Features

- Interactive terminal (like minicom, but better)
- Auto-logging with timestamps and rotation
- Terminal-safe control-byte escaping (`SO`/`SI` and other C0 bytes shown as
  `^N`/`^O`; `--raw` disables it)
- External command injection via Unix socket (for AI/scripts)
- ZMODEM file transfer over serial
- Record/replay serial sessions
- Macro recording and playback (F1-F12 hotkeys)
- Board config management
- AI agent skill for serial debugging

## Install

```bash
pip install ttypal-ai
```

Platform-specific setup:

- [Linux](docs/linux.md) - Native support; serial port permissions required
- [macOS](docs/macos.md) - Native plug-and-play support (untested)
- [Windows](docs/windows-wsl.md) - Run through WSL2 + usbipd-win (untested)

## Quick Start

```bash
# Interactive mode
ttypal

# Headless daemon (for AI automation)
ttypal-daemon start -b myboard

# Send commands from another process
ttypal-send --wait "# " "uname -a"

# Read recent serial output
ttypal-tail -n 50
```

## Terminal-safe output

Board output and log *display* are rendered through a control-byte filter. A
stray `SO` (`0x0E`) would otherwise leave the terminal stuck in DEC Special
Graphics; other unsafe C0 bytes and DEL are shown in caret notation (`^N`,
`^O`, `^?`, ...). `CR`, `LF`, `TAB`, `BS`, `BEL` and `ESC` (ANSI sequences)
pass through unchanged.

Log files themselves are not caret-escaped, so `SO`/`SI` remain available for
debugging. Note that the logger decodes UTF-8 with replacement; use `--record`
when you need lossless binary capture. `ESC` is passed through by default,
including DEC charset designations, so this is not a full sandbox for arbitrary
binary output.

Use `--raw` on `ttypal`, `ttypal-send` or `ttypal-tail` to disable caret
escaping. `--raw` is not a lossless capture path: `ttypal-send` output may still
have ANSI sequences/timestamps normalized by the daemon, and `ttypal-tail
--raw` can feed control bytes to the terminal again. The interactive terminal
can enable raw mode permanently in the board config (`--no-raw` overrides it):

```toml
[terminal]
raw = true
```

## Python API

Use `TtypalClient` from Python tests and automation code to talk to a running
`ttypal-daemon` without spawning `ttypal-send` for every operation.

```python
from ttypal.client import TtypalClient, TtypalTimeoutError

serial = TtypalClient(session="myboard")

try:
    output = serial.send_wait("uname -a", prompt="# ", timeout=30)
except TtypalTimeoutError as exc:
    print(f"timed out via {exc.socket_path}: {exc.output}")
else:
    print(output)
```

Stable first-version methods:

| Method | Purpose |
|--------|---------|
| `send(command)` | Send a command without waiting for output |
| `send_wait(command, prompt="# ", timeout=None)` | Send a command and return output collected until prompt |
| `expect_send(expect, command, timeout=None)` | Wait for text, then send a command |
| `expect_send_wait(expect, command, prompt="# ", timeout=None)` | Wait for text, send a command, then wait for prompt |
| `probe(timeout=2.0)` | Send Enter and return the current console response |
| `request(payload, operation_timeout=None, io_timeout=None)` | Send a raw daemon protocol request |

## Macros

Bind command sequences to F1-F12 keys in your board config:

```toml
[macro]
F1 = ["echo hello", "sleep 0.5", "ls -la"]
F2 = ["reboot"]
```

Or record interactively: `Ctrl-T r` to start, `Ctrl-T s` to stop and save.

## AI Agent Integration

Clone this repo and point your agent runtime at the reusable skill in
`.agents/skills/ttypal/`.

```bash
cd /path/to/ttypal-ai
# Then ask your AI agent to operate the serial port with ttypal
```

## License

MIT
