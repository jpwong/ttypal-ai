import threading
import time
from pathlib import Path

from ttypal.socket_server import SocketServer


class _Logger:
    current_log = ""


def _server_for_log(path):
    logger = _Logger()
    logger.current_log = str(path)
    return SocketServer(None, logger, "/tmp/unused-ttypal-test.sock")


class _SignalLogger:
    """Logger stub that signals the first metadata read."""

    def __init__(self, path):
        self._path = str(path)
        self.accessed = threading.Event()

    @property
    def current_log(self):
        self.accessed.set()
        return self._path

    @current_log.setter
    def current_log(self, value):
        self._path = str(value)


class _RotatingLogger:
    """Logger stub that returns a different path on each metadata read."""

    def __init__(self, paths):
        self._paths = [str(p) for p in paths]
        self._index = 0

    @property
    def current_log(self):
        path = self._paths[min(self._index, len(self._paths) - 1)]
        self._index += 1
        return path


def test_wait_for_prompt_after_cmd_returns_command_output(tmp_path):
    prefix = "~ # "
    log_path = Path(tmp_path) / "serial.log"
    log_path.write_text(prefix + "uname -m\naarch64\n~ # ", encoding="utf-8")

    result = _server_for_log(log_path)._wait_for_prompt_after_cmd(
        "uname -m", "# ", 1, len(prefix)
    )

    assert result.matched is True
    assert "aarch64" in result.output


def test_wait_for_prompt_after_cmd_times_out_instead_of_empty_success(tmp_path):
    prefix = "~ # "
    log_path = Path(tmp_path) / "serial.log"
    log_path.write_text(prefix + "uname -m\n", encoding="utf-8")

    result = _server_for_log(log_path)._wait_for_prompt_after_cmd(
        "uname -m", "# ", 0.05, len(prefix)
    )

    assert result.matched is False
    assert result.output == ""


def test_wait_for_prompt_after_cmd_uses_byte_mark_with_unicode_prefix(tmp_path):
    prefix = "启动日志\n~ # "
    log_path = Path(tmp_path) / "serial.log"
    log_path.write_text(prefix + "uname -m\naarch64\n~ # ", encoding="utf-8")

    result = _server_for_log(log_path)._wait_for_prompt_after_cmd(
        "uname -m", "# ", 1, len(prefix.encode("utf-8"))
    )

    assert result.matched is True
    assert "aarch64" in result.output


def test_wait_for_prompt_after_unseen_echo_accepts_prefixed_prompt(tmp_path):
    """A non-echoed command (e.g. a password) still completes at '~ # '."""
    prefix = "~ # \r\nPassword: \r\n"
    log_path = Path(tmp_path) / "serial.log"
    log_path.write_text(prefix + "~ # \r\n", encoding="utf-8")

    result = _server_for_log(log_path)._wait_for_prompt_after_cmd(
        "secret123", "# ", 1, len(prefix.encode())
    )

    assert result.matched is True


def test_wait_for_prompt_after_unseen_echo_accepts_ansi_colored_prompt(tmp_path):
    prefix = "Password: \r\n"
    log_path = Path(tmp_path) / "serial.log"
    log_path.write_text(prefix + "\x1b[1;32m~ # \x1b[0m\r\n", encoding="utf-8")

    result = _server_for_log(log_path)._wait_for_prompt_after_cmd(
        "secret123", "~ # ", 1, len(prefix.encode())
    )

    assert result.matched is True


def test_wait_for_prompt_after_unseen_echo_accepts_bracket_prompt(tmp_path):
    prefix = "Password: \r\n"
    log_path = Path(tmp_path) / "serial.log"
    log_path.write_text(prefix + "[root@board] # \r\n", encoding="utf-8")

    result = _server_for_log(log_path)._wait_for_prompt_after_cmd(
        "secret123", "[root@board] # ", 1, len(prefix.encode())
    )

    assert result.matched is True


def test_wait_for_prompt_after_cmd_accepts_late_prompt(tmp_path):
    """Wait for the post-command prompt instead of returning an old one."""
    prefix = "~ # \r\n"
    log_path = Path(tmp_path) / "serial.log"
    log_path.write_text(prefix, encoding="utf-8")

    def append_later():
        time.sleep(0.3)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("Password: \r\n~ # \r\n")

    threading.Thread(target=append_later, daemon=True).start()
    result = _server_for_log(log_path)._wait_for_prompt_after_cmd(
        "secret123", "~ # ", 1.5, len(prefix.encode())
    )

    assert result.matched is True
    assert "Password:" in result.output


def test_wait_for_prompt_after_unseen_echo_ignores_prompt_inside_echo(tmp_path):
    """Prompt text in a command line is not completion when echo is missing."""
    prefix = "BOOT\r\n"
    log_path = Path(tmp_path) / "serial.log"
    log_path.write_text(prefix + "~ # echo '# ' \r\n", encoding="utf-8")

    result = _server_for_log(log_path)._wait_for_prompt_after_cmd(
        "secret", "# ", 0.05, len(prefix.encode())
    )

    assert result.matched is False


def test_wait_for_prompt_after_cmd_ignores_old_prompt_without_new_output(tmp_path):
    """Slow authentication must not complete on a prompt from before the mark."""
    prefix = "~ # \r\n"
    log_path = Path(tmp_path) / "serial.log"
    log_path.write_text(prefix, encoding="utf-8")

    result = _server_for_log(log_path)._wait_for_prompt_after_cmd(
        "secret123", "~ # ", 0.7, len(prefix.encode())
    )

    assert result.matched is False


