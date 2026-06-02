import os
import sys
import tty
import termios
import threading
import signal

from .macro import Macro, FKEY_ESCAPE_MAP


class Terminal:
    ESCAPE_KEY = 0x14  # Ctrl-T

    def __init__(self, serial_conn, logger, socket_server=None, macro=None):
        self.conn = serial_conn
        self.logger = logger
        self.socket_server = socket_server
        self.macro = macro or Macro()
        self._running = False
        self._old_termios = None
        self._line_buf = ""

    def start(self):
        self._running = True
        self.conn.open()

        if self.socket_server:
            self.socket_server.start()

        reader_thread = threading.Thread(target=self._reader, daemon=True)
        reader_thread.start()

        port = self.conn.port
        baud = self.conn.baudrate
        log = self.logger.current_log
        print(f"\r\n  ttypal 已连接: {port} @ {baud}")
        print(f"  日志: {log}")
        print(f"  Ctrl-T q 退出 | Ctrl-T h 帮助\r\n")

        try:
            self._writer()
        except KeyboardInterrupt:
            pass
        finally:
            self._cleanup()

    def _reader(self):
        while self._running:
            try:
                data = self.conn.read()
                if data:
                    os.write(sys.stdout.fileno(), data)
                    self.logger.write(data)
            except Exception:
                if self._running:
                    sys.stdout.write("\r\n  [连接断开，尝试重连...]\r\n")
                    sys.stdout.flush()
                    if self.conn.reconnect():
                        sys.stdout.write("  [已重连]\r\n")
                        sys.stdout.flush()
                    else:
                        sys.stdout.write("  [重连失败]\r\n")
                        sys.stdout.flush()
                        self._running = False

    def _writer(self):
        fd = sys.stdin.fileno()
        self._old_termios = termios.tcgetattr(fd)
        tty.setraw(fd)
        escape_pending = False
        esc_buf = ""

        try:
            while self._running:
                ch = os.read(fd, 1)
                if not ch:
                    continue

                b = ch[0]

                # Accumulate escape sequences for F keys
                if esc_buf:
                    esc_buf += chr(b)
                    matched_key = FKEY_ESCAPE_MAP.get(esc_buf)
                    if matched_key:
                        esc_buf = ""
                        if self.macro.has_binding(matched_key):
                            self.macro.play(matched_key, self.conn)
                        continue
                    # Check if still a valid prefix
                    is_prefix = any(s.startswith(esc_buf) for s in FKEY_ESCAPE_MAP)
                    if not is_prefix:
                        # Not a known sequence — send buffered bytes through
                        for c in esc_buf:
                            self.conn.write(bytes([ord(c)]))
                        esc_buf = ""
                    continue

                if escape_pending:
                    escape_pending = False
                    if b == ord("q"):
                        self._running = False
                        break
                    elif b == ord("h"):
                        self._show_help()
                    elif b == ord("r"):
                        self._start_macro_record()
                    elif b == ord("s"):
                        self._stop_macro_record()
                    elif b == self.ESCAPE_KEY:
                        self.conn.write(ch)
                    else:
                        self.conn.write(bytes([self.ESCAPE_KEY, b]))
                    continue

                if b == self.ESCAPE_KEY:
                    escape_pending = True
                    continue

                if b == 0x1b:
                    esc_buf = "\x1b"
                    continue

                # Track line buffer for macro recording
                if self.macro.recording:
                    if b == 0x0d:  # Enter
                        self.macro.record_cmd(self._line_buf)
                        self._line_buf = ""
                    elif b == 0x7f or b == 0x08:  # Backspace
                        self._line_buf = self._line_buf[:-1]
                    elif 0x20 <= b < 0x7f:
                        self._line_buf += chr(b)

                self.conn.write(ch)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, self._old_termios)

    def _show_help(self):
        macro_lines = ""
        for key in sorted(self.macro.bindings.keys(), key=lambda k: int(k[1:])):
            cmds = self.macro.bindings[key]
            preview = "; ".join(cmds[:3])
            if len(cmds) > 3:
                preview += "..."
            macro_lines += f"  │ {key:<4} {preview[:18]:<18} │\r\n"

        help_text = (
            "\r\n"
            "  ┌─── ttypal 快捷键 ───┐\r\n"
            "  │ Ctrl-T q  退出       │\r\n"
            "  │ Ctrl-T r  录制宏     │\r\n"
            "  │ Ctrl-T s  停止录制   │\r\n"
            "  │ Ctrl-T h  此帮助     │\r\n"
            "  │ Ctrl-T Ctrl-T 发送   │\r\n"
            "  │ F1-F12    播放宏     │\r\n"
            "  └──────────────────────┘\r\n"
        )
        if macro_lines:
            help_text += "  宏绑定:\r\n" + macro_lines
        sys.stdout.write(help_text)
        sys.stdout.flush()

    def _start_macro_record(self):
        self.macro.start_record()
        self._line_buf = ""
        sys.stdout.write("\r\n  [宏录制开始，Ctrl-T s 停止]\r\n")
        sys.stdout.flush()

    def _stop_macro_record(self):
        if not self.macro.recording:
            sys.stdout.write("\r\n  [未在录制]\r\n")
            sys.stdout.flush()
            return
        cmds = self.macro.stop_record()
        if not cmds:
            sys.stdout.write("\r\n  [录制为空，已取消]\r\n")
            sys.stdout.flush()
            return
        sys.stdout.write(f"\r\n  已录制 {len(cmds)} 条命令: {'; '.join(cmds[:5])}\r\n")
        sys.stdout.write("  保存到哪个键? (1-12, 直接回车取消): ")
        sys.stdout.flush()
        # Temporarily restore terminal to read input
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._old_termios)
        try:
            choice = input().strip()
        except (EOFError, KeyboardInterrupt):
            choice = ""
        finally:
            tty.setraw(sys.stdin.fileno())
        if choice and choice.isdigit() and 1 <= int(choice) <= 12:
            key_name = f"F{choice}"
            self.macro.save_binding(key_name, cmds)
            self._save_macro_to_config(key_name, cmds)
            sys.stdout.write(f"\r\n  [已保存到 {key_name}]\r\n")
        else:
            sys.stdout.write("\r\n  [已取消]\r\n")
        sys.stdout.flush()

    def _save_macro_to_config(self, key_name, cmds):
        try:
            from .config import load_board, save_board
            board_name = self.logger.board_name
            cfg = load_board(board_name)
            if cfg:
                if "macro" not in cfg:
                    cfg["macro"] = {}
                cfg["macro"][key_name] = cmds
                save_board(board_name, cfg)
        except Exception:
            pass

    def _cleanup(self):
        self._running = False
        if self.socket_server:
            self.socket_server.stop()
        self.conn.close()
        self.logger.close()
        sys.stdout.write("\r\n  ttypal 已断开\r\n")
        sys.stdout.flush()
