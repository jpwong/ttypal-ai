"""
AI 端到端测试：验证通过 socket 发命令能得到正确的设备回复。
模拟 AI 的完整工作流：ttypal-send --wait "# " "command"
"""
import json
import socket
import threading
import time
from pathlib import Path

from ttypal.replay_backend import ReplayBackend
from ttypal.logger import Logger
from ttypal.socket_server import SocketServer


FIXTURES = Path(__file__).parent / "fixtures"


def _start_reader(backend, logger, stop_event):
    """模拟 terminal 的 reader 线程：从串口读数据写入 logger"""
    while not stop_event.is_set():
        data = backend.read()
        if data:
            logger.write(data)
        elif not backend.is_open:
            break
        else:
            time.sleep(0.01)


def _send_request(sock_path, req):
    """通过 socket 发请求，返回响应"""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(sock_path)
    s.sendall(json.dumps(req).encode() + b"\n")
    s.shutdown(socket.SHUT_WR)

    resp_data = b""
    while True:
        chunk = s.recv(4096)
        if not chunk:
            break
        resp_data += chunk
    s.close()
    return json.loads(resp_data)


def test_ai_send_echo_gets_correct_output(tmp_path):
    """AI 发送 'echo hello'，验证返回内容包含 'hello'"""
    backend = ReplayBackend(str(FIXTURES / "basic_commands.rec"), realtime=True)
    backend.open()

    logger = Logger("ai_test", directory=str(tmp_path / "logs"))
    sock_path = str(tmp_path / "ai.sock")
    srv = SocketServer(backend, logger, sock_path, "# ")
    srv.start()

    stop = threading.Event()
    reader = threading.Thread(target=_start_reader, args=(backend, logger, stop))
    reader.start()

    # 等录制前几个 RX 事件播放完（prompt 出现）
    time.sleep(0.3)

    resp = _send_request(sock_path, {
        "cmd": "send_wait",
        "data": "echo hello",
        "prompt": "# ",
        "timeout": 5,
    })

    assert resp["status"] == "ok"
    assert "hello" in resp["output"]

    stop.set()
    srv.stop()
    reader.join(timeout=2)
    logger.close()


def test_ai_send_uname_gets_kernel_info(tmp_path):
    """AI 发送 'uname -a'，验证返回内容包含 Linux 内核信息"""
    backend = ReplayBackend(str(FIXTURES / "basic_commands.rec"), realtime=True)
    backend.open()

    logger = Logger("ai_test2", directory=str(tmp_path / "logs"))
    sock_path = str(tmp_path / "ai2.sock")
    srv = SocketServer(backend, logger, sock_path, "# ")
    srv.start()

    stop = threading.Event()
    reader = threading.Thread(target=_start_reader, args=(backend, logger, stop))
    reader.start()

    # 等所有 RX 播放完
    time.sleep(0.5)

    resp = _send_request(sock_path, {
        "cmd": "send_wait",
        "data": "uname -a",
        "prompt": "# ",
        "timeout": 5,
    })

    assert resp["status"] == "ok"
    assert "Linux" in resp["output"]
    assert "rockchip" in resp["output"]

    stop.set()
    srv.stop()
    reader.join(timeout=2)
    logger.close()


def test_ai_send_simple_no_wait(tmp_path):
    """AI 发送命令不等待回复（fire-and-forget），验证命令被发到串口"""
    backend = ReplayBackend(str(FIXTURES / "basic_commands.rec"), realtime=False)
    backend.open()

    logger = Logger("ai_test3", directory=str(tmp_path / "logs"))
    sock_path = str(tmp_path / "ai3.sock")
    srv = SocketServer(backend, logger, sock_path, "# ")
    srv.start()

    time.sleep(0.1)

    resp = _send_request(sock_path, {
        "cmd": "send",
        "data": "reboot",
    })

    assert resp["status"] == "ok"
    assert b"reboot\r\n" in backend.sent_data

    srv.stop()
    logger.close()


def test_ai_send_wait_timeout(tmp_path):
    """AI 发命令等待一个不会出现的 prompt，验证超时后仍返回已收集的数据"""
    backend = ReplayBackend(str(FIXTURES / "basic_commands.rec"), realtime=True)
    backend.open()

    logger = Logger("ai_test4", directory=str(tmp_path / "logs"))
    sock_path = str(tmp_path / "ai4.sock")
    srv = SocketServer(backend, logger, sock_path, "# ")
    srv.start()

    stop = threading.Event()
    reader = threading.Thread(target=_start_reader, args=(backend, logger, stop))
    reader.start()

    time.sleep(0.3)

    resp = _send_request(sock_path, {
        "cmd": "send_wait",
        "data": "ls",
        "prompt": "IMPOSSIBLE_PROMPT>>> ",
        "timeout": 1,
    })

    # 超时也应该返回 ok 并附带已收集的输出
    assert resp["status"] == "ok"
    assert "output" in resp

    stop.set()
    srv.stop()
    reader.join(timeout=2)
    logger.close()
