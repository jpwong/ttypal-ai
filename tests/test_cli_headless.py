import os
import signal

from ttypal import cli_headless


def test_read_pid_permission_denied_is_running(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_headless, "PID_DIR", tmp_path)
    (tmp_path / "ttypal-otheruser.pid").write_text("12345")

    def raise_permission_error(pid, sig):
        raise PermissionError

    monkeypatch.setattr(os, "kill", raise_permission_error)

    assert cli_headless._read_pid("otheruser") == 12345
    assert (tmp_path / "ttypal-otheruser.pid").exists()


def test_read_pid_unlink_permission_denied_does_not_raise(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_headless, "PID_DIR", tmp_path)
    (tmp_path / "ttypal-stale.pid").write_text("99999999")

    def raise_process_lookup(pid, sig):
        raise ProcessLookupError

    def raise_permission_error(*args, **kwargs):
        raise PermissionError

    monkeypatch.setattr(os, "kill", raise_process_lookup)
    monkeypatch.setattr(type(tmp_path / "ttypal-stale.pid"), "unlink", raise_permission_error)

    assert cli_headless._read_pid("stale") is None


def test_stop_permission_denied_does_not_remove_session(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli_headless, "PID_DIR", tmp_path)
    (tmp_path / "ttypal-otheruser.pid").write_text("12345")
    removed = []

    def fake_kill(pid, sig):
        assert pid == 12345
        if sig == 0:
            raise PermissionError
        assert sig == signal.SIGTERM
        raise PermissionError

    monkeypatch.setattr(os, "kill", fake_kill)
    monkeypatch.setattr(cli_headless, "_find_running", lambda: ["otheruser"])
    monkeypatch.setattr("ttypal.session.remove_session", lambda name: removed.append(name))

    args = type("Args", (), {"session": "otheruser", "board": None})()
    cli_headless.cmd_stop(args)

    assert "无权限停止" in capsys.readouterr().out
    assert removed == []
    assert (tmp_path / "ttypal-otheruser.pid").exists()


def test_stop_waits_for_exit_before_cleanup(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli_headless, "PID_DIR", tmp_path)
    (tmp_path / "ttypal-board.pid").write_text("12345")
    removed = []
    signals = []

    def fake_kill(pid, sig):
        assert pid == 12345
        signals.append(sig)

    monkeypatch.setattr(os, "kill", fake_kill)
    monkeypatch.setattr(cli_headless, "_wait_for_pid_exit", lambda pid: True)
    monkeypatch.setattr("ttypal.session.remove_session", lambda name: removed.append(name))

    args = type("Args", (), {"session": "board", "board": None})()
    cli_headless.cmd_stop(args)

    assert signals == [0, signal.SIGTERM]
    assert removed == ["board"]
    assert not (tmp_path / "ttypal-board.pid").exists()
    assert "已停止" in capsys.readouterr().out


def test_stop_timeout_keeps_session_metadata(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli_headless, "PID_DIR", tmp_path)
    (tmp_path / "ttypal-board.pid").write_text("12345")
    removed = []

    def fake_kill(pid, sig):
        assert pid == 12345

    monkeypatch.setattr(os, "kill", fake_kill)
    monkeypatch.setattr(cli_headless, "_wait_for_pid_exit", lambda pid: False)
    monkeypatch.setattr("ttypal.session.remove_session", lambda name: removed.append(name))

    args = type("Args", (), {"session": "board", "board": None})()
    cli_headless.cmd_stop(args)

    assert removed == []
    assert (tmp_path / "ttypal-board.pid").exists()
    assert "停止超时" in capsys.readouterr().out


def test_status_session_ignores_stale_metadata(monkeypatch, capsys):
    monkeypatch.setattr(
        "ttypal.session.load_session",
        lambda name: {
            "profile": "board",
            "port": "/dev/ttyUSB1",
            "baudrate": 1500000,
            "socket": "/tmp/ttypal-board.sock",
            "pid": 12345,
        },
    )
    monkeypatch.setattr("ttypal.session.is_session_alive", lambda name: False)

    args = type("Args", (), {"session": "board", "board": None})()
    cli_headless.cmd_status(args)

    out = capsys.readouterr().out
    assert "未运行" in out
    assert "运行中" not in out
