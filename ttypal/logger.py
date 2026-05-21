import os
import time
from datetime import datetime
from pathlib import Path


class Logger:
    def __init__(self, board_name, directory="~/ttypal-logs",
                 rotate_size_kb=10240, timestamp_format="%H:%M:%S.%f"):
        self.board_name = board_name
        self.base_dir = Path(os.path.expanduser(directory)) / board_name
        self.rotate_size = rotate_size_kb * 1024
        self.ts_format = timestamp_format
        self._file = None
        self._file_path = None
        self._line_start = True
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._open_new()

    def _open_new(self):
        if self._file:
            self._file.close()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        self._file_path = self.base_dir / f"{ts}.log"
        self._file = open(self._file_path, "a", encoding="utf-8", errors="replace")

    def write(self, data):
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="replace")
        if not data:
            return

        out = []
        for ch in data:
            if self._line_start:
                ts = datetime.now().strftime(self.ts_format)
                # 截断微秒到毫秒
                if ".%f" in self.ts_format:
                    ts = ts[:-3]
                out.append(f"[{ts}] ")
                self._line_start = False
            out.append(ch)
            if ch == "\n":
                self._line_start = True

        text = "".join(out)
        self._file.write(text)
        self._file.flush()

        if self._file_path.stat().st_size > self.rotate_size:
            self._open_new()

    @property
    def current_log(self):
        return self._file_path

    @property
    def log_dir(self):
        return self.base_dir

    def close(self):
        if self._file:
            self._file.close()
