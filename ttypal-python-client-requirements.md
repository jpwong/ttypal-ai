# ttypal Python Client Technical Plan

## Background

The SV15 board-test pipeline starts `ttypal-daemon` to own the serial port and
then calls `ttypal-send` from Python tests through `subprocess.run()`.

The current data path is:

```text
pytest test code -> subprocess -> ttypal-send -> Unix socket -> ttypal-daemon
```

This works, but it couples Python tests to CLI process spawning and CLI stderr /
exit-code parsing. `ttypal-send` does not own the serial port; it only resolves a
daemon socket, sends one JSON request, reads one JSON response, and exits.

The preferred design is:

```text
pytest test code -> TtypalClient -> Unix socket -> ttypal-daemon
```

`ttypal-daemon` remains the only process that opens `/dev/ttyUSB*`. The Python
client becomes the single implementation of socket request/response handling for
CLI tools, CI tests, agent tools, and local board scripts.

## Design Principles

- Prefer the cleanest Python/library API over preserving legacy CLI-internal
  behavior.
- Keep daemon ownership of serial devices unchanged.
- Make socket discovery, request I/O, protocol validation, and daemon errors
  explicit Python concepts.
- Use structured daemon error codes instead of relying on human-readable
  messages.
- Keep high-level client helpers small and predictable.
- Let CLI commands become thin presentation layers over the Python client.
- Treat this work as the pre-v1 API-hardening track for `ttypal-ai`.

## Version Target

The target release for the initial implementation is `v0.9.0`.

`v1.0.0` should be reserved for a later stability milestone after the Python
client has been used broadly enough and reported issues have converged.

Version policy for this feature:

- `v0.9.0` should include the clean Python client design, daemon protocol
  updates, CLI reuse, documentation, and automated tests described here.
- Pre-v1 releases may still make breaking changes if real use shows API or
  protocol problems.
- `v1.0.0` should be cut only after the public `TtypalClient` API, exception
  model, socket discovery behavior, and daemon response schema have been used
  in real projects, documented, tested, and considered stable.
- After `v1.0.0`, changes to `TtypalClient` method signatures, exception
  classes, daemon response `status/code` schema, or documented timeout semantics
  should follow semantic versioning.
- New helper methods may be added in minor versions if they do not change
  existing behavior.
- Breaking changes after v1 should require a major version bump.

The current package version is `v0.9.0`; this plan intentionally allows the
implementation to move through additional pre-v1 releases if needed before
declaring `v1.0.0`.

## Goals

- Add an importable Python client API in `ttypal/client.py`.
- Refactor socket discovery so library code never calls `sys.exit()`.
- Make `ttypal-send` and `ttypal-xfer` reuse the same client request path.
- Let Python tests call `probe`, `send`, `send_wait`, `expect_send`, and
  `expect_send_wait` through normal methods.
- Return structured Python exceptions with useful context.
- Upgrade daemon error responses to include stable error codes and partial
  output where available.
- Clearly separate daemon operation timeout from client socket I/O timeout.

## Non-Goals

- Do not replace `ttypal-daemon`.
- Do not let each pytest process open the serial device directly.
- Do not change the board profile TOML format.
- Do not add tail/status helpers in the first client version.
- Do not redesign prompt matching in this work except for timeout/error
  reporting.

## Public API

Add:

```text
ttypal/client.py
```

Primary use:

```python
from ttypal.client import TtypalClient

serial = TtypalClient(session="sv15-ci-1675880")
output = serial.send_wait("cat /etc/os-release", prompt="# ", timeout=30)
```

Constructor:

```python
TtypalClient(
    *,
    session: str | None = None,
    board: str | None = None,
    socket_path: str | None = None,
    default_timeout: float = 10,
    io_timeout_margin: float = 5,
)
```

Selection rules:

- `socket_path`, `session`, and `board` are mutually exclusive.
- Passing more than one raises `ValueError`.
- Passing none uses automatic discovery.
- `socket_path` is used directly.
- `session` resolves through session metadata.
- `board` resolves through active sessions with matching board profile.

