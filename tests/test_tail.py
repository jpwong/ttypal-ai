import tempfile
import os
import socket
from pathlib import Path

from ttypal.logger import Logger, SESSION_MARKER_PREFIX
from ttypal.cli_tail import tail, _read_session_id, _is_daemon_alive


def test_session_marker_in_new_file(tmp_path):
    logger = Logger("testboard", directory=str(tmp_path))
    log_file = logger.current_log
    logger.close()

    first_line = log_file.read_text().split("\n")[0]
    assert first_line.startswith(SESSION_MARKER_PREFIX)
    assert logger.session_id in first_line


def test_session_marker_consistent_after_rotation(tmp_path):
    logger = Logger("testboard", directory=str(tmp_path), rotate_size_kb=1)
    for i in range(200):
        logger.write(f"{'x' * 100}\n".encode())
    logger.close()

    log_files = sorted((tmp_path / "testboard").glob("*.log"))
    assert len(log_files) > 1

    session_ids = [_read_session_id(f) for f in log_files]
    assert all(sid == logger.session_id for sid in session_ids)


def test_tail_basic(tmp_path):
    logger = Logger("testboard", directory=str(tmp_path))
    for i in range(5):
        logger.write(f"line{i}\n".encode())
    logger.close()

    lines = tail(tmp_path / "testboard", 3)
    assert len(lines) == 3
    assert "line2" in lines[0]
    assert "line4" in lines[2]


def test_tail_cross_file_same_session(tmp_path):
    logger = Logger("testboard", directory=str(tmp_path), rotate_size_kb=1)
    written_lines = []
    for i in range(200):
        text = f"data_{i:04d}\n"
        logger.write(text.encode())
        written_lines.append(f"data_{i:04d}")
    logger.close()

    log_files = sorted((tmp_path / "testboard").glob("*.log"))
    assert len(log_files) > 1

    lines = tail(tmp_path / "testboard", 10)
    assert len(lines) == 10
    for line in lines:
        assert any(w in line for w in written_lines[-10:])


def test_tail_does_not_cross_session_boundary(tmp_path):
    board_dir = tmp_path / "testboard"

    # Session 1
    logger1 = Logger("testboard", directory=str(tmp_path))
    for i in range(10):
        logger1.write(f"old_line_{i}\n".encode())
    logger1.close()

    # Session 2
    logger2 = Logger("testboard", directory=str(tmp_path))
    for i in range(3):
        logger2.write(f"new_line_{i}\n".encode())
    logger2.close()

    assert logger1.session_id != logger2.session_id

    lines = tail(board_dir, 100)
    assert len(lines) == 3
    for line in lines:
        assert "new_line_" in line
    for line in lines:
        assert "old_line_" not in line


def test_tail_boundary_request_more_than_available(tmp_path):
    logger = Logger("testboard", directory=str(tmp_path))
    logger.write(b"only_line\n")
    logger.close()

    lines = tail(tmp_path / "testboard", 100)
    assert len(lines) == 1
    assert "only_line" in lines[0]


def test_tail_empty_dir(tmp_path):
    board_dir = tmp_path / "testboard"
    board_dir.mkdir(parents=True)

    lines = tail(board_dir, 10)
    assert lines == []


def test_tail_session_marker_not_in_output(tmp_path):
    logger = Logger("testboard", directory=str(tmp_path))
    logger.write(b"visible\n")
    logger.close()

    lines = tail(tmp_path / "testboard", 100)
    for line in lines:
        assert not line.startswith(SESSION_MARKER_PREFIX)


def test_tail_no_session_marker_in_old_files(tmp_path):
    """旧格式日志文件（无 session 标记）不应被当前 session 读取"""
    board_dir = tmp_path / "testboard"
    board_dir.mkdir(parents=True)

    # 模拟旧日志（无 session 标记）
    old_log = board_dir / "20260101_000000.log"
    old_log.write_text("[00:00:00] old_data\n" * 10)

    # 新 session
    logger = Logger("testboard", directory=str(tmp_path))
    logger.write(b"new_data\n")
    logger.close()

    lines = tail(board_dir, 100)
    assert len(lines) == 1
    assert "new_data" in lines[0]
    for line in lines:
        assert "old_data" not in line


def test_logger_no_timestamp(tmp_path):
    """时间戳关闭时日志直接写入原始数据"""
    logger = Logger("testboard", directory=str(tmp_path), timestamp_format="")
    logger.write(b"raw line 1\n")
    logger.write(b"raw line 2\n")
    logger.close()

    content = logger.current_log.read_text()
    lines = content.strip().split("\n")
    assert lines[0].startswith(SESSION_MARKER_PREFIX)
    assert lines[1] == "raw line 1"
    assert lines[2] == "raw line 2"


def test_tail_works_without_timestamp(tmp_path):
    """时间戳关闭时 tail 仍然正确工作"""
    logger = Logger("testboard", directory=str(tmp_path), timestamp_format="")
    for i in range(5):
        logger.write(f"no_ts_{i}\n".encode())
    logger.close()

    lines = tail(tmp_path / "testboard", 3)
    assert len(lines) == 3
    assert "no_ts_2" in lines[0]
    assert "no_ts_4" in lines[2]
    for line in lines:
        assert not line.startswith(SESSION_MARKER_PREFIX)


def test_tail_cross_session_without_timestamp(tmp_path):
    """时间戳关闭时 session 边界仍然有效"""
    # Session 1
    logger1 = Logger("testboard", directory=str(tmp_path), timestamp_format="")
    for i in range(10):
        logger1.write(f"old_{i}\n".encode())
    logger1.close()

    # Session 2
    logger2 = Logger("testboard", directory=str(tmp_path), timestamp_format="")
    logger2.write(b"new_only\n")
    logger2.close()

    lines = tail(tmp_path / "testboard", 100)
    assert len(lines) == 1
    assert "new_only" in lines[0]


def test_daemon_alive_no_pid_file():
    assert _is_daemon_alive("nonexistent_board_xyz") is False


def test_daemon_alive_stale_pid(tmp_path, monkeypatch):
    pid_file = Path("/tmp/ttypal-testdaemon.pid")
    pid_file.write_text("99999999")
    try:
        assert _is_daemon_alive("testdaemon") is False
    finally:
        pid_file.unlink(missing_ok=True)


def test_daemon_alive_current_process(tmp_path):
    pid_file = Path("/tmp/ttypal-testdaemon2.pid")
    pid_file.write_text(str(os.getpid()))
    try:
        assert _is_daemon_alive("testdaemon2") is True
    finally:
        pid_file.unlink(missing_ok=True)


def test_daemon_alive_socket_exists(tmp_path):
    sock_file = Path("/tmp/ttypal-testsock.sock")
    sock_file.unlink(missing_ok=True)
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.bind(str(sock_file))
        assert _is_daemon_alive("testsock") is True
    finally:
        sock.close()
        sock_file.unlink(missing_ok=True)
