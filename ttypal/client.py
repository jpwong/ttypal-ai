"""Python client for talking to a running ttypal daemon.

Example:

    from ttypal.client import TtypalClient

    serial = TtypalClient(session="my-board")
    output = serial.send_wait("uname -a", prompt="# ", timeout=30)
    print(output)
"""

import json
import os
import socket

from .session import SessionLookupError, resolve_socket


class TtypalClientError(Exception):
    """Base error for ttypal client failures."""

    def __init__(
        self,
        message,
        *,
        socket_path=None,
        payload=None,
        response=None,
        code=None,
        output=None,
    ):
        super().__init__(message)
        self.socket_path = socket_path
        self.payload = payload
        self.response = response
        self.code = code
        self.output = output


class TtypalSocketNotFound(TtypalClientError):
    """Resolved socket path does not exist."""


class TtypalSessionError(TtypalClientError):
    """Session or board lookup failed."""


class TtypalConnectionError(TtypalClientError):
    """Could not connect to the daemon socket."""


class TtypalDaemonError(TtypalClientError):
    """Daemon returned an error response."""


class TtypalProtocolError(TtypalClientError):
    """Daemon response was not valid ttypal protocol JSON."""


class TtypalTimeoutError(TtypalDaemonError):
    """Daemon wait timeout or client-side socket I/O timeout."""


class TtypalClient:
    """Client for sending commands to a running ttypal daemon.

    Args:
        session: Running ttypal session name.
        board: Board profile name used to find a running session.
        socket_path: Explicit daemon Unix socket path.
        default_timeout: Default daemon operation timeout in seconds.
        io_timeout_margin: Extra seconds added to operation timeout for socket
            I/O when no explicit I/O timeout is supplied.
    """

    def __init__(
        self,
        *,
        session=None,
        board=None,
        socket_path=None,
        default_timeout=10,
        io_timeout_margin=5,
    ):
        selectors = [value is not None for value in (session, board, socket_path)]
        if sum(selectors) > 1:
            raise ValueError("Use only one of session, board, or socket_path")

        self.session = session
        self.board = board
        self.default_timeout = default_timeout
        self.io_timeout_margin = io_timeout_margin

        if socket_path is not None:
            self.socket_path = socket_path
        else:
            try:
                self.socket_path = resolve_socket(session=session, board=board)
            except SessionLookupError as exc:
                raise TtypalSessionError(str(exc)) from exc

    def send(self, command):
        """Send a command without waiting for output."""
        self.request({"cmd": "send", "data": command})

    def send_wait(self, command, prompt="# ", timeout=None):
        """Send a command and return output collected until prompt appears."""
        op_timeout = self._timeout(timeout)
        resp = self.request(
            {
                "cmd": "send_wait",
                "data": command,
                "prompt": prompt,
                "timeout": op_timeout,
            },
            operation_timeout=op_timeout,
        )
        return resp.get("output", "")

    def expect_send(self, expect, command, timeout=None):
        """Wait for text to appear, then send a command."""
        op_timeout = self._timeout(timeout)
        self.request(
            {
                "cmd": "expect_send",
                "expect": expect,
                "data": command,
                "timeout": op_timeout,
            },
            operation_timeout=op_timeout,
        )

    def expect_send_wait(self, expect, command, prompt="# ", timeout=None):
        """Wait for text, send a command, then return output until prompt."""
        op_timeout = self._timeout(timeout)
        resp = self.request(
            {
                "cmd": "expect_send_wait",
                "expect": expect,
                "data": command,
                "prompt": prompt,
                "timeout": op_timeout,
            },
            operation_timeout=op_timeout,
        )
        return resp.get("output", "")

    def probe(self, timeout=2.0):
        """Send Enter and return the console response."""
        resp = self.request(
            {"cmd": "probe", "timeout": timeout},
            operation_timeout=timeout,
        )
        return resp.get("output", "")

    def request(self, payload, *, operation_timeout=None, io_timeout=None):
        """Send a raw daemon protocol request and return the response dict."""
        if operation_timeout is None:
            operation_timeout = self.default_timeout
        if io_timeout is None:
            io_timeout = operation_timeout + self.io_timeout_margin

        sock_path = self.socket_path
        if not os.path.exists(sock_path):
            raise TtypalSocketNotFound(
                f"Socket 不存在: {sock_path}",
                socket_path=sock_path,
                payload=payload,
            )

        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(io_timeout)
                sock.connect(sock_path)
                sock.sendall(json.dumps(payload).encode() + b"\n")
                sock.shutdown(socket.SHUT_WR)

                resp_data = b""
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    resp_data += chunk
        except socket.timeout as exc:
            raise TtypalTimeoutError(
                f"ttypal socket I/O timed out after {io_timeout}s",
                socket_path=sock_path,
                payload=payload,
                code="client_io_timeout",
            ) from exc
        except (ConnectionRefusedError, ConnectionResetError, BrokenPipeError, OSError) as exc:
            if isinstance(exc, FileNotFoundError):
                raise TtypalSocketNotFound(
                    f"Socket 不存在: {sock_path}",
                    socket_path=sock_path,
                    payload=payload,
                ) from exc
            raise TtypalConnectionError(
                "无法连接 ttypal，确认是否在运行",
                socket_path=sock_path,
                payload=payload,
            ) from exc

        try:
            resp = json.loads(resp_data)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise TtypalProtocolError(
                "Invalid JSON response from ttypal daemon",
                socket_path=sock_path,
                payload=payload,
                response=resp_data,
            ) from exc

        if not isinstance(resp, dict) or "status" not in resp:
            raise TtypalProtocolError(
                "Malformed response from ttypal daemon",
                socket_path=sock_path,
                payload=payload,
                response=resp,
            )

        if resp.get("status") == "ok":
            return resp

        message = resp.get("message", "unknown")
        code = resp.get("code")
        error_cls = TtypalTimeoutError if code == "wait_timeout" else TtypalDaemonError
        raise error_cls(
            message,
            socket_path=sock_path,
            payload=payload,
            response=resp,
            code=code,
            output=resp.get("output"),
        )

    def _timeout(self, timeout):
        return self.default_timeout if timeout is None else timeout
