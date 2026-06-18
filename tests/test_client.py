import json
import socket
import threading

import pytest

from ttypal.client import (
    TtypalClient,
    TtypalConnectionError,
    TtypalDaemonError,
    TtypalProtocolError,
    TtypalSocketNotFound,
    TtypalTimeoutError,
)


def _serve_once(sock_path, response):
    ready = threading.Event()
    received = {}

    def run():
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(sock_path))
        server.listen(1)
        ready.set()
        conn, _ = server.accept()
        data = b""
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
        received["payload"] = json.loads(data)
        if isinstance(response, bytes):
            conn.sendall(response)
        else:
            conn.sendall(json.dumps(response).encode() + b"\n")
        conn.close()
        server.close()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    ready.wait(timeout=2)
    return received, thread


def test_constructor_rejects_multiple_selectors(tmp_path):
    with pytest.raises(ValueError):
        TtypalClient(session="s", socket_path=str(tmp_path / "x.sock"))


def test_send_wait_success(tmp_path):
    sock_path = tmp_path / "ttypal.sock"
    received, thread = _serve_once(sock_path, {"status": "ok", "output": "Linux\n# "})

    client = TtypalClient(socket_path=str(sock_path))
    assert client.send_wait("uname -a", prompt="# ", timeout=3) == "Linux\n# "
    thread.join(timeout=2)
    assert received["payload"] == {
        "cmd": "send_wait",
        "data": "uname -a",
        "prompt": "# ",
        "timeout": 3,
    }


def test_daemon_error_maps_to_daemon_error(tmp_path):
    sock_path = tmp_path / "ttypal.sock"
    _received, _thread = _serve_once(
        sock_path,
        {"status": "error", "code": "bad_request", "message": "missing field"},
    )

    client = TtypalClient(socket_path=str(sock_path))
    with pytest.raises(TtypalDaemonError) as excinfo:
        client.send("ls")
    assert excinfo.value.code == "bad_request"
    assert "missing field" in str(excinfo.value)


def test_wait_timeout_preserves_output(tmp_path):
    sock_path = tmp_path / "ttypal.sock"
    _received, _thread = _serve_once(
        sock_path,
        {
            "status": "error",
            "code": "wait_timeout",
            "message": "timeout",
            "output": "partial",
        },
    )

    client = TtypalClient(socket_path=str(sock_path))
    with pytest.raises(TtypalTimeoutError) as excinfo:
        client.send_wait("sleep 10", timeout=1)
    assert excinfo.value.code == "wait_timeout"
    assert excinfo.value.output == "partial"


def test_missing_socket_maps_to_socket_not_found(tmp_path):
    client = TtypalClient(socket_path=str(tmp_path / "missing.sock"))
    with pytest.raises(TtypalSocketNotFound):
        client.send("ls")


def test_refused_connection_maps_to_connection_error(tmp_path):
    sock_path = tmp_path / "orphan.sock"
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(sock_path))
    server.close()

    client = TtypalClient(socket_path=str(sock_path))
    with pytest.raises(TtypalConnectionError):
        client.send("ls")


def test_invalid_json_maps_to_protocol_error(tmp_path):
    sock_path = tmp_path / "ttypal.sock"
    _received, _thread = _serve_once(sock_path, b"not-json\n")

    client = TtypalClient(socket_path=str(sock_path))
    with pytest.raises(TtypalProtocolError):
        client.send("ls")


def test_malformed_response_maps_to_protocol_error(tmp_path):
    sock_path = tmp_path / "ttypal.sock"
    _received, _thread = _serve_once(sock_path, {"output": "missing status"})

    client = TtypalClient(socket_path=str(sock_path))
    with pytest.raises(TtypalProtocolError):
        client.send("ls")
