# ttypal

Serial port debug tool designed for both humans and AI agents.

## Features

- Interactive terminal (like minicom, but better)
- Auto-logging with timestamps and rotation
- External command injection via Unix socket (for AI/scripts)
- Record/replay serial sessions
- Board config management
- Claude Code plugin for AI-driven serial debugging

## Install

```bash
pip install ttypal
```

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

## Claude Code Integration

```bash
claude --plugin-dir /path/to/ttypal
# Then use /ttypal skill or just ask AI to operate the serial port
```

## License

MIT
