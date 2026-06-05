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

ttypal must be installed (`pip install ttypal-ai`) and a ttypal session must be active.

**How to check:** Run `ttypal-daemon status`. It shows all active sessions (both daemon and interactive mode). If no session is running, **ask the user** which board profile to use, then start one: `ttypal-daemon start -b <board> [-S <session>]`. See "Session Selection" below.

### Board vs Session

- `-b/--board` selects the **board profile** (TOML config with baudrate, prompt, macros, default port).
- `-S/--session` selects the **running session** (socket/pid/log identity). When omitted, session name defaults to board name.
- `--port` and `--baudrate` override profile defaults at daemon start.

## Session Selection — MANDATORY FIRST STEP

Before sending any command, you MUST determine which session to use. Follow this flow:

1. **If the user already specified a session or profile** in their request (e.g. "send command to rk3588", "use session myboard"): use it directly, no need to ask. Proceed to step 4.
2. **Check existing sessions:** Run `ttypal-daemon status`.
3. **If the target is unclear:** **Ask the user** which session to use. Present the list of active sessions. The user may choose one, or choose to start a new session.
   - If no session was selected (none exist, or user chose to start a new one): **ask the user** which board profile to use.
     - You can list available profiles by checking `~/.config/ttypal/boards/` (each `.toml` file is a profile name).
     - After the user confirms, start: `ttypal-daemon start -b <user-chosen-profile> [-S <session-name>]`
4. Proceed with commands.

**NEVER** assume a board profile or silently create a session without explicit user confirmation when the target is ambiguous.

## Multi-board

When multiple boards are connected, use `-S` (session) or `-b` (board profile) to select the target:

```bash
# Discover active sessions
ttypal-daemon status

# Use -S with all commands (preferred when multiple sessions exist)
ttypal-send -S myboard --probe
ttypal-tail -S myboard -n 20
ttypal-xfer -S myboard --put file.bin

# Use -b to find session by profile name (works when only one session uses that profile)
ttypal-send -b rk3588 "uname -a"
```

If only one session is running, `-b` and `-S` are both optional — commands auto-detect it. If multiple sessions are running and neither is specified, commands will error with a list of available sessions.

### Same profile, multiple sessions

When two boards share the same profile (e.g. two RK3588 boards on different USB ports):

```bash
ttypal-daemon start -b rk3588 -S left --port /dev/ttyUSB0
ttypal-daemon start -b rk3588 -S right --port /dev/ttyUSB1

ttypal-send -S left "echo hello"
ttypal-send -S right "echo hello"
```

The `--socket` flag is available as a low-level override (e.g. for non-standard socket paths), but `-S`/`-b` is the preferred interface.

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

# Specify session if multiple boards are connected
ttypal-send -S myboard "ls"
```

### Login sequence

**Step 1: Decide if login is needed — use `--probe` first**

```bash
ttypal-send -S <session> --probe
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
ttypal-send -S <session> --probe
```

If response shows `# ` or `$ `, login succeeded. If `Login incorrect` or `login:` appears again, login failed.

**Login failure handling:**

- Retry at most **3 times** (password may have been mistyped, or serial noise corrupted input)
- Between retries, reset state by sending Ctrl-C then probing again:
  ```bash
  ttypal-send $'\x03'          # send Ctrl-C to clear any partial input
  ttypal-send -S <session> --probe
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

# Specific session's logs
ttypal-tail -S mysession
```

## Stopping the daemon

```bash
ttypal-daemon stop
# or for a specific session:
ttypal-daemon stop -S mysession
```

## Capability boundaries — READ THIS

1. **File transfer uses ZMODEM over serial.** Use `ttypal-xfer` for file transfer. It bridges host-side `lrzsz` with the device's `rz`/`sz`. Requires `lrzsz` on host and device.

   ```bash
   # Send file to device
   ttypal-xfer --put local_file.bin

   # Receive file from device
   ttypal-xfer --get /remote/path ./local_dir

   # Specify session if multiple boards are connected
   ttypal-xfer -S mysession --put local_file.bin
   ```

   **Known issue (RK platforms with FIQ debugger):** ZMODEM transfers may trigger FIQ debugger — both file data and protocol frames (CRC, headers) can contain the trigger sequence. No effective software workaround exists. Files <100KB generally reliable; larger files increasingly likely to trigger `debug>` mode (send `console` to recover). For large files, use TFTP/SCP via network or disable FIQ debugger (`no_fiq_debugger` boot param).

2. **Long output may be unreliable.** Commands that produce hundreds of lines (like `cat` of large files) may have data interleaved with background device messages. For large outputs, prefer writing results to a file on the device and transferring via network.

3. **Background prints are normal.** The device may print kernel messages or application logs at any time. These appear interleaved in `ttypal-tail` output. This is expected serial console behavior, not a bug.

4. **Prompt matching is best-effort.** The `send_wait` mechanism searches the log for the command echo and the next prompt occurrence. It works well for short commands with clean output but may fail for commands that produce output containing the prompt string.

## Typical AI workflow

```bash
# 1. Check active sessions
ttypal-daemon status

# 2. If no session running, ASK USER which profile to use, then start:
ttypal-daemon start -b <user-specified-profile>

# 3. Probe device state (what prompt comes back?)
ttypal-send -S myboard --probe

# 4. Based on probe result, login if needed or proceed with commands
ttypal-send -S myboard --wait "# " "uname -a"
ttypal-send -S myboard --wait "# " "cat /etc/os-release"

# 5. Read recent logs
ttypal-tail -S myboard -n 30
```
