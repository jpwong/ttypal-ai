import json
import time
import threading
from collections import deque
from pathlib import Path


class Recorder:
    def __init__(self, output_path=None, ring_size=0):
        """
        output_path: 录制文件路径，None 则只用内存环形 buffer
        ring_size: 环形 buffer 最大事件数，0 表示不限制（全部写入文件）
        """
        self.output_path = Path(output_path) if output_path else None
        self.ring_size = ring_size
        self._ring = deque(maxlen=ring_size if ring_size > 0 else None)
        self._file = None
        self._start_time = None
        self._lock = threading.Lock()

        if self.output_path:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            self._file = open(self.output_path, "a", encoding="utf-8")

    def _elapsed(self):
        if self._start_time is None:
            self._start_time = time.monotonic()
        return time.monotonic() - self._start_time

    def record(self, direction, data):
        """
        direction: "rx" (received from device) or "tx" (sent to device)
        data: bytes
        """
        if not data:
            return
        event = {
            "t": round(self._elapsed(), 4),
            "dir": direction,
            "hex": data.hex(),
        }
        with self._lock:
            self._ring.append(event)
            if self._file:
                self._file.write(json.dumps(event) + "\n")
                self._file.flush()

    def record_rx(self, data):
        self.record("rx", data)

    def record_tx(self, data):
        if isinstance(data, str):
            data = data.encode()
        self.record("tx", data)

    def get_ring(self):
        with self._lock:
            return list(self._ring)

    def close(self):
        if self._file:
            self._file.close()
            self._file = None

    @staticmethod
    def load(path):
        events = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
        return events
