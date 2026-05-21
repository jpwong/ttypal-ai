import os
import sys
import tty
import termios
import threading
import signal


class Terminal:
    ESCAPE_KEY = 0x14  # Ctrl-T

    def __init__(self, serial_conn, logger, socket_server=None):
        self.conn = serial_conn
        self.logger = logger
        self.socket_server = socket_server
        self._running = False
        self._old_termios = None

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

        try:
            while self._running:
                ch = os.read(fd, 1)
                if not ch:
                    continue

                b = ch[0]

                if escape_pending:
                    escape_pending = False
                    if b == ord("q"):
                        self._running = False
                        break
                    elif b == ord("h"):
                        self._show_help()
                    elif b == self.ESCAPE_KEY:
                        self.conn.write(ch)
                    else:
                        self.conn.write(bytes([self.ESCAPE_KEY, b]))
                    continue

                if b == self.ESCAPE_KEY:
                    escape_pending = True
                    continue

                self.conn.write(ch)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, self._old_termios)

    def _show_help(self):
        help_text = (
            "\r\n"
            "  ┌─── ttypal 快捷键 ───┐\r\n"
            "  │ Ctrl-T q  退出       │\r\n"
            "  │ Ctrl-T h  此帮助     │\r\n"
            "  │ Ctrl-T Ctrl-T 发送   │\r\n"
            "  └──────────────────────┘\r\n"
        )
        sys.stdout.write(help_text)
        sys.stdout.flush()

    def _cleanup(self):
        self._running = False
        if self.socket_server:
            self.socket_server.stop()
        self.conn.close()
        self.logger.close()
        sys.stdout.write("\r\n  ttypal 已断开\r\n")
        sys.stdout.flush()
