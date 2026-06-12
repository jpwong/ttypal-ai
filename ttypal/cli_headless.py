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


def _pid_file(session_name):
    return PID_DIR / f"ttypal-{session_name}.pid"


def _sock_file(session_name):
    return PID_DIR / f"ttypal-{session_name}.sock"


def _read_pid(session_name):
    pf = _pid_file(session_name)
    if not pf.exists():
        return None
    try:
        pid = int(pf.read_text().strip())
    except PermissionError:
        return None
    except ValueError:
        try:
            pf.unlink(missing_ok=True)
        except PermissionError:
            pass
        return None
    try:
        os.kill(pid, 0)
        return pid
    except PermissionError:
        return pid
    except ProcessLookupError:
        try:
            pf.unlink(missing_ok=True)
        except PermissionError:
            pass
        return None


def _find_running():
    from .session import list_sessions
    return [name for name, _ in list_sessions()]


def cmd_start(args):
    from ttypal.config import load_board, list_boards
    from ttypal.session import save_session

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

    session_name = args.session or board

    if _read_pid(session_name):
        print(f"ttypal-daemon ({session_name}) 已在运行")
        return

    cfg = load_board(board)
    if cfg is None:
        print(f"配置 '{board}' 不存在")
        sys.exit(1)

    # Apply overrides
    if args.port:
        cfg["serial"]["port"] = args.port
    if args.baudrate:
        cfg["serial"]["baudrate"] = args.baudrate

    pid = os.fork()
    if pid > 0:
        # parent — wait for daemon to be ready
        for _ in range(10):
            time.sleep(0.5)
            if _sock_file(session_name).exists():
                print(f"ttypal-daemon ({session_name}) 已启动 [PID {pid}]")
                print(f"  socket: {_sock_file(session_name)}")
                return
        # check if child is still alive
        try:
            os.kill(pid, 0)
            print(f"ttypal-daemon ({session_name}) 启动中 [PID {pid}]")
        except ProcessLookupError:
            print(f"启动失败，查看日志: /tmp/ttypal-daemon-{session_name}.log")
            sys.exit(1)
        return

    # child — daemonize
    os.setsid()
    sys.stdin.close()

    log_path = f"/tmp/ttypal-daemon-{session_name}.log"
    log_fd = open(log_path, "a")
    os.dup2(log_fd.fileno(), 1)
    os.dup2(log_fd.fileno(), 2)

    _pid_file(session_name).write_text(str(os.getpid()))

    # Save session metadata
    from datetime import datetime
    ser_cfg = cfg["serial"]
    sock_cfg = cfg.get("socket", {})
    # Session name determines runtime socket/pid/log paths
    sock_path = f"/tmp/ttypal-{session_name}.sock"
    prompt = sock_cfg.get("prompt", "# ")

    session_info = {
        "profile": board,
        "port": ser_cfg["port"],
        "baudrate": ser_cfg["baudrate"],
        "socket": sock_path,
        "pid": os.getpid(),
        "started": datetime.now().isoformat(),
    }
    save_session(session_name, session_info)

    try:
        _run_daemon(session_name, cfg)
    finally:
        _pid_file(session_name).unlink(missing_ok=True)
        from .session import remove_session
        remove_session(session_name, pid=os.getpid())


def _run_daemon(session_name, cfg):
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
        board_name=session_name,
        directory=log_cfg.get("directory", "~/ttypal-logs"),
        rotate_size_kb=log_cfg.get("rotate_size_kb", 10240),
        timestamp_format=log_cfg.get("timestamp_format", "%y%m%d %H:%M:%S.%f"),
    )

    sock_path = f"/tmp/ttypal-{session_name}.sock"
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
    from .session import remove_session

    session_name = args.session
    board = args.board

    if session_name:
        sessions = [session_name]
    elif board:
        from .session import list_sessions
        all_sessions = list_sessions()
        sessions = [name for name, info in all_sessions if info.get("profile") == board]
        if not sessions:
            print(f"ttypal-daemon ({board}) 未在运行")
            return
    else:
        sessions = _find_running()
        if not sessions:
            print("没有运行中的 ttypal-daemon")
            return

    for s in sessions:
        pid = _read_pid(s)
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
            except PermissionError:
                print(f"ttypal-daemon ({s}) 正在运行但当前用户无权限停止 [PID {pid}]")
                continue
            try:
                _pid_file(s).unlink(missing_ok=True)
            except PermissionError:
                pass
            remove_session(s)
            print(f"ttypal-daemon ({s}) 已停止 [PID {pid}]")
        else:
            print(f"ttypal-daemon ({s}) 未在运行")


def cmd_status(args):
    from .session import list_sessions, load_session

    session_name = args.session
    board = args.board

    if session_name:
        info = load_session(session_name)
        if info:
            pid = info.get("pid", "?")
            print(f"ttypal-daemon ({session_name}): 运行中 [PID {pid}]")
            print(f"  profile: {info.get('profile', '?')}")
            print(f"  port: {info.get('port', '?')}")
            print(f"  baudrate: {info.get('baudrate', '?')}")
            print(f"  socket: {info.get('socket', '?')}")
        else:
            print(f"ttypal-daemon ({session_name}): 未运行")
    elif board:
        all_sessions = list_sessions()
        matches = [(name, info) for name, info in all_sessions if info.get("profile") == board]
        if not matches:
            print(f"ttypal-daemon ({board}): 未运行")
        else:
            for name, info in matches:
                pid = info.get("pid", "?")
                print(f"ttypal-daemon ({name}): 运行中 [PID {pid}]")
                print(f"  profile: {info.get('profile', '?')}")
                print(f"  port: {info.get('port', '?')}")
                print(f"  baudrate: {info.get('baudrate', '?')}")
                print(f"  socket: {info.get('socket', '?')}")
    else:
        all_sessions = list_sessions()
        if not all_sessions:
            print("没有运行中的 ttypal-daemon")
        else:
            for name, info in all_sessions:
                pid = info.get("pid", "?")
                print(f"ttypal-daemon ({name}): 运行中 [PID {pid}]")
                print(f"  profile: {info.get('profile', '?')}")
                print(f"  port: {info.get('port', '?')}")
                print(f"  baudrate: {info.get('baudrate', '?')}")
                print(f"  socket: {info.get('socket', '?')}")


def main():
    from ttypal import __version__
    parser = argparse.ArgumentParser(
        prog="ttypal-daemon",
        description="ttypal 后台 daemon（供 AI 自动化使用）",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")

    p_start = sub.add_parser("start", help="启动 daemon")
    p_start.add_argument("-b", "--board", help="板子配置名称")
    p_start.add_argument("-S", "--session", help="Session 名称（运行时身份）")
    p_start.add_argument("--port", help="覆盖串口路径")
    p_start.add_argument("--baudrate", type=int, help="覆盖波特率")

    p_stop = sub.add_parser("stop", help="停止 daemon")
    p_stop.add_argument("-S", "--session", help="Session 名称")
    p_stop.add_argument("-b", "--board", help="板子配置名称（停止该 profile 的所有 session）")

    p_status = sub.add_parser("status", help="查看运行状态")
    p_status.add_argument("-S", "--session", help="Session 名称")
    p_status.add_argument("-b", "--board", help="板子配置名称")

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
