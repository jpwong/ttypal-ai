import os
import json
from pathlib import Path

import pytest

from ttypal.session import (
    session_file, save_session, load_session, remove_session,
    list_sessions, find_socket, SESSION_DIR,
)


@pytest.fixture
def session_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("ttypal.session.SESSION_DIR", tmp_path)
    return tmp_path


def test_session_file_path(session_dir):
    path = session_file("test1")
    assert path == session_dir / "ttypal-test1.session"


def test_save_and_load(session_dir):
    info = {
        "profile": "rk3588",
        "port": "/dev/ttyUSB0",
        "baudrate": 115200,
        "socket": "/tmp/ttypal-test1.sock",
        "pid": os.getpid(),
        "started": "2026-06-04T12:00:00",
    }
    save_session("test1", info)
    loaded = load_session("test1")
    assert loaded["profile"] == "rk3588"
    assert loaded["port"] == "/dev/ttyUSB0"
    assert loaded["socket"] == "/tmp/ttypal-test1.sock"


def test_load_nonexistent(session_dir):
    assert load_session("nope") is None


def test_load_dead_process(session_dir):
    """load_session returns None when the PID is dead."""
    info = {
        "profile": "rk3588",
        "port": "/dev/ttyUSB0",
        "baudrate": 115200,
        "socket": "/tmp/ttypal-dead.sock",
        "pid": 99999999,  # very unlikely to exist
        "started": "2026-06-04T12:00:00",
    }
    save_session("dead", info)
    assert load_session("dead") is None
    assert not session_file("dead").exists()


def test_remove_session(session_dir):
    save_session("todelete", {"profile": "x", "socket": "/tmp/x.sock", "pid": os.getpid()})
    assert session_file("todelete").exists()
    remove_session("todelete")
    assert not session_file("todelete").exists()


def test_remove_nonexistent(session_dir):
    # Should not raise
    remove_session("nope")


def test_list_sessions(session_dir):
    save_session("alpha", {"profile": "rk3588", "socket": "/tmp/a.sock", "pid": os.getpid()})
    save_session("beta", {"profile": "rk3568", "socket": "/tmp/b.sock", "pid": os.getpid()})
    sessions = list_sessions()
    names = [name for name, _ in sessions]
    assert names == ["alpha", "beta"]


def test_list_sessions_ignores_dead(session_dir):
    save_session("alive", {"profile": "rk3588", "socket": "/tmp/a.sock", "pid": os.getpid()})
    save_session("dead", {"profile": "rk3568", "socket": "/tmp/b.sock", "pid": 99999999})
    sessions = list_sessions()
    names = [name for name, _ in sessions]
    assert names == ["alive"]


class TestFindSocket:
    def test_by_session_name(self, session_dir):
        save_session("left", {"profile": "rk3588", "socket": "/tmp/ttypal-left.sock", "pid": os.getpid()})
        assert find_socket(session="left") == "/tmp/ttypal-left.sock"

    def test_by_session_name_not_found(self, session_dir):
        with pytest.raises(SystemExit):
            find_socket(session="nope")

    def test_by_board_single(self, session_dir):
        save_session("left", {"profile": "rk3588", "socket": "/tmp/ttypal-left.sock", "pid": os.getpid()})
        assert find_socket(board="rk3588") == "/tmp/ttypal-left.sock"

    def test_by_board_multiple(self, session_dir):
        save_session("left", {"profile": "rk3588", "socket": "/tmp/ttypal-left.sock", "pid": os.getpid()})
        save_session("right", {"profile": "rk3588", "socket": "/tmp/ttypal-right.sock", "pid": os.getpid()})
        with pytest.raises(SystemExit):
            find_socket(board="rk3588")

    def test_by_board_not_found(self, session_dir):
        with pytest.raises(SystemExit):
            find_socket(board="nonexistent")

    def test_auto_detect_single(self, session_dir):
        save_session("only", {"profile": "rk3588", "socket": "/tmp/ttypal-only.sock", "pid": os.getpid()})
        assert find_socket() == "/tmp/ttypal-only.sock"

    def test_auto_detect_multiple(self, session_dir):
        save_session("a", {"profile": "rk3588", "socket": "/tmp/a.sock", "pid": os.getpid()})
        save_session("b", {"profile": "rk3568", "socket": "/tmp/b.sock", "pid": os.getpid()})
        with pytest.raises(SystemExit):
            find_socket()

    def test_auto_detect_none(self, session_dir):
        with pytest.raises(SystemExit):
            find_socket()
