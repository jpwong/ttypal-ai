# ttypal

Serial port debug tool designed for both humans and AI agents.

## Features

- Interactive terminal (like minicom, but better)
- Auto-logging with timestamps and rotation
- External command injection via Unix socket (for AI/scripts)
- ZMODEM file transfer over serial
- Record/replay serial sessions
- Board config management
- Claude Code skill for AI-driven serial debugging

## Install

```bash
pip install ttypal-ai
```

Platform-specific setup:

- [Linux](docs/linux.md) — 原生支持，需配置串口权限
- [macOS](docs/macos.md) — 原生支持，即插即用（未测试）
- [Windows](docs/windows-wsl.md) — 通过 WSL2 + usbipd-win 运行（未测试）

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

Clone this repo and open it with Claude Code — the `/ttypal` skill loads automatically from `.claude/skills/`.

```bash
cd /path/to/ttypal-ai
claude
# Then use /ttypal skill or just ask AI to operate the serial port
```

## License

MIT
