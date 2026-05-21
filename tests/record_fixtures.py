#!/usr/bin/env python3
"""录制测试用的串口数据"""
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ttypal.serial_conn import SerialConnection
from ttypal.recorder import Recorder

OUTPUT_DIR = Path(__file__).parent / "fixtures"
OUTPUT_DIR.mkdir(exist_ok=True)


def record_session(name, commands, prompt="# ", timeout=3):
    rec_path = OUTPUT_DIR / f"{name}.rec"
    recorder = Recorder(output_path=str(rec_path))

    conn = SerialConnection(
        port="/dev/ttyUSB1",
        baudrate=1500000,
        dtr=False,
        rts=False,
        recorder=recorder,
    )

    print(f"录制: {name}")
    conn.open()
    time.sleep(0.5)

    # 先发回车唤醒，等 prompt
    conn.write("\r\n")
    _wait_prompt(conn, prompt, timeout)

    for cmd in commands:
        print(f"  发送: {cmd}")
        conn.write(cmd + "\r\n")
        _wait_prompt(conn, prompt, timeout)

    conn.close()
    recorder.close()
    print(f"  保存: {rec_path}")
    print()


def _wait_prompt(conn, prompt, timeout):
    buf = b""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        data = conn.read()
        if data:
            buf += data
            if prompt.encode() in buf.split(b"\n")[-1]:
                return buf
    return buf


if __name__ == "__main__":
    # Session 1: 基本命令
    record_session("basic_commands", [
        "echo hello",
        "uname -a",
        "uptime",
    ])

    # Session 2: 文件操作
    record_session("file_ops", [
        "ls /tmp",
        "cat /proc/version",
    ])

    # Session 3: 空回车（测试纯 prompt 响应）
    record_session("empty_input", [
        "",
    ])

    print("录制完成！")
