from pathlib import Path

from ttypal.socket_server import SocketServer


class _Logger:
    current_log = ""


def _server_for_log(path):
    logger = _Logger()
    logger.current_log = str(path)
    return SocketServer(None, logger, "/tmp/unused-ttypal-test.sock")


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