Methods:

```python
client.send(command: str) -> None
client.send_wait(command: str, prompt: str = "# ", timeout: float | None = None) -> str
client.expect_send(expect: str, command: str, timeout: float | None = None) -> None
client.expect_send_wait(
    expect: str,
    command: str,
    prompt: str = "# ",
    timeout: float | None = None,
) -> str
client.probe(timeout: float = 2.0) -> str
client.request(
    payload: dict,
    *,
    operation_timeout: float | None = None,
    io_timeout: float | None = None,
) -> dict
```

Helper behavior:

- `send()` sends `{"cmd": "send", "data": command}`.
- `send_wait()` sends `{"cmd": "send_wait", "data": command, "prompt": prompt,
  "timeout": timeout}`.
- `expect_send()` sends `{"cmd": "expect_send", "expect": expect, "data":
  command, "timeout": timeout}`.
- `expect_send_wait()` sends `{"cmd": "expect_send_wait", "expect": expect,
  "data": command, "prompt": prompt, "timeout": timeout}`.
- `probe()` sends `{"cmd": "probe", "timeout": timeout}` and defaults to 2
  seconds.
- If a helper timeout is `None`, it uses `default_timeout`, except `probe()`.

`request()` remains public for advanced users and future CLI reuse. It validates
the response and raises client exceptions for all non-OK outcomes.

### Import Surface

After `pip install ttypal-ai`, these names should be importable:

```python
from ttypal.client import (
    TtypalClient,
    TtypalClientError,
    TtypalSocketNotFound,
    TtypalSessionError,
    TtypalConnectionError,
    TtypalDaemonError,
    TtypalProtocolError,
    TtypalTimeoutError,
)
```

The package root may also re-export the primary class and exception base for
convenience:

```python
from ttypal import TtypalClient, TtypalClientError
```

The canonical import remains `from ttypal.client import TtypalClient`.

### User-Facing Interface Summary

`TtypalClient` should expose only the following stable methods in the first
version:

| Method | Purpose | Returns |
|--------|---------|---------|
| `send(command)` | send a command without waiting for output | `None` |
| `send_wait(command, prompt="# ", timeout=None)` | send a command and wait for prompt | command output `str` |
| `expect_send(expect, command, timeout=None)` | wait for text, then send command | `None` |
| `expect_send_wait(expect, command, prompt="# ", timeout=None)` | wait for text, send command, then wait for prompt | command output `str` |
| `probe(timeout=2.0)` | press enter and return current console response | response `str` |
| `request(payload, operation_timeout=None, io_timeout=None)` | send a raw daemon protocol request | response `dict` |

The constructor should expose these attributes for diagnostics:

```python
client.socket_path
client.session
client.board
client.default_timeout
```

`socket_path` should contain the resolved socket path after construction.

### Installed Usage Discovery

Users who install from PyPI should be able to learn the API without reading the
source tree.

Required documentation surfaces:

1. `README.md` must include a "Python API" section with:
   - installation command.
   - minimal session-based example.
   - `send_wait()` example.
   - timeout exception example.
   - method summary table.
2. `ttypal/client.py` must include module docstring examples so this works:

   ```bash
   python -m pydoc ttypal.client
   ```

3. `TtypalClient` and all public methods must have concise docstrings so this
   works in Python:

   ```python
   from ttypal.client import TtypalClient
   help(TtypalClient)
   help(TtypalClient.send_wait)
   ```

4. CLI help should mention the Python API for automation use:

   ```bash
   ttypal-send --help
   ```

   The help epilog should point users to:

   ```python
   from ttypal.client import TtypalClient
   ```

5. The package metadata should keep `README.md` as the PyPI long description,
   so the Python API section appears on the PyPI project page.

Minimum README example:

