---
name: ttypal
description: "Operate serial ports through ttypal. Use for UART/serial console access, embedded Linux board debugging, sending commands to a board, reading recent serial output, logging in over a serial console, or transferring files over serial."
allowed-tools: Bash(ttypal-send *) Bash(ttypal-tail *) Bash(ttypal-daemon *) Bash(ttypal-xfer *)
tags:
  - serial
  - uart
  - embedded
  - debug
  - console
---

# ttypal - Serial Console Operations for AI Agents

ttypal provides a daemon-owned serial console with command injection, logging,
tailing, and ZMODEM file transfer. The daemon owns the physical serial device;
agents and scripts should talk to the daemon through the Python API or CLI.

## Operating Model

- `ttypal-daemon` owns `/dev/ttyUSB*` and keeps the serial reader/logger alive.
- `TtypalClient` is the preferred API for Python automation and tests.
- `ttypal-send`, `ttypal-tail`, and `ttypal-xfer` are CLI tools for shell-based
  workflows.
- Do not open the serial device directly from Python tests or agent scripts.
- Always identify the target session before sending commands.

## Session Selection

Before sending a command, determine the target session.

1. If the user specified a session (`-S` value) or board profile (`-b` value),
   use it.
2. Otherwise run:

   ```bash
   ttypal-daemon status
   ```

3. If exactly one session is active, confirm with the user before using it.
4. If multiple sessions are active, ask the user which one to use.
5. If no session is active and the user already gave a board profile, start one:

   ```bash
   ttypal-daemon start -b <board> -S <session>
   ```

6. If no board profile is known, ask the user. Do not guess.

Use `-S <session>` for all commands once a session is known. Use `-b <board>`
only when selecting by profile is unambiguous.

## Preferred Python API

Use `TtypalClient` when writing or modifying Python automation, CI tests, or
agent tools.

```python
from ttypal.client import TtypalClient, TtypalTimeoutError

serial = TtypalClient(session="my-session")

try:
    output = serial.send_wait("uname -a", prompt="~ # ", timeout=30)
except TtypalTimeoutError as exc:
    print(f"serial timeout via {exc.socket_path}: {exc.output}")
else:
    print(output)
```

Stable first-version methods:

| Method | Use |
|--------|-----|
| `send(command)` | Send a command without waiting for output |
| `send_wait(command, prompt="# ", timeout=None)` | Send a command and wait for prompt |
| `expect_send(expect, command, timeout=None)` | Wait for text, then send a command |
| `expect_send_wait(expect, command, prompt="# ", timeout=None)` | Wait for text, send a command, then wait for prompt |
| `probe(timeout=2.0)` | Send Enter and return current console response |
| `request(payload, operation_timeout=None, io_timeout=None)` | Send a raw daemon protocol request |

Important exception classes:

- `TtypalSocketNotFound`
- `TtypalSessionError`
- `TtypalConnectionError`
- `TtypalDaemonError`
- `TtypalProtocolError`
- `TtypalTimeoutError`

For prompt timeouts, `TtypalTimeoutError.output` may contain partial output.

## CLI Usage

Use the CLI for manual checks, shell scripts, and quick agent operations.

```bash
# Probe current console state
ttypal-send -S <session> --probe

# Fire-and-forget
ttypal-send -S <session> "reboot"

# Send command and wait for prompt
ttypal-send -S <session> --wait "~ # " --timeout 30 "uname -a"

# Wait for text, then send
ttypal-send -S <session> --wait-for "login:" "root"

# Wait for text, send, then wait for prompt
ttypal-send -S <session> --wait-for "Password:" --wait "~ # " "password"

# Read recent logs
ttypal-tail -S <session> -n 50
```

## Prompt Matching

Prefer the most specific prompt that is stable for the target board.

Good:

```bash
ttypal-send -S <session> --wait "~ # " "uname -m"
ttypal-send -S <session> --wait "root@board:/" "pwd"
```

Risky:

```bash
ttypal-send -S <session> --wait "#" "uname -m"
```

Prompt matching is substring-based. If the board prints `~ # `, matching `#`
or `# ` can work, but it is broad and may match `#` in command output. Use a
full prompt such as `~ # ` when possible.

If a command output may contain the prompt string at the beginning of a line, use
a fuller prompt or a unique completion marker.

## Login Workflow

Always probe before login:

```bash
ttypal-send -S <session> --probe
```

Interpret the response:

- Shell prompt (`#`, `$`, `~ #`, `root@...`) means already logged in.
- `login:` means send the username.
- `Password:` means send only the password.
- Empty output may mean the board is off, disconnected, or quiet.

Do not blindly send credentials. Sending `root` at a shell prompt can execute it
as a command and confuse the session.

Known limitation: `--wait-for` searches recent log content and can match stale
text such as an old `Password:`. If the login state is ambiguous, use `--probe`
and recent logs to confirm the current prompt. For fragile login flows, send one
step at a time and verify with `ttypal-tail`.

## Error Handling

- `ttypal-send --wait ...` exits non-zero when the prompt times out.
- Python callers should catch `TtypalTimeoutError` and inspect `exc.output`.
- Socket connection failures usually mean the daemon is not running, not
  reachable, or owned by another user.
- If `ttypal-daemon status` says a session is running but `ttypal-send` cannot
  connect, treat the session as unhealthy and report the PID/socket/owner to the
  user.

## File Transfer

Use `ttypal-xfer` for ZMODEM over serial.

```bash
# Send local file to device
ttypal-xfer -S <session> --put local_file.bin

# Receive remote file from device
ttypal-xfer -S <session> --get /remote/path ./local_dir
```

Requirements:

- Host needs `lrzsz`.
- Device needs `rz`/`sz`.

Known RK/FIQ debugger limitation: ZMODEM data can trigger the FIQ debugger on
some Rockchip platforms. Small files are more reliable. For large files, prefer
network transfer such as TFTP/SCP, or disable FIQ debugger when appropriate.

## Practical Rules

- Use one serial command at a time. Do not run multiple `ttypal-send --wait`
  commands in parallel against the same session.
- Prefer `TtypalClient` for Python code and `ttypal-send` for shell workflows.
- Use `ttypal-tail -S <session> -n 50` to inspect state after unexpected output.
- Stop after repeated login failures and ask the user to verify credentials,
  baud rate, and board state.
- Do not hide partial output from failures; it is often the most useful debug
  signal.
