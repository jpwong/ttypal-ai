#!/usr/bin/env python3
"""ttypal-daemon: headless serial daemon for AI automation"""
import argparse
import os
import signal
import sys
import threading
import time
from pathlib import Path


PID_DIR = Path("/tmp")


def _pid_file(board_name):
    return PID_DIR / f"ttypal-{board_name}.pid"


def _sock_file(board_name):
    return PID_DIR / f"ttypal-{board_name}.sock"


def _read_pid(board_name):
    pf = _pid_file(board_name)
    if not pf.exists():
        return None
    try:
        pid = int(pf.read_text().strip())
        os.kill(pid, 0)
        return pid
    except (ValueError, ProcessLookupError, PermissionError):
        pf.unlink(missing_ok=True)
        return None


def _find_running():
    boards = []
    for f in PID_DIR.glob("ttypal-*.pid"):
        name = f.stem.replace("ttypal-", "")
        if _read_pid(name):
            boards.append(name)
    return boards


def cmd_start(args):
    from ttypal.config import load_board, list_boards

    board = args.board
    if not board:
        boards = list_boards()
        if not boards:
            print("没有板子配置，请先运行 ttypal 创建")
            sys.exit(1)
        if len(boards) == 1:
            board = boards[0]
        else:
            print("多个板子配置，请用 -b 指定:")
            for b in boards:
                print(f"  {b}")
            sys.exit(1)

    if _read_pid(board):
        print(f"ttypal-daemon ({board}) 已在运行")
        return

    cfg = load_board(board)
    if cfg is None:
        print(f"配置 '{board}' 不存在")
        sys.exit(1)

    pid = os.fork()
    if pid > 0:
        # parent — wait for daemon to be ready
        for _ in range(10):
            time.sleep(0.5)
            if _sock_file(board).exists():
                print(f"ttypal-daemon ({board}) 已启动 [PID {pid}]")
                print(f"  socket: {_sock_file(board)}")
                return
        # check if child is still alive
        try:
            os.kill(pid, 0)
            print(f"ttypal-daemon ({board}) 启动中 [PID {pid}]")
        except ProcessLookupError:
            print(f"启动失败，查看日志: /tmp/ttypal-daemon-{board}.log")
            sys.exit(1)
        return

    # child — daemonize
    os.setsid()
    sys.stdin.close()

    log_path = f"/tmp/ttypal-daemon-{board}.log"
    log_fd = open(log_path, "a")
    os.dup2(log_fd.fileno(), 1)
    os.dup2(log_fd.fileno(), 2)

    _pid_file(board).write_text(str(os.getpid()))

    try:
        _run_daemon(board, cfg)
    finally:
        _pid_file(board).unlink(missing_ok=True)


def _run_daemon(board, cfg):
    from ttypal.serial_conn import SerialConnection
    from ttypal.logger import Logger
    from ttypal.socket_server import SocketServer

    ser_cfg = cfg["serial"]
    log_cfg = cfg.get("log", {})
    sock_cfg = cfg.get("socket", {})

    conn = SerialConnection(
        port=ser_cfg["port"],
        baudrate=ser_cfg["baudrate"],
        bytesize=ser_cfg.get("bytesize", 8),
        parity=ser_cfg.get("parity", "none"),
        stopbits=ser_cfg.get("stopbits", 1),
        rtscts=ser_cfg.get("rtscts", False),
        dtr=ser_cfg.get("dtr", False),
        rts=ser_cfg.get("rts", False),
    )

    logger = Logger(
        board_name=board,
        directory=log_cfg.get("directory", "~/ttypal-logs"),
        rotate_size_kb=log_cfg.get("rotate_size_kb", 10240),
        timestamp_format=log_cfg.get("timestamp_format", "%y%m%d %H:%M:%S.%f"),
    )

    sock_path = sock_cfg.get("path", f"/tmp/ttypal-{board}.sock")
    sock_path = sock_path.replace("{name}", board)
    prompt = sock_cfg.get("prompt", "# ")

    conn.open()

    srv = SocketServer(conn, logger, sock_path, prompt)
    srv.start()

    running = True

    def handle_term(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, handle_term)
    signal.signal(signal.SIGINT, handle_term)

    def reader():
        while running:
            try:
                data = conn.read()
                if data:
                    logger.write(data)
            except Exception:
                break

    t = threading.Thread(target=reader, daemon=True)
    t.start()

    while running:
        time.sleep(0.5)

    srv.stop()
    conn.close()
    logger.close()


def cmd_stop(args):
    board = args.board
    if board:
        boards = [board]
    else:
        boards = _find_running()
        if not boards:
            print("没有运行中的 ttypal-daemon")
            return

    for b in boards:
        pid = _read_pid(b)
        if pid:
            os.kill(pid, signal.SIGTERM)
            _pid_file(b).unlink(missing_ok=True)
            print(f"ttypal-daemon ({b}) 已停止 [PID {pid}]")
        else:
            print(f"ttypal-daemon ({b}) 未在运行")


def cmd_status(args):
    board = args.board
    if board:
        pid = _read_pid(board)
        if pid:
            print(f"ttypal-daemon ({board}): 运行中 [PID {pid}]")
            print(f"  socket: {_sock_file(board)}")
        else:
            print(f"ttypal-daemon ({board}): 未运行")
    else:
        boards = _find_running()
        if not boards:
            print("没有运行中的 ttypal-daemon")
        else:
            for b in boards:
                pid = _read_pid(b)
                print(f"ttypal-daemon ({b}): 运行中 [PID {pid}]")
                print(f"  socket: {_sock_file(b)}")


def main():
    parser = argparse.ArgumentParser(
        prog="ttypal-daemon",
        description="ttypal 后台 daemon（供 AI 自动化使用）",
    )
    sub = parser.add_subparsers(dest="command")

    p_start = sub.add_parser("start", help="启动 daemon")
    p_start.add_argument("-b", "--board", help="板子配置名称")

    p_stop = sub.add_parser("stop", help="停止 daemon")
    p_stop.add_argument("-b", "--board", help="板子名称（不指定则停止所有）")

    p_status = sub.add_parser("status", help="查看运行状态")
    p_status.add_argument("-b", "--board", help="板子名称")

    args = parser.parse_args()

    if args.command == "start":
        cmd_start(args)
    elif args.command == "stop":
        cmd_stop(args)
    elif args.command == "status":
        cmd_status(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