```python
from ttypal.client import TtypalClient, TtypalTimeoutError

serial = TtypalClient(session="sv15-ci")

try:
    output = serial.send_wait("uname -a", prompt="# ", timeout=30)
except TtypalTimeoutError as exc:
    print(f"timed out via {exc.socket_path}: {exc.output}")
else:
    print(output)
```

## Timeout Semantics

Two timeout types must remain separate:

- Operation timeout: sent to the daemon and used by daemon-side wait/probe/file
  transfer logic.
- I/O timeout: used by the Python client while connecting, sending, and reading
  the Unix socket response.

If `io_timeout` is omitted:

```python
io_timeout = operation_timeout + io_timeout_margin
```

If both `io_timeout` and `operation_timeout` are omitted, `operation_timeout`
defaults to the client's `default_timeout`.

This prevents long but valid daemon operations from being reported as client-side
socket failures.

## Socket Discovery

Refactor `ttypal/session.py` to expose exception-based lookup:

```python
class SessionLookupError(Exception): ...
class SessionNotFound(SessionLookupError): ...
class BoardSessionNotFound(SessionLookupError): ...
class MultipleSessionsFound(SessionLookupError): ...

def resolve_socket(
    *,
    session: str | None = None,
    board: str | None = None,
) -> str:
    ...
```

Rules:

- `session` and `board` are mutually exclusive.
- `session` must resolve to a live session metadata file or a matching fallback
  socket.
- `board` must resolve to exactly one live session for that profile or a
  matching fallback socket.
- no arguments means automatic discovery and requires exactly one active
  session or exactly one fallback socket.

The old `find_socket()` may remain only as a CLI presentation wrapper:

```python
def find_socket(session=None, board=None):
    try:
        return resolve_socket(session=session, board=board)
    except SessionLookupError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
```

New code should not call `find_socket()`.

## Daemon Protocol

Requests remain newline-delimited JSON over Unix domain sockets.

Successful response:

```json
{
  "status": "ok",
  "output": "optional command output"
}
```

Error response:

```json
{
  "status": "error",
  "code": "wait_timeout",
  "message": "waiting for prompt timed out",
  "output": "partial output if available"
}
```

Required error codes:

| Code | Meaning |
|------|---------|
| `unknown_command` | daemon does not recognize `cmd` |
| `bad_request` | missing or invalid request field |
| `wait_timeout` | `expect`, `prompt`, or other daemon wait timed out |
| `transfer_failed` | ZMODEM operation failed |
| `internal_error` | unexpected daemon exception |

Daemon-side changes:

- `expect_send` timeout returns `status=error`, `code=wait_timeout`.
- `expect_send_wait` timeout while waiting for `expect` returns
  `status=error`, `code=wait_timeout`.
- `send_wait` timeout while waiting for prompt returns `status=error`,
  `code=wait_timeout`, and includes partial output.
- `expect_send_wait` prompt timeout returns `status=error`,
  `code=wait_timeout`, and includes partial output.
- malformed JSON or missing required fields return `status=error`,
  `code=bad_request`.
- unknown `cmd` returns `status=error`, `code=unknown_command`.
- unhandled daemon exceptions return `status=error`, `code=internal_error`.

To distinguish prompt timeout from successful completion, internal wait helpers
should return a structured result instead of only a string:

```python
WaitResult(
    matched: bool,
    output: str,
)
```

## Exceptions

Add client exceptions:

```python
class TtypalClientError(Exception): ...
class TtypalSocketNotFound(TtypalClientError): ...
class TtypalSessionError(TtypalClientError): ...
class TtypalConnectionError(TtypalClientError): ...
class TtypalDaemonError(TtypalClientError): ...
class TtypalProtocolError(TtypalClientError): ...
class TtypalTimeoutError(TtypalDaemonError): ...
```

Exception fields:

```python
exc.socket_path
exc.payload
exc.response
exc.code
exc.output
```

Mapping:

