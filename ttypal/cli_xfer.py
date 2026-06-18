#!/usr/bin/env python3
import argparse
import os
import sys

from .client import TtypalClient, TtypalClientError


def _client_from_args(args):
    if args.socket:
        return TtypalClient(socket_path=args.socket)
    if args.session:
        return TtypalClient(session=args.session)
    if args.board:
        return TtypalClient(board=args.board)
    return TtypalClient()


def main():
    from ttypal import __version__
    parser = argparse.ArgumentParser(description="ttypal ZMODEM 文件传输")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--put", metavar="FILE", help="发送本地文件到设备")
    group.add_argument("--get", metavar="REMOTE_FILE", help="从设备接收文件")
    parser.add_argument("dest", nargs="?", help="目标路径（--put 无效，--get 为本地保存目录）")
    parser.add_argument("-b", "--board", help="板子配置名称 (通过 profile 查找 session)")
    parser.add_argument("-S", "--session", help="Session 名称 (直接查找)")
    parser.add_argument("--socket", "-s", help="ttypal socket 路径 (覆盖 -b/-S)")
    parser.add_argument("--timeout", "-t", type=int, default=120, help="传输超时秒数 (默认 120)")
    args = parser.parse_args()

    try:
        client = _client_from_args(args)

        if args.put:
            if not os.path.isfile(args.put):
                print(f"文件不存在: {args.put}", file=sys.stderr)
                sys.exit(1)
            resp = client.request(
                {
                    "cmd": "zmodem_send",
                    "file": os.path.abspath(args.put),
                    "timeout": args.timeout,
                },
                operation_timeout=args.timeout,
                io_timeout=args.timeout + 30,
            )
            print(f"发送成功: {resp.get('bytes_sent', '?')} 字节")

        elif args.get:
            local_dir = os.path.abspath(args.dest or ".")
            resp = client.request(
                {
                    "cmd": "zmodem_recv",
                    "remote_file": args.get,
                    "local_path": local_dir,
                    "timeout": args.timeout,
                },
                operation_timeout=args.timeout,
                io_timeout=args.timeout + 30,
            )
            path = resp.get("path", local_dir)
            size = resp.get("bytes_received", "?")
            print(f"接收成功: {size} 字节 -> {path}")

    except TtypalClientError as exc:
        action = "发送" if args.put else "接收"
        print(f"{action}失败: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
