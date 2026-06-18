#!/usr/bin/env python3
import argparse
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
    parser = argparse.ArgumentParser(
        description="向 ttypal 发送串口命令",
        epilog=(
            "Python API: from ttypal.client import TtypalClient; "
            "client = TtypalClient(session='name')"
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("command", nargs="?", default="", help="要发送的命令")
    parser.add_argument("-b", "--board", help="板子配置名称 (通过 profile 查找 session)")
    parser.add_argument("-S", "--session", help="Session 名称 (直接查找)")
    parser.add_argument("--socket", "-s", help="ttypal socket 路径 (覆盖 -b/-S)")
    parser.add_argument("--wait", "-w", metavar="PROMPT", help="等待指定 prompt 后返回输出")
    parser.add_argument("--wait-for", metavar="STRING", help="发送前等待指定字符串出现")
    parser.add_argument("--probe", action="store_true", help="发送回车并返回设备响应（探测设备状态）")
    parser.add_argument("--timeout", "-t", type=float, default=10, help="等待超时秒数 (默认 10)")
    args = parser.parse_args()

    try:
        client = _client_from_args(args)
        output = None

        if args.probe:
            timeout = args.timeout if args.timeout != 10 else 2
            output = client.probe(timeout=timeout)
        elif args.wait_for and args.wait:
            output = client.expect_send_wait(
                args.wait_for, args.command, prompt=args.wait, timeout=args.timeout
            )
        elif args.wait_for:
            client.expect_send(args.wait_for, args.command, timeout=args.timeout)
        elif args.wait:
            output = client.send_wait(args.command, prompt=args.wait, timeout=args.timeout)
        else:
            client.send(args.command)

        if output is not None:
            print(output, end="")
    except TtypalClientError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