- Session lookup failures raise `TtypalSessionError`.
- Missing socket file raises `TtypalSocketNotFound`.
- Refused, reset, or broken socket connection raises `TtypalConnectionError`.
- Undecodable or invalid JSON response raises `TtypalProtocolError`.
- Missing `status` or malformed daemon response raises `TtypalProtocolError`.
- Daemon response with `status != "ok"` raises `TtypalDaemonError`.
- Daemon response with `code == "wait_timeout"` raises `TtypalTimeoutError`.
- Client-side socket timeout also raises `TtypalTimeoutError`, with
  `code="client_io_timeout"`.

## CLI Integration

`ttypal-send` becomes a thin wrapper:

1. Parse arguments.
2. Build `TtypalClient(socket_path=...)`, `TtypalClient(session=...)`,
   `TtypalClient(board=...)`, or auto client.
3. Call the matching helper.
4. Print returned output if present.
5. Convert `TtypalClientError` to stderr and exit 1.

`ttypal-xfer` should also use `TtypalClient.request()` for `zmodem_send` and
`zmodem_recv`, so socket I/O and response validation have one implementation.

The CLI output text may change where needed to reflect structured errors. The
CLI must not expose tracebacks for expected client/daemon errors.

## SV15 CI Usage

Example:

```python
from ttypal.client import TtypalClient, TtypalTimeoutError

serial = TtypalClient(session=TTYPAL_SESSION)

try:
    output = serial.send_wait(command, prompt=BOARD_PROMPT, timeout=30)
except TtypalTimeoutError as exc:
    raise AssertionError(
        f"serial command timed out via {exc.socket_path}: {exc.output}"
    ) from exc
```

CI setup scripts can continue to start and stop `ttypal-daemon` through CLI
entry points. Test code should use the Python client for serial operations.

## Implementation Plan

1. Add exception-based socket discovery in `ttypal/session.py`.
2. Add `ttypal/client.py` with request I/O, response validation, exceptions,
   and high-level helper methods.
3. Update `SocketServer` responses to include structured error codes.
4. Change daemon wait helpers to report matched-vs-timeout status and partial
   output.
5. Refactor `ttypal-send` to use `TtypalClient`.
6. Refactor `ttypal-xfer` to use `TtypalClient.request()`.
7. Update tests for session lookup, client request handling, daemon timeout
   errors, and CLI wrappers.
8. Update documentation references in `README.md`, `docs/architecture.md`,
   `docs/test-cases.md`, `docs/manual-test-cases.md`, and
   `.agents/skills/ttypal/SKILL.md` if affected.

## Cleanup Targets

This feature should also clean up existing implementation debt that becomes
obsolete once `TtypalClient` exists:

- Replace duplicate socket JSON request code in `ttypal/cli_send.py` and
  `ttypal/cli_xfer.py` with `TtypalClient.request()` or named helpers.
- Move library-facing socket discovery away from `session.find_socket()` because
  it prints errors and exits the process.
- Keep `find_socket()` only as a legacy CLI presentation wrapper, if it remains
  at all.
- Replace ad hoc socket request helpers in tests with client-based tests or a
  shared test helper where raw protocol testing is still intentional.
- Keep AI-agent instructions under `.agents/` instead of tool-specific
  directories such as `.claude/` or `.qwen/`.

## Test Requirements

Unit tests:

- explicit socket path selection.
- session-based socket lookup.
- board/profile-based socket lookup.
- auto discovery with zero, one, and multiple sessions.
- constructor rejects multiple selectors.
- successful request/response handling.
- daemon error response maps to `TtypalDaemonError`.
- daemon `wait_timeout` maps to `TtypalTimeoutError` and preserves output.
- missing socket maps to `TtypalSocketNotFound`.
- refused connection maps to `TtypalConnectionError`.
- invalid JSON maps to `TtypalProtocolError`.
- malformed daemon response maps to `TtypalProtocolError`.

Integration/e2e tests:

