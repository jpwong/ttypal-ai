---
description: "Operate serial ports via ttypal. Use when the user needs to send commands to a device over UART/serial, read serial console output, debug embedded Linux boards, interact with a development board, or diagnose serial communication. Also for 'send command to board', 'check serial output', 'what is the board printing', 'run this on the device'."
allowed-tools: Bash(ttypal-send *) Bash(ttypal-tail *) Bash(ttypal-daemon *) Bash(ttypal-xfer *)
---

# ttypal — Serial Port Debug Tool for AI

You have access to a serial port debug tool called ttypal. It lets you send commands to embedded devices and read their output through UART.

## Prerequisites

ttypal must be installed (`pip install ttypal-ai`) and a daemon must be running. Check status first:

```bash
ttypal-daemon status
```

If not running, start it:

```bash
ttypal-daemon start -b <board-name>
```

To see available board configs: `ttypal-daemon start` (shows selection menu, not suitable for non-interactive use — use `-b` flag).

## Sending commands

```bash
# Fire-and-forget (no response needed)
ttypal-send "reboot"

# Send and wait for response (PREFERRED for most commands)
ttypal-send --wait "# " "uname -a"

# With custom timeout (default 10s)
ttypal-send --wait "# " --timeout 30 "long_running_command"

# Specify socket if multiple boards are connected
ttypal-send --socket /tmp/ttypal-myboard.sock "ls"
```

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

   **Known issue (RK platforms):** ZMODEM binary data may trigger FIQ debugger. If board enters `debug>` prompt, send `console` to recover. For large binary transfers, consider TFTP/SCP via network instead.

2. **Long output may be unreliable.** Commands that produce hundreds of lines (like `cat` of large files) may have data interleaved with background device messages. For large outputs, prefer writing results to a file on the device and transferring via network.

3. **Background prints are normal.** The device may print kernel messages or application logs at any time. These appear interleaved in `ttypal-tail` output. This is expected serial console behavior, not a bug.

4. **Prompt matching is best-effort.** The `send_wait` mechanism searches the log for the command echo and the next prompt occurrence. It works well for short commands with clean output but may fail for commands that produce output containing the prompt string.

## Typical AI workflow

```bash
# 1. Check if daemon is running
ttypal-daemon status

# 2. Start if needed
ttypal-daemon start -b myboard

# 3. Explore the device
ttypal-send --wait "# " "uname -a"
ttypal-send --wait "# " "cat /etc/os-release"
ttypal-send --wait "# " "ps aux"

# 4. Read recent logs
ttypal-tail -n 30

# 5. When done, stop daemon
ttypal-daemon stop
```
