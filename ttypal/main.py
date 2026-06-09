#!/usr/bin/env python3
import argparse
import sys
import os

from ttypal import __version__
from ttypal.config import resolve_config, select_board
from ttypal.serial_conn import SerialConnection
from ttypal.logger import Logger
from ttypal.socket_server import SocketServer
from ttypal.terminal import Terminal


def main():
    parser = argparse.ArgumentParser(
        prog="ttypal",
        description="ttypal — 你的串口调试伙伴",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-b", "--board", help="板子配置名称")
    parser.add_argument("-S", "--session", help="Session 名称（运行时身份）")
    parser.add_argument("-p", "--port", help="覆盖串口路径")
    parser.add_argument("--baudrate", type=int, help="覆盖波特率")
    parser.add_argument("--save-as", metavar="NAME", help="保存当前参数为新配置")
    parser.add_argument("--record", metavar="FILE", help="录制串口数据到文件")
    parser.add_argument("--replay", metavar="FILE", help="回放录制文件（替代真实串口）")
    parser.add_argument("--realtime", action="store_true", help="回放时保持原始时序")
    args = parser.parse_args()

    if args.replay:
        from ttypal.replay_backend import ReplayBackend
        conn = ReplayBackend(args.replay, realtime=args.realtime)
        name = "replay"
        # minimal config for replay mode
        cfg = {"log": {}, "socket": {"path": f"/tmp/ttypal-replay.sock", "prompt": "# "}, "record": {}}
    else:
        name, cfg = resolve_config(args)
        if args.save_as:
            from ttypal.config import save_board
            save_board(args.save_as, cfg)
            print(f"已保存配置: {args.save_as}")
            return

        ser_cfg = cfg["serial"]
        rec_cfg = cfg.get("record", {})

        recorder = None
        record_path = args.record
        if not record_path and rec_cfg.get("enabled"):
            from pathlib import Path
            rec_dir = Path(os.path.expanduser(rec_cfg.get("directory", "~/ttypal-logs"))) / name
            rec_dir.mkdir(parents=True, exist_ok=True)
            from datetime import datetime
            record_path = str(rec_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.rec")

        if record_path:
            from ttypal.recorder import Recorder
            ring_size = rec_cfg.get("ring_size", 100000)
            recorder = Recorder(output_path=record_path, ring_size=ring_size)
        else:
            recorder = None

        conn = SerialConnection(
            port=ser_cfg["port"],
            baudrate=ser_cfg["baudrate"],
            bytesize=ser_cfg.get("bytesize", 8),
            parity=ser_cfg.get("parity", "none"),
            stopbits=ser_cfg.get("stopbits", 1),
            rtscts=ser_cfg.get("rtscts", False),
            dtr=ser_cfg.get("dtr", False),
            rts=ser_cfg.get("rts", False),
            recorder=recorder,
        )

    # Use session name for runtime identity if specified
    session_name = args.session or name

    log_cfg = cfg.get("log", {})
    sock_cfg = cfg.get("socket", {})

    logger = Logger(
        board_name=session_name,
        directory=log_cfg.get("directory", "~/ttypal-logs"),
        rotate_size_kb=log_cfg.get("rotate_size_kb", 10240),
        timestamp_format=log_cfg.get("timestamp_format", "%y%m%d %H:%M:%S.%f"),
    )

    sock_path = f"/tmp/ttypal-{session_name}.sock"
    prompt = sock_cfg.get("prompt", "# ")

    socket_srv = SocketServer(conn, logger, sock_path, prompt)

    # Write session metadata so client tools can find this instance
    if not args.replay:
        from ttypal.session import save_session, remove_session
        from datetime import datetime
        ser_cfg = cfg["serial"]
        save_session(session_name, {
            "profile": name,
            "port": ser_cfg["port"],
            "baudrate": ser_cfg["baudrate"],
            "socket": sock_path,
            "pid": os.getpid(),
            "started": datetime.now().isoformat(),
        })

    from ttypal.macro import Macro
    macro = Macro.from_config(cfg)
    terminal = Terminal(conn, logger, socket_srv, macro)

    try:
        terminal.start()
    except Exception as e:
        print(f"\r\n  错误: {e}")
        sys.exit(1)
    finally:
        if not args.replay:
            remove_session(session_name, pid=os.getpid())


if __name__ == "__main__":
    main()