- `TtypalClient.send()` against replay-backed socket server.
- `TtypalClient.send_wait()` returns expected output.
- `TtypalClient.probe()` defaults to two seconds.
- `send_wait` prompt timeout returns structured daemon timeout error.
- representative `ttypal-send` invocations still call through the client.
- `ttypal-xfer` request path uses the client and maps daemon transfer errors.

Manual regression:

- Ask whether real hardware testing is possible before commit.
- If hardware is available, run relevant cases from
  `docs/manual-test-cases.md`, especially send, send_wait, probe, wait-for,
  session/board/socket selection, and error handling.
- Record any newly discovered edge cases in `docs/test-cases.md` or
  `docs/manual-test-cases.md`.

## Acceptance Criteria

For `v0.9.0`:

- `from ttypal.client import TtypalClient` works after installing `ttypal-ai`.
- Python tests can run serial commands without spawning `ttypal-send`.
- `ttypal-send` and `ttypal-xfer` share the same socket request implementation.
- Library code no longer depends on `find_socket()` or `sys.exit()` paths.
- Daemon error responses contain stable `code` values.
- Wait timeouts raise `TtypalTimeoutError` and preserve partial output where
  available.
- Failures include enough context to identify the selected session/socket,
  request payload, daemon response, and partial output.
- README, PyPI long description, pydoc output, and CLI help all explain the
  Python API.
- The provisional public API surface is explicitly listed in documentation.
- `make test` passes.

## v0.9 Release Checklist

Before tagging `v0.9.0`:

1. Version numbers are updated in `ttypal/__init__.py`, `pyproject.toml`, and
   `AGENTS.md`.
2. `README.md` includes the stable Python API section and examples.
3. `docs/architecture.md` documents the client/daemon boundary and protocol
   response schema.
4. `docs/test-cases.md` lists the new automated client and protocol tests.
5. `docs/manual-test-cases.md` includes real hardware regression cases for the
   Python client.
6. `.agents/skills/ttypal/SKILL.md` references the Python API where useful for
   agent usage.
7. `make test` passes.
8. Real machine regression has been requested; if hardware is available,
   relevant manual cases pass.
9. `make build` succeeds.
10. `make release` is run only after the above items are complete.

## v1 Readiness Criteria

Do not tag `v1.0.0` immediately after the first implementation. Consider v1 only
after:

- `v0.9.x` has been used by CI, agent workflows, and local board scripts beyond
  the initial implementation environment.
- Reported API, timeout, session discovery, and daemon protocol issues have
  converged rather than continuing to reveal design churn.
- The documented `TtypalClient` methods and exception model have proven
  sufficient for real callers.
- Any breaking changes discovered during `v0.9.x` have already been made before
  the v1 cut.
- Manual hardware regression has been repeated on representative boards.
- The project is ready to treat the Python API and daemon response schema as
  stable public contracts.

## Post-v0.9 Stabilization Findings

Real-machine regression with the `1.5m` profile exposed daemon lifecycle issues
outside the Python client request path:

- A session owned by another user can appear as running because its PID is
  alive, while the daemon socket refuses connections. `ttypal-daemon status`
  should verify socket reachability and report unhealthy cross-user sessions
  with owner, PID, socket path, and suggested remediation.
- `ttypal-daemon start` can print "启动中" and return before the daemon has
  proven that it owns the serial port and can serve socket requests. Startup
  should wait for initialization/socket readiness and return non-zero with the
  actual serial lock or permission error when startup fails.
- `expect_send` / `--wait-for` can match stale text from the recent log window.
  During login testing, an old `Password:` caused the password to be sent at a
  fresh `login:` prompt. The wait-for implementation should be redesigned to
  support a fresh wait window for interactive sequences.

## Open Questions

- Should `TtypalClient` expose daemon lifecycle helpers later, or should daemon
  start/stop remain CLI-only?
- Should file transfer get named client helpers (`put`, `get`) after `xfer`
  request reuse lands?
- Should `default_timeout` stay at 10 seconds for CI, or should SV15 provide a
  project-specific wrapper with longer defaults?
