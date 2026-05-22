import serial
import threading
import time
import fcntl
import os


class SerialConnection:
    def __init__(self, port, baudrate=115200, bytesize=8, parity="none",
                 stopbits=1, rtscts=False, dtr=False, rts=False, recorder=None):
        self.port = port
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = self._parse_parity(parity)
        self.stopbits = stopbits
        self.rtscts = rtscts
        self.dtr = dtr
        self.rts = rts
        self._serial = None
        self._lock = threading.Lock()
        self._recorder = recorder
        self._lock_fd = None
        self._paused = threading.Event()

    @staticmethod
    def _parse_parity(p):
        return {"none": serial.PARITY_NONE, "even": serial.PARITY_EVEN,
                "odd": serial.PARITY_ODD, "mark": serial.PARITY_MARK,
                "space": serial.PARITY_SPACE}.get(p, serial.PARITY_NONE)

    def _acquire_lock(self):
        lock_path = f"/tmp/ttypal-{os.path.basename(self.port)}.lock"
        self._lock_fd = open(lock_path, "w")
        try:
            fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._lock_fd.write(str(os.getpid()))
            self._lock_fd.flush()
        except OSError:
            self._lock_fd.close()
            self._lock_fd = None
            raise RuntimeError(f"串口 {self.port} 已被其他 ttypal 实例占用")

    def _release_lock(self):
        if self._lock_fd:
            fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            self._lock_fd.close()
            self._lock_fd = None

    def open(self):
        self._acquire_lock()
        self._serial = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=self.bytesize,
            parity=self.parity,
            stopbits=self.stopbits,
            rtscts=self.rtscts,
            dsrdtr=False,
            timeout=0.1,
        )
        self._serial.dtr = self.dtr
        self._serial.rts = self.rts

    def close(self):
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._release_lock()

    def pause(self):
        self._paused.set()

    def resume(self):
        self._paused.clear()

    def read(self, size=None):
        if not self._serial:
            return b""
        if self._paused.is_set():
            time.sleep(0.05)
            return b""
        with self._lock:
            waiting = self._serial.in_waiting
            if waiting:
                data = self._serial.read(size or waiting)
            else:
                data = self._serial.read(1)
        if data and self._recorder:
            self._recorder.record_rx(data)
        return data

    def write(self, data):
        if isinstance(data, str):
            data = data.encode()
        with self._lock:
            self._serial.write(data)
        if self._recorder:
            self._recorder.record_tx(data)

    def reconnect(self, retries=5, delay=2):
        for i in range(retries):
            try:
                self.close()
                time.sleep(delay)
                self.open()
                return True
            except serial.SerialException:
                if i < retries - 1:
                    time.sleep(delay)
        return False

    @property
    def is_open(self):
        return self._serial is not None and self._serial.is_open
