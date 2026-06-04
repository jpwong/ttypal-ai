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

## Multi-board

When multiple boards are connected, all commands use `-b BOARD` to select which board to target:

```bash
# Discover active instances
ls /tmp/ttypal-*.sock    # socket filename suffix = board name

# Use -b with all commands
ttypal-send -b myboard --probe
ttypal-tail -b myboard -n 20
ttypal-xfer -b myboard --put file.bin
```

If only one instance is running, `-b` is optional — commands auto-detect it. If multiple instances are running and `-b` is omitted, commands will error with a list of available boards.

The `--socket` flag is available as a low-level override (e.g. for non-standard socket paths), but `-b` is the preferred interface.

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

# Specify board if multiple boards are connected
ttypal-send -b myboard "ls"
```

### Login sequence

**Step 1: Decide if login is needed — use `--probe` first**

```bash
ttypal-send -b <board> --probe
```

Interpret the response:
- Returns a shell prompt (`# `, `$ `, or `root@host:/`) → **already logged in, skip login**
- Returns `login:` → need full login (username + password)
- Returns `Password:` → username already entered, only password needed
- Returns nothing / blank → device may be off or serial disconnected, ask user

**Do NOT** blindly send login credentials — if already at a shell, sending "root" as a command will confuse the session.

**Step 2: Login with `--wait-for`**

```bash
# Full login (login: prompt detected)
ttypal-send --wait-for "login:" --wait "Password:" "root"
ttypal-send --wait-for "Password:" --wait "# " "mypassword"

# Only password needed (Password: prompt detected)
ttypal-send --wait-for "Password:" --wait "# " "mypassword"
```

**Step 3: Verify login succeeded**

```bash
ttypal-send -b <board> --probe
```

If response shows `# ` or `$ `, login succeeded. If `Login incorrect` or `login:` appears again, login failed.

**Login failure handling:**

- Retry at most **3 times** (password may have been mistyped, or serial noise corrupted input)
- Between retries, reset state by sending Ctrl-C then probing again:
  ```bash
  ttypal-send $'\x03'          # send Ctrl-C to clear any partial input
  ttypal-send -b <board> --probe
  ```
- After 3 failures, **stop and report to user** — do not keep retrying. The user needs to check: correct password, serial baud rate, device state.

### `--wait-for` behavior

- Default timeout: **10s** (override with `--timeout N`)
- On timeout: the command is **not sent**, and `ttypal-send` exits with error (exit code 1)
- If the target string is already present in recent output, it matches immediately

Common pitfall: if the device is already at a shell prompt and you run `--wait-for "login:"`, it will wait 10s then fail. Always probe first (Step 1).

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

   # Specify board if multiple boards are connected
   ttypal-xfer -b myboard --put local_file.bin
   ```

   **Known issue (RK platforms with FIQ debugger):** ZMODEM transfers may trigger FIQ debugger — both file data and protocol frames (CRC, headers) can contain the trigger sequence. No effective software workaround exists. Files <100KB generally reliable; larger files increasingly likely to trigger `debug>` mode (send `console` to recover). For large files, use TFTP/SCP via network or disable FIQ debugger (`no_fiq_debugger` boot param).

2. **Long output may be unreliable.** Commands that produce hundreds of lines (like `cat` of large files) may have data interleaved with background device messages. For large outputs, prefer writing results to a file on the device and transferring via network.

3. **Background prints are normal.** The device may print kernel messages or application logs at any time. These appear interleaved in `ttypal-tail` output. This is expected serial console behavior, not a bug.

4. **Prompt matching is best-effort.** The `send_wait` mechanism searches the log for the command echo and the next prompt occurrence. It works well for short commands with clean output but may fail for commands that produce output containing the prompt string.

## Typical AI workflow

```bash
# 1. Discover active instances
ls /tmp/ttypal-*.sock    # if multiple, note the board names (suffix after ttypal-)

# 2. Check if daemon is running
ttypal-daemon status

# 3. If not running, ASK the user first — they may already have ttypal open interactively.
#    Only start daemon if user confirms no active session:
ttypal-daemon start -b myboard

# 4. Probe device state (what prompt comes back?)
ttypal-send -b myboard --probe       # use -b if multiple boards

# 5. Based on probe result, login if needed or proceed with commands
ttypal-send -b myboard --wait "# " "uname -a"
ttypal-send -b myboard --wait "# " "cat /etc/os-release"

# 6. Read recent logs
ttypal-tail -b myboard -n 30
```
