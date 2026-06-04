#!/usr/bin/env python3
import argparse
import json
import os
import socket
import sys
import glob


def find_socket(board=None):
    if board:
        sock = f"/tmp/ttypal-{board}.sock"
        if not os.path.exists(sock):
            print(f"板子 '{board}' 的 ttypal 未运行 (未找到 {sock})", file=sys.stderr)
            sys.exit(1)
        return sock
    socks = glob.glob("/tmp/ttypal-*.sock")
    if len(socks) == 1:
        return socks[0]
    if len(socks) > 1:
        print("多个 ttypal 实例运行中，请用 -b 或 --socket 指定:", file=sys.stderr)
        for s in socks:
            print(f"  {s}", file=sys.stderr)
        sys.exit(1)
    print("未找到运行中的 ttypal 实例", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="向 ttypal 发送串口命令")
    parser.add_argument("command", nargs="?", default="", help="要发送的命令")
    parser.add_argument("--board", "-b", help="板子名称 (自动推导 socket 路径)")
    parser.add_argument("--socket", "-s", help="ttypal socket 路径 (覆盖 -b)")
    parser.add_argument("--wait", "-w", metavar="PROMPT", help="等待指定 prompt 后返回输出")
    parser.add_argument("--wait-for", metavar="STRING", help="发送前等待指定字符串出现")
    parser.add_argument("--probe", action="store_true", help="发送回车并返回设备响应（探测设备状态）")
    parser.add_argument("--timeout", "-t", type=float, default=10, help="等待超时秒数 (默认 10)")
    args = parser.parse_args()

    sock_path = args.socket or find_socket(args.board)

    if args.probe:
        req = {"cmd": "probe", "timeout": args.timeout if args.timeout != 10 else 2}
    elif args.wait_for and args.wait:
        req = {"cmd": "expect_send_wait", "expect": args.wait_for,
               "data": args.command, "prompt": args.wait, "timeout": args.timeout}
    elif args.wait_for:
        req = {"cmd": "expect_send", "expect": args.wait_for,
               "data": args.command, "timeout": args.timeout}
    elif args.wait:
        req = {"cmd": "send_wait", "data": args.command,
               "prompt": args.wait, "timeout": args.timeout}
    else:
        req = {"cmd": "send", "data": args.command}

    try:
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

        resp = json.loads(resp_data)
        if resp.get("status") == "ok":
            if "output" in resp:
                print(resp["output"], end="")
        else:
            print(f"错误: {resp.get('message', 'unknown')}", file=sys.stderr)
            sys.exit(1)
    except ConnectionRefusedError:
        print("无法连接 ttypal，确认是否在运行", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"Socket 不存在: {sock_path}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