def test_wait_for_string_accepts_prompt_at_end(tmp_path):
    log_path = Path(tmp_path) / "serial.log"
    log_path.write_text("~ # \r\n", encoding="utf-8")

    assert _server_for_log(log_path)._wait_for_string("~ # ", 0.2) is True


def test_wait_for_string_accepts_ansi_colored_prompt(tmp_path):
    log_path = Path(tmp_path) / "serial.log"
    log_path.write_text("\x1b[1;32m~ # \x1b[0m\r\n", encoding="utf-8")

    assert _server_for_log(log_path)._wait_for_string("~ # ", 0.2) is True


def test_to_plain_preserves_text_between_osc_sequences():
    text = (
        "\x1b]8;;file:///a\x1b\\a.txt\x1b]8;;\x1b\\ "
        "\x1b]8;;file:///b\x1b\\b.txt\x1b]8;;\x1b\\"
    )

    assert SocketServer._to_plain(text).strip() == "a.txt b.txt"


def test_wait_for_string_does_not_strip_untimestamped_bracket_line(tmp_path):
    """An untimestamped '[  OK  ]' line is real console output, not a prefix."""
    log_path = Path(tmp_path) / "serial.log"
    log_path.write_text("login: \r\n[  OK  ] \r\n", encoding="utf-8")

    assert _server_for_log(log_path)._wait_for_string("login:", 0.2) is False


def test_wait_for_string_does_not_strip_numeric_bracket_line(tmp_path):
    """A bare '[1]' job-control line is not a logger timestamp."""
    log_path = Path(tmp_path) / "serial.log"
    log_path.write_text("login: \r\n[1] 1234\r\n", encoding="utf-8")

    assert _server_for_log(log_path)._wait_for_string("login:", 0.2) is False


def test_wait_for_string_accepts_prompt_followed_by_timestamped_blank(tmp_path):
    """Timestamped blank lines after the prompt are visually empty."""
    log_path = Path(tmp_path) / "serial.log"
    log_path.write_text(
        "[261109 17:50:30.374] ~ # \r\n"
        "[261109 17:50:30.374] \r\n",
        encoding="utf-8",
    )

    assert _server_for_log(log_path)._wait_for_string("~ # ", 0.2) is True


def test_wait_for_string_with_real_logger_timestamps(tmp_path):
    from ttypal.logger import Logger

    logger = Logger("selftest", directory=str(tmp_path))
    try:
        logger.write("~ # \r\n")
        logger.write("\r\n")
        server = SocketServer(None, logger, "/tmp/unused-ttypal-test.sock")
        assert server._wait_for_string("~ # ", 0.2) is True
    finally:
        logger.close()


def test_wait_for_string_ignores_stale_prompt_followed_by_output(tmp_path):
    """A prompt from before the request must not match once new output follows."""
    log_path = Path(tmp_path) / "serial.log"
    log_path.write_text("~ # \r\nreboot\r\nRequesting system reboot\r\n",
                        encoding="utf-8")

    assert _server_for_log(log_path)._wait_for_string("~ # ", 0.2) is False


def test_wait_for_string_target_spanning_request_boundary(tmp_path):
    """A target split by the request mark must still match after completion."""
    log_path = Path(tmp_path) / "serial.log"
    log_path.write_text("boot...\r\nlog", encoding="utf-8")
    logger = _SignalLogger(log_path)
    server = SocketServer(None, logger, "/tmp/unused-ttypal-test.sock")

    def append_later():
        assert logger.accessed.wait(timeout=2)
        time.sleep(0.05)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("in: ")

    threading.Thread(target=append_later, daemon=True).start()
    assert server._wait_for_string("login:", 2.0) is True


def test_wait_for_string_matches_new_output(tmp_path):
    log_path = Path(tmp_path) / "serial.log"
    log_path.write_text("boot...\r\n", encoding="utf-8")
    server = _server_for_log(log_path)

    def append_later():
        time.sleep(0.1)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("more boot\r\nSV32 login: ")

    threading.Thread(target=append_later, daemon=True).start()
    assert server._wait_for_string("login:", 3.0) is True


def test_wait_for_string_drains_old_file_on_rotation(tmp_path):
    """A target written just before log rotation is not lost."""
    old_path = tmp_path / "old.log"
    new_path = tmp_path / "new.log"
    old_path.write_text("boot...\r\n", encoding="utf-8")
    new_path.write_text("", encoding="utf-8")
    logger = _SignalLogger(old_path)
    server = SocketServer(None, logger, "/tmp/unused-ttypal-test.sock")
    result = {}

    def wait():
        result["matched"] = server._wait_for_string("login:", 2.0)

    thread = threading.Thread(target=wait, daemon=True)
    thread.start()
    assert logger.accessed.wait(timeout=2)
    time.sleep(0.05)
    with open(old_path, "a", encoding="utf-8") as f:
        f.write("login: ")
    logger.current_log = new_path
    thread.join(timeout=3)

    assert result["matched"] is True


def test_wait_for_string_rejects_old_tail_when_new_file_has_output(tmp_path):
    """A stale target followed by new-file output is not at the console end."""
    old_path = tmp_path / "old.log"
    new_path = tmp_path / "new.log"
    old_path.write_text("boot...\r\nlogin: ", encoding="utf-8")
    new_path.write_text("Password: ", encoding="utf-8")
    logger = _RotatingLogger([old_path, new_path])
    server = SocketServer(None, logger, "/tmp/unused-ttypal-test.sock")

    assert server._wait_for_string("login:", 0.3) is False
