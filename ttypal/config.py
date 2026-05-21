import os
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
import tomli_w


CONFIG_DIR = Path.home() / ".config" / "ttypal" / "boards"

DEFAULT_CONFIG = {
    "serial": {
        "port": "/dev/ttyUSB0",
        "baudrate": 115200,
        "bytesize": 8,
        "parity": "none",
        "stopbits": 1,
        "rtscts": False,
        "dtr": False,
        "rts": False,
    },
    "log": {
        "directory": str(Path.home() / "ttypal-logs"),
        "rotate_size_kb": 10240,
        "timestamp_format": "%y%m%d %H:%M:%S.%f",
    },
    "socket": {
        "path": "/tmp/ttypal-{name}.sock",
        "prompt": "# ",
    },
    "record": {
        "enabled": False,
        "directory": str(Path.home() / "ttypal-logs"),
        "ring_size": 100000,
    },
}

COMMON_BAUDRATES = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]


def list_boards():
    if not CONFIG_DIR.exists():
        return []
    return sorted(p.stem for p in CONFIG_DIR.glob("*.toml"))


def load_board(name):
    path = CONFIG_DIR / f"{name}.toml"
    if not path.exists():
        return None
    with open(path, "rb") as f:
        return tomllib.load(f)


def save_board(name, cfg):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_DIR / f"{name}.toml", "wb") as f:
        tomli_w.dump(cfg, f)


def delete_board(name):
    path = CONFIG_DIR / f"{name}.toml"
    if path.exists():
        path.unlink()


def _detect_ports():
    import serial.tools.list_ports
    return [p.device for p in serial.tools.list_ports.comports()]


def _ask(prompt, default=""):
    suffix = f" [{default}]" if default else ""
    val = input(f"{prompt}{suffix}: ").strip()
    return val if val else default


def _ask_choice(prompt, choices, default=0):
    for i, c in enumerate(choices):
        marker = "*" if i == default else " "
        print(f"  {marker} {i + 1}) {c}")
    raw = input(f"{prompt} [{default + 1}]: ").strip()
    if not raw:
        return choices[default]
    try:
        idx = int(raw) - 1
        if 0 <= idx < len(choices):
            return choices[idx]
    except ValueError:
        pass
    return choices[default]


def create_board_interactive():
    print("\n  新建板子配置")
    print("  " + "─" * 30)

    name = _ask("  配置名称", "myboard")

    ports = _detect_ports()
    if ports:
        print("\n  检测到串口:")
        port = _ask_choice("  选择串口", ports + ["手动输入..."])
        if port == "手动输入...":
            port = _ask("  串口路径", "/dev/ttyUSB0")
    else:
        print("\n  未检测到串口")
        port = _ask("  串口路径", "/dev/ttyUSB0")

    print("\n  波特率:")
    baud_strs = [str(b) for b in COMMON_BAUDRATES]
    for i, b in enumerate(baud_strs):
        marker = "*" if i == COMMON_BAUDRATES.index(115200) else " "
        print(f"  {marker} {i + 1}) {b}")
    print(f"    c) 自定义")
    raw = input(f"  选择波特率 [{COMMON_BAUDRATES.index(115200) + 1}]: ").strip()
    if raw.lower() == "c":
        baud_input = _ask("  输入波特率", "115200")
        baudrate = int(baud_input)
    elif not raw:
        baudrate = 115200
    else:
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(COMMON_BAUDRATES):
                baudrate = COMMON_BAUDRATES[idx]
            else:
                baudrate = int(raw)
        except ValueError:
            baudrate = 115200

    prompt = _ask("  Shell 提示符", "# ")

    cfg = {
        "serial": {
            **DEFAULT_CONFIG["serial"],
            "port": port,
            "baudrate": baudrate,
        },
        "log": {**DEFAULT_CONFIG["log"]},
        "socket": {
            "path": f"/tmp/ttypal-{name}.sock",
            "prompt": prompt,
        },
    }

    save_board(name, cfg)
    print(f"\n  已保存: {CONFIG_DIR / name}.toml")
    return name, cfg


def select_board():
    boards = list_boards()

    print("\n  ttypal - Serial Debug Tool")
    print("  " + "═" * 30)

    if boards:
        for i, name in enumerate(boards):
            cfg = load_board(name)
            port = cfg["serial"]["port"]
            baud = cfg["serial"]["baudrate"]
            print(f"  {i + 1}) {name:<14} {port}  {baud}")
        print()

    print(f"  n) 新建配置")
    print(f"  q) 退出")

    default = "1" if boards else "n"
    choice = input(f"\n  请选择 [{default}]: ").strip() or default

    if choice.lower() == "q":
        sys.exit(0)

    if choice.lower() == "n":
        return create_board_interactive()

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(boards):
            name = boards[idx]
            return name, load_board(name)
    except ValueError:
        pass

    print("  无效选择")
    return select_board()


def resolve_config(args):
    if args.board:
        cfg = load_board(args.board)
        if cfg is None:
            print(f"配置 '{args.board}' 不存在")
            sys.exit(1)
        name = args.board
    else:
        name, cfg = select_board()

    if args.port:
        cfg["serial"]["port"] = args.port
    if args.baudrate:
        cfg["serial"]["baudrate"] = args.baudrate

    return name, cfg
