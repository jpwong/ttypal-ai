import os
import socket
from types import SimpleNamespace

from ttypal.main import _resolve_raw_output, _session_conflict


def _args(raw):
    return SimpleNamespace(raw=raw)


def test_raw_defaults_off_for_old_config():
    assert _resolve_raw_output(_args(None), {}) is False


def test_raw_reads_terminal_config():
    assert _resolve_raw_output(_args(None), {"terminal": {"raw": True}}) is True


def test_cli_raw_overrides_false_config():
    assert _resolve_raw_output(_args(True), {"terminal": {"raw": False}}) is True


def test_cli_no_raw_overrides_true_config():
    assert _resolve_raw_output(_args(False), {"terminal": {"raw": True}}) is False


def test_raw_ignores_invalid_terminal_section():
    assert _resolve_raw_output(_args(None), {"terminal": "invalid"}) is False


def _listening_sock(path):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(str(path))
    s.listen(1)
    return s


def _save_session(tmp_path, monkeypatch, name, info):
    monkeypatch.setattr("ttypal.session.SESSION_DIR", tmp_path)
    from ttypal.session import save_session
    save_session(name, info)


def test_session_conflict_none_without_socket(tmp_path, monkeypatch):
    monkeypatch.setattr("ttypal.session.SESSION_DIR", tmp_path)
    assert _session_conflict("1.5m", tmp_path / "ttypal-1.5m.sock") is None


def test_session_conflict_ignores_stale_socket(tmp_path, monkeypatch):
    """A killed instance leaves the socket file behind; it must not block startup."""
    monkeypatch.setattr("ttypal.session.SESSION_DIR", tmp_path)
    stale = tmp_path / "ttypal-1.5m.sock"
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(str(stale))
    s.close()

    assert _session_conflict("1.5m", stale) is None


def test_session_conflict_reports_pid(tmp_path, monkeypatch):
    sock_path = tmp_path / "ttypal-1.5m.sock"
    server = _listening_sock(sock_path)
    _save_session(tmp_path, monkeypatch, "1.5m", {
        "profile": "1.5m",
        "port": "/dev/ttyUSB1",
        "socket": str(sock_path),
        "pid": os.getpid(),
    })
    try:
        msg = _session_conflict("1.5m", sock_path)
        assert msg is not None
        assert f"PID {os.getpid()}" in msg
        assert "/dev/ttyUSB1" in msg
        assert "-S" in msg
    finally:
        server.close()
        sock_path.unlink(missing_ok=True)


def test_session_conflict_without_metadata(tmp_path, monkeypatch):
    """Metadata can be missing (old instance, another user): still refuse."""
    monkeypatch.setattr("ttypal.session.SESSION_DIR", tmp_path)
    sock_path = tmp_path / "ttypal-1.5m.sock"
    server = _listening_sock(sock_path)
    try:
        msg = _session_conflict("1.5m", sock_path)
        assert msg is not None
        assert "已被另一个 ttypal 实例使用" in msg
        assert "-S" in msg
    finally:
        server.close()
        sock_path.unlink(missing_ok=True)
