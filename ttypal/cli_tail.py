#!/usr/bin/env python3
import argparse
import os
import sys
import time
import glob
from pathlib import Path


LOG_BASE = Path.home() / "ttypal-logs"


def find_board_log_dir(board=None):
    if board:
        d = LOG_BASE / board
        if d.exists():
            return d
        print(f"日志目录不存在: {d}", file=sys.stderr)
        sys.exit(1)

    if not LOG_BASE.exists():
        print(f"日志目录不存在: {LOG_BASE}", file=sys.stderr)
        sys.exit(1)

    boards = sorted(LOG_BASE.iterdir())
    if len(boards) == 1:
        return boards[0]
    if len(boards) > 1:
        print("多个板子日志，请用 -b 指定:", file=sys.stderr)
        for b in boards:
            print(f"  {b.name}", file=sys.stderr)
        sys.exit(1)
    print("无日志", file=sys.stderr)
    sys.exit(1)


def latest_log(log_dir):
    logs = sorted(log_dir.glob("*.log"))
    if not logs:
        print("无日志文件", file=sys.stderr)
        sys.exit(1)
    return logs[-1]


def tail(filepath, n):
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
        return lines[-n:]


def follow(filepath):
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        f.seek(0, 2)
        try:
            while True:
                line = f.readline()
                if line:
                    sys.stdout.write(line)
                    sys.stdout.flush()
                else:
                    time.sleep(0.1)
        except KeyboardInterrupt:
            pass


def main():
    parser = argparse.ArgumentParser(description="查看 ttypal 串口日志")
    parser.add_argument("-n", "--lines", type=int, default=20, help="显示最后 N 行 (默认 20)")
    parser.add_argument("-f", "--follow", action="store_true", help="持续跟踪输出")
    parser.add_argument("-b", "--board", help="板子名称")
    args = parser.parse_args()

    log_dir = find_board_log_dir(args.board)
    log_file = latest_log(log_dir)

    lines = tail(log_file, args.lines)
    for line in lines:
        sys.stdout.write(line)

    if args.follow:
        follow(log_file)


if __name__ == "__main__":
    main()
