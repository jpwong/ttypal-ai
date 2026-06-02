"""
集成测试：用 ReplayBackend 跑完整链路
- socket server 接收命令 → 写入串口
- logger 记录输出
"""
import json
import socket
import threading
import time
from pathlib import Path

from ttypal.replay_backend import ReplayBackend
from ttypal.logger import Logger
from ttypal.socket_server import SocketServer


def _create_recording(tmp_path):
    rec_file = tmp_path / "session.rec"
    # 模拟设备输出 prompt，然后输出命令结果，再输出 prompt
    events = [
        {"t": 0.0, "dir": "rx", "hex": b"root@board:~# ".hex()},
        {"t": 0.5, "dir": "rx", "hex": b"file1  file2\r\n".hex()},
        {"t": 0.6, "dir": "rx", "hex": b"root@board:~# ".hex()},
    ]
    with open(rec_file, "w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")
    return str(rec_file)


def test_socket_send(tmp_path):
    rec_path = _create_recording(tmp_path)
    backend = ReplayBackend(rec_path, realtime=False)
    backend.open()

    logger = Logger("integration", directory=str(tmp_path / "logs"))
    sock_path = str(tmp_path / "test.sock")
    srv = SocketServer(backend, logger, sock_path, "# ")
    srv.start()

    time.sleep(0.1)

    # send a command
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(sock_path)
    req = json.dumps({"cmd": "send", "data": "ls"}) + "\n"
    s.sendall(req.encode())
    s.shutdown(socket.SHUT_WR)

    resp_data = b""
    while True:
        chunk = s.recv(4096)
        if not chunk:
            break
        resp_data += chunk
    s.close()

    resp = json.loads(resp_data)
    assert resp["status"] == "ok"
    assert backend.sent_data == b"ls\r\n"

    srv.stop()
    logger.close()


def test_socket_send_wait(tmp_path):
    # 创建一个带延迟的录制，模拟命令响应
    rec_file = tmp_path / "session2.rec"
    events = [
        {"t": 0.0, "dir": "rx", "hex": b"# ".hex()},
        {"t": 0.2, "dir": "rx", "hex": b"output line\r\n".hex()},
        {"t": 0.3, "dir": "rx", "hex": b"# ".hex()},
    ]
    with open(rec_file, "w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")

    backend = ReplayBackend(str(rec_file), realtime=True)
    backend.open()

    logger = Logger("integration2", directory=str(tmp_path / "logs2"))
    sock_path = str(tmp_path / "test2.sock")
    srv = SocketServer(backend, logger, sock_path, "# ")
    srv.start()

    time.sleep(0.2)

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(sock_path)
    req = json.dumps({"cmd": "send_wait", "data": "ls", "prompt": "# ", "timeout": 3}) + "\n"
    s.sendall(req.encode())
    s.shutdown(socket.SHUT_WR)

    resp_data = b""
    while True:
        chunk = s.recv(4096)
        if not chunk:
            break
        resp_data += chunk
    s.close()

    resp = json.loads(resp_data)
    assert resp["status"] == "ok"
    assert "output" in resp

    srv.stop()
    logger.close()


def test_logger_captures_replay_output(tmp_path):
    rec_path = _create_recording(tmp_path)
    backend = ReplayBackend(rec_path, realtime=False)

    logger = Logger("capture_test", directory=str(tmp_path / "logs3"))
    backend.open()

    time.sleep(0.2)
    while True:
        data = backend.read()
        if not data:
            break
        logger.write(data)

    logger.close()

    log_files = list((tmp_path / "logs3" / "capture_test").glob("*.log"))
    assert len(log_files) == 1
    content = log_files[0].read_text()
    assert "root@board" in content
    assert "file1" in content


def test_socket_probe(tmp_path):
    rec_file = tmp_path / "session_probe.rec"
    events = [
        {"t": 0.0, "dir": "rx", "hex": b"root@board:~# ".hex()},
    ]
    with open(rec_file, "w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")

    backend = ReplayBackend(str(rec_file), realtime=True)
    backend.open()

    logger = Logger("probe_test", directory=str(tmp_path / "logs_probe"))
    sock_path = str(tmp_path / "probe.sock")
    srv = SocketServer(backend, logger, sock_path, "# ")
    srv.start()

    time.sleep(0.2)

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(sock_path)
    req = json.dumps({"cmd": "probe", "timeout": 1}) + "\n"
    s.sendall(req.encode())
    s.shutdown(socket.SHUT_WR)

    resp_data = b""
    while True:
        chunk = s.recv(4096)
        if not chunk:
            break
        resp_data += chunk
    s.close()

    resp = json.loads(resp_data)
    assert resp["status"] == "ok"
    assert "output" in resp
    assert backend.sent_data == b"\r\n"

    srv.stop()
    logger.close()
