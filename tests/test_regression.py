"""
回归测试：使用真实串口录制的 fixture 验证
"""
import time
from pathlib import Path

from ttypal.replay_backend import ReplayBackend
from ttypal.logger import Logger

FIXTURES = Path(__file__).parent / "fixtures"


def test_basic_commands_replay(tmp_path):
    backend = ReplayBackend(str(FIXTURES / "basic_commands.rec"), realtime=False)
    backend.open()

    collected = b""
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        data = backend.read()
        if data:
            collected += data
        elif not backend.is_open:
            break
        else:
            time.sleep(0.01)

    text = collected.decode("utf-8", errors="replace")
    assert "hello" in text
    assert "Linux" in text
    assert "rockchip" in text
    assert "load average" in text


def test_basic_commands_logger_output(tmp_path):
    backend = ReplayBackend(str(FIXTURES / "basic_commands.rec"), realtime=False)
    logger = Logger("regtest", directory=str(tmp_path))

    backend.open()
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        data = backend.read()
        if data:
            logger.write(data)
        elif not backend.is_open:
            break
        else:
            time.sleep(0.01)
    logger.close()

    log_files = list((tmp_path / "regtest").glob("*.log"))
    assert len(log_files) >= 1
    content = log_files[0].read_text()
    assert "hello" in content
    assert "rockchip" in content
    # 验证有时间戳
    assert "[" in content


def test_file_ops_replay(tmp_path):
    backend = ReplayBackend(str(FIXTURES / "file_ops.rec"), realtime=False)
    backend.open()

    collected = b""
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        data = backend.read()
        if data:
            collected += data
        elif not backend.is_open:
            break
        else:
            time.sleep(0.01)

    text = collected.decode("utf-8", errors="replace")
    assert "root@rockchip" in text


def test_replay_preserves_tx(tmp_path):
    """验证回放时发送的命令被正确记录"""
    backend = ReplayBackend(str(FIXTURES / "basic_commands.rec"), realtime=False)
    backend.open()
    time.sleep(0.1)

    backend.write("test_cmd\r\n")
    assert b"test_cmd\r\n" in backend.sent_data
    backend.close()
