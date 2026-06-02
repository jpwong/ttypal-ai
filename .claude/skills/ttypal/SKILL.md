---
name: ttypal
description: "Operate serial ports via ttypal. Use when the user needs to send commands to a device over UART/serial, read serial console output, debug embedded Linux boards, interact with a development board, or diagnose serial communication. Also for 'send command to board', 'check serial output', 'what is the board printing', 'run this on the device'."
allowed-tools: Bash(ttypal-send *) Bash(ttypal-tail *) Bash(ttypal-daemon *) Bash(ttypal-xfer *)
tags:
  - serial
  - uart
  - embedded
  - debug
  - console
---

# ttypal — Serial Port Debug Tool for AI

You have access to a serial port debug tool called ttypal. It lets you send commands to embedded devices and read their output through UART.

## Prerequisites

ttypal must be installed (`pip install ttypal-ai`) and a ttypal session must be active. The user may run ttypal in **two modes**:

1. **Daemon mode** — `ttypal-daemon start -b <board>` runs in background, `ttypal-daemon status` reports it.
2. **Interactive mode** — user runs `ttypal` directly in another terminal. `ttypal-daemon status` will report "not running" even though the session is active and the socket is available.

**How to check:** Run `ttypal-daemon status` once. If it reports not running, **ask the user if they already have ttypal open interactively** before trying to start a daemon. If the user confirms an active session (e.g. "already opened", "running interactively", "it's up"), **skip daemon startup and proceed directly** with `ttypal-tail` and `ttypal-send` — they work the same in both modes.

To see available board configs: `ttypal-daemon start` (shows selection menu, not suitable for non-interactive use — use `-b` flag).

## Sending commands

```bash
# Probe device state (send Enter, return response)
ttypal-send --probe

# Fire-and-forget (no response needed)
ttypal-send "reboot"

# Send and wait for response (PREFERRED for most commands)
ttypal-send --wait "# " "uname -a"

# With custom timeout (default 10s)
ttypal-send --wait "# " --timeout 30 "long_running_command"

# Wait for a string to appear BEFORE sending (for login, prompts, etc.)
ttypal-send --wait-for "login:" "root"
ttypal-send --wait-for "Password:" "mypassword"

# Combine: wait for string, send, then wait for prompt
ttypal-send --wait-for "login:" --wait "Password:" "root"
ttypal-send --wait-for "Password:" --wait "# " "mypassword"

# Specify socket if multiple boards are connected
ttypal-send --socket /tmp/ttypal-myboard.sock "ls"
```

### Login sequence

For devices that require login, use `--wait-for` to synchronize with the login prompts:

```bash
# Step 1: wait for login prompt, then send username
ttypal-send --wait-for "login:" "root"
# Step 2: wait for password prompt, then send password
ttypal-send --wait-for "Password:" --wait "# " "mypassword"
```

**Do NOT** blindly send username/password with sleep — use `--wait-for` to ensure proper sequencing.

### Prompt matching

The `--wait` flag takes the shell prompt string. Common prompts:
- `"# "` — root shell
- `"$ "` — normal user shell
- `"root@hostname:/"` — full prompt (more reliable but board-specific)

**IMPORTANT**: If the command output contains the prompt string (e.g., script output containing `#`), use the full prompt like `"root@boardname:/"` to avoid premature matching.

## Reading serial output / logs

```bash
# Last 20 lines (default)
ttypal-tail

# Last N lines
ttypal-tail -n 50

# Follow mode (like tail -f)
ttypal-tail -f

# Specific board's logs
ttypal-tail -b myboard
```

## Stopping the daemon

```bash
ttypal-daemon stop
# or for a specific board:
ttypal-daemon stop -b myboard
```

## Capability boundaries — READ THIS

1. **File transfer uses ZMODEM over serial.** Use `ttypal-xfer` for file transfer. It bridges host-side `lrzsz` with the device's `rz`/`sz`. Requires `lrzsz` on host and device.

   ```bash
   # Send file to device
   ttypal-xfer --put local_file.bin

   # Receive file from device
   ttypal-xfer --get /remote/path ./local_dir
   ```

   **Known issue (RK platforms with FIQ debugger):** ZMODEM transfers may trigger FIQ debugger — both file data and protocol frames (CRC, headers) can contain the trigger sequence. No effective software workaround exists. Files <100KB generally reliable; larger files increasingly likely to trigger `debug>` mode (send `console` to recover). For large files, use TFTP/SCP via network or disable FIQ debugger (`no_fiq_debugger` boot param).

2. **Long output may be unreliable.** Commands that produce hundreds of lines (like `cat` of large files) may have data interleaved with background device messages. For large outputs, prefer writing results to a file on the device and transferring via network.

3. **Background prints are normal.** The device may print kernel messages or application logs at any time. These appear interleaved in `ttypal-tail` output. This is expected serial console behavior, not a bug.

4. **Prompt matching is best-effort.** The `send_wait` mechanism searches the log for the command echo and the next prompt occurrence. It works well for short commands with clean output but may fail for commands that produce output containing the prompt string.

## Typical AI workflow

```bash
# 1. Check if daemon is running
ttypal-daemon status

# 2. If not running, ASK the user first — they may already have ttypal open interactively.
#    Only start daemon if user confirms no active session:
ttypal-daemon start -b myboard

# 3. Probe device state (what prompt comes back?)
ttypal-send --probe

# 4. Based on probe result, login if needed or proceed with commands
ttypal-send --wait "# " "uname -a"
ttypal-send --wait "# " "cat /etc/os-release"

# 5. Read recent logs
ttypal-tail -n 30
```
