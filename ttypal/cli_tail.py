#!/usr/bin/env python3
import argparse
import os
import sys
import time
from pathlib import Path

from .config import load_board, list_boards
from .logger import SESSION_MARKER_PREFIX


def _get_log_dir(board):
    cfg = load_board(board)
    if cfg:
        log_cfg = cfg.get("log", {})
        directory = log_cfg.get("directory", "~/ttypal-logs")
        d = Path(os.path.expanduser(directory)) / board
        if d.exists():
            return d

    fallback = Path.home() / "ttypal-logs" / board
    if fallback.exists():
        return fallback

    print(f"日志目录不存在: {board}", file=sys.stderr)
    sys.exit(1)


def find_board_log_dir(board=None):
    if board:
        return _get_log_dir(board)

    boards = list_boards()
    if len(boards) == 1:
        return _get_log_dir(boards[0])
    if len(boards) > 1:
        print("多个板子配置，请用 -b 指定:", file=sys.stderr)
        for b in boards:
            print(f"  {b}", file=sys.stderr)
        sys.exit(1)
    print("无板子配置", file=sys.stderr)
    sys.exit(1)


def _read_session_id(filepath):
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            first_line = f.readline().strip()
            if first_line.startswith(SESSION_MARKER_PREFIX):
                return first_line[len(SESSION_MARKER_PREFIX):]
    except Exception:
        pass
    return None


def tail(log_dir, n):
    logs = sorted(log_dir.glob("*.log"))
    if not logs:
        return []

    current_session = _read_session_id(logs[-1])
    collected = []

    for log_file in reversed(logs):
        session_id = _read_session_id(log_file)
        if current_session and session_id != current_session:
            break

        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            lines = [l for l in f.readlines() if not l.startswith(SESSION_MARKER_PREFIX)]

        collected = lines + collected
        if len(collected) >= n:
            break

    return collected[-n:]


def follow(filepath):
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        f.seek(0, 2)
        try:
            while True:
                line = f.readline()
                if line:
                    if not line.startswith(SESSION_MARKER_PREFIX):
                        sys.stdout.write(line)
                        sys.stdout.flush()
                else:
                    time.sleep(0.1)
        except KeyboardInterrupt:
            pass


def _is_daemon_alive(board):
    sock_file = Path(f"/tmp/ttypal-{board}.sock")
    if sock_file.is_socket():
        return True
    pid_file = Path(f"/tmp/ttypal-{board}.pid")
    if not pid_file.exists():
        return False
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 0)
        return True
    except (ValueError, ProcessLookupError, PermissionError):
        return False


def main():
    parser = argparse.ArgumentParser(description="查看 ttypal 串口日志")
    parser.add_argument("-n", "--lines", type=int, default=20, help="显示最后 N 行 (默认 20)")
    parser.add_argument("-f", "--follow", action="store_true", help="持续跟踪输出")
    parser.add_argument("-b", "--board", help="板子名称")
    args = parser.parse_args()

    log_dir = find_board_log_dir(args.board)
    board_name = args.board or log_dir.name

    if not _is_daemon_alive(board_name):
        if args.follow:
            print(f"ttypal ({board_name}) 未运行，无法跟踪实时输出", file=sys.stderr)
            sys.exit(1)
        print(f"注意: ttypal ({board_name}) 未运行，以下为历史日志", file=sys.stderr)

    lines = tail(log_dir, args.lines)
    for line in lines:
        sys.stdout.write(line)

    if args.follow:
        logs = sorted(log_dir.glob("*.log"))
        if logs:
            follow(logs[-1])


if __name__ == "__main__":
    main()
