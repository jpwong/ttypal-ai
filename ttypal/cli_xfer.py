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


def send_request(sock_path, req, timeout=180):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(sock_path)
    s.settimeout(timeout)
    s.sendall(json.dumps(req).encode() + b"\n")
    s.shutdown(socket.SHUT_WR)

    resp_data = b""
    while True:
        chunk = s.recv(4096)
        if not chunk:
            break
        resp_data += chunk
    s.close()
    return json.loads(resp_data)


def main():
    parser = argparse.ArgumentParser(description="ttypal ZMODEM 文件传输")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--put", metavar="FILE", help="发送本地文件到设备")
    group.add_argument("--get", metavar="REMOTE_FILE", help="从设备接收文件")
    parser.add_argument("dest", nargs="?", help="目标路径（--put 无效，--get 为本地保存目录）")
    parser.add_argument("--board", "-b", help="板子名称 (自动推导 socket 路径)")
    parser.add_argument("--socket", "-s", help="ttypal socket 路径 (覆盖 -b)")
    parser.add_argument("--timeout", "-t", type=int, default=120, help="传输超时秒数 (默认 120)")
    args = parser.parse_args()

    sock_path = args.socket or find_socket(args.board)

    try:
        if args.put:
            if not os.path.isfile(args.put):
                print(f"文件不存在: {args.put}", file=sys.stderr)
                sys.exit(1)
            req = {
                "cmd": "zmodem_send",
                "file": os.path.abspath(args.put),
                "timeout": args.timeout,
            }
            resp = send_request(sock_path, req, timeout=args.timeout + 30)

            if resp.get("status") == "ok":
                print(f"发送成功: {resp.get('bytes_sent', '?')} 字节")
            else:
                print(f"发送失败: {resp.get('message', 'unknown')}", file=sys.stderr)
                sys.exit(1)

        elif args.get:
            local_dir = os.path.abspath(args.dest or ".")
            req = {
                "cmd": "zmodem_recv",
                "remote_file": args.get,
                "local_path": local_dir,
                "timeout": args.timeout,
            }
            resp = send_request(sock_path, req, timeout=args.timeout + 30)

            if resp.get("status") == "ok":
                path = resp.get("path", local_dir)
                size = resp.get("bytes_received", "?")
                print(f"接收成功: {size} 字节 -> {path}")
            else:
                print(f"接收失败: {resp.get('message', 'unknown')}", file=sys.stderr)
                sys.exit(1)

    except ConnectionRefusedError:
        print("无法连接 ttypal，确认是否在运行", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"Socket 不存在: {sock_path}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
