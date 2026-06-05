#!/usr/bin/env python3
import argparse
import os
import sys
import time
from pathlib import Path

from .config import load_board, list_boards
from .logger import SESSION_MARKER_PREFIX
from .session import list_sessions, load_session


def _get_log_dir(session_name):
    """Get log directory for a session or board name."""
    # Try session metadata first
    info = load_session(session_name)
    if info:
        profile = info.get("profile")
        cfg = load_board(profile) if profile else None
        if cfg:
            log_cfg = cfg.get("log", {})
            directory = log_cfg.get("directory", "~/ttypal-logs")
            d = Path(os.path.expanduser(directory)) / session_name
            if d.exists():
                return d

    # Try loading board config directly (works when no session is running)
    cfg = load_board(session_name)
    if cfg:
        log_cfg = cfg.get("log", {})
        directory = log_cfg.get("directory", "~/ttypal-logs")
        d = Path(os.path.expanduser(directory)) / session_name
        if d.exists():
            return d

    # Fallback: try common locations
    for base in [Path.home() / "ttypal-logs", Path.home() / "workspace" / "ttypal-logs"]:
        d = base / session_name
        if d.exists():
            return d

    print(f"日志目录不存在: {session_name}", file=sys.stderr)
    sys.exit(1)


def _resolve_session(session=None, board=None):
    """Resolve session name from -S or -b flags."""
    if session:
        if not load_session(session):
            print(f"Session '{session}' not found or not running", file=sys.stderr)
            sys.exit(1)
        return session

    sessions = list_sessions()

    if board:
        matches = [name for name, info in sessions if info.get("profile") == board]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            print(f"Multiple sessions with profile '{board}', use -S to specify:", file=sys.stderr)
            for name in matches:
                print(f"  {name}", file=sys.stderr)
            sys.exit(1)
        # No matching session, try using board name directly (legacy)
        return board

    # Auto-detect
    if len(sessions) == 1:
        return sessions[0][0]
    if len(sessions) > 1:
        print("Multiple sessions running, use -b or -S to specify:", file=sys.stderr)
        for name, info in sessions:
            print(f"  {name} (profile: {info.get('profile', '?')})", file=sys.stderr)
        sys.exit(1)

    # No sessions, try to find any log directory
    boards = list_boards()
    if len(boards) == 1:
        return boards[0]
    if len(boards) > 1:
        print("多个板子配置，请用 -b 或 -S 指定:", file=sys.stderr)
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


def _is_daemon_alive(session_name):
    sock_file = Path(f"/tmp/ttypal-{session_name}.sock")
    if sock_file.is_socket():
        return True
    pid_file = Path(f"/tmp/ttypal-{session_name}.pid")
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
    parser.add_argument("-b", "--board", help="板子配置名称")
    parser.add_argument("-S", "--session", help="Session 名称")
    args = parser.parse_args()

    session_name = _resolve_session(session=args.session, board=args.board)
    log_dir = _get_log_dir(session_name)

    if not _is_daemon_alive(session_name):
        if args.follow:
            print(f"ttypal ({session_name}) 未运行，无法跟踪实时输出", file=sys.stderr)
            sys.exit(1)
        print(f"注意: ttypal ({session_name}) 未运行，以下为历史日志", file=sys.stderr)

    lines = tail(log_dir, args.lines)
    for line in lines:
        sys.stdout.write(line)

    if args.follow:
        logs = sorted(log_dir.glob("*.log"))
        if logs:
            follow(logs[-1])


if __name__ == "__main__":
    main()
