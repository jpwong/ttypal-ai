import time
import threading
from ttypal.recorder import Recorder


class ReplayBackend:
    """
    替代 SerialConnection 的回放后端，从录制文件回放数据。
    实现与 SerialConnection 相同的 read/write/open/close 接口。
    """

    def __init__(self, recording_path, realtime=False):
        """
        recording_path: .rec 文件路径
        realtime: True 则按原始时序回放，False 则尽快返回数据
        """
        self.events = Recorder.load(recording_path)
        self.realtime = realtime
        self._rx_buffer = bytearray()
        self._tx_log = []
        self._lock = threading.Lock()
        self._index = 0
        self._start_time = None
        self._running = False
        self._thread = None
        self.port = f"replay:{recording_path}"
        self.baudrate = 0

    def open(self):
        self._running = True
        self._start_time = time.monotonic()
        self._thread = threading.Thread(target=self._replay_loop, daemon=True)
        self._thread.start()

    def close(self):
        self._running = False

    def read(self, size=None):
        with self._lock:
            if not self._rx_buffer:
                time.sleep(0.01)
                return b""
            if size:
                data = bytes(self._rx_buffer[:size])
                del self._rx_buffer[:size]
            else:
                data = bytes(self._rx_buffer)
                self._rx_buffer.clear()
            return data

    def write(self, data):
        if isinstance(data, str):
            data = data.encode()
        self._tx_log.append(data)

    def reconnect(self, retries=5, delay=2):
        return True

    @property
    def is_open(self):
        return self._running

    def _replay_loop(self):
        for event in self.events:
            if not self._running:
                break
            if self.realtime and self._start_time:
                target = self._start_time + event["t"]
                now = time.monotonic()
                if target > now:
                    time.sleep(target - now)

            if event["dir"] == "rx":
                data = bytes.fromhex(event["hex"])
                with self._lock:
                    self._rx_buffer.extend(data)
        self._running = False

    @property
    def sent_data(self):
        return b"".join(self._tx_log)
