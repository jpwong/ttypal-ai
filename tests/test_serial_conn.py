import os
import threading
import time

import pytest

from ttypal.serial_conn import SerialConnection


class FakeSerial:
    """Minimal pyserial stand-in; a blocking read can simulate a quiet port."""

    is_open = True

    def __init__(self, data=b"", read_delay=0.5):
        self._buffer = bytearray(data)
        self.read_delay = read_delay
        self.read_calls = []
        self.written = b""
        self.polled = threading.Event()

    @property
    def in_waiting(self):
        self.polled.set()
        return len(self._buffer)

    def read(self, count):
        self.read_calls.append(count)
        if not self._buffer:
            time.sleep(self.read_delay)
            return b""
        data = bytes(self._buffer[:count])
        del self._buffer[:count]
        return data

    def write(self, data):
        self.written += data
        return len(data)


def _fake_conn(fake):
    conn = SerialConnection("/dev/ttypal-fake-test")
    conn._serial = fake
    return conn


def test_lock_file_readonly_still_acquires_flock():
    lock_file = "/tmp/ttypal-ttypal-readonly-test.lock"
    with open(lock_file, "w", encoding="utf-8") as f:
        f.write("other")
    os.chmod(lock_file, 0o444)

    conn = SerialConnection("/dev/ttypal-readonly-test")
    try:
        conn._acquire_lock()
        assert conn._lock_fd is not None
    finally:
        conn._release_lock()
        os.chmod(lock_file, 0o666)
        os.unlink(lock_file)


def test_lock_file_contention_raises_runtime_error():
    lock_file = "/tmp/ttypal-ttypal-contention-test.lock"
    first = SerialConnection("/dev/ttypal-contention-test")
    second = SerialConnection("/dev/ttypal-contention-test")

    try:
        first._acquire_lock()
        with pytest.raises(RuntimeError, match="已被其他 ttypal 实例占用"):
            second._acquire_lock()
    finally:
        second._release_lock()
        first._release_lock()
        try:
            os.unlink(lock_file)
        except FileNotFoundError:
            pass


def test_read_returns_available_data():
    fake = FakeSerial(data=b"hello")
    conn = _fake_conn(fake)

    assert conn.read() == b"hello"
    assert fake.read_calls == [5]


def test_read_honours_size_limit():
    fake = FakeSerial(data=b"abcdef")
    conn = _fake_conn(fake)

    assert conn.read(2) == b"ab"
    assert conn.read() == b"cdef"


def test_read_zero_returns_all_available():
    fake = FakeSerial(data=b"abcdef")
    conn = _fake_conn(fake)

    assert conn.read(0) == b"abcdef"


def test_read_records_rx_data():
    class FakeRecorder:
        def __init__(self):
            self.rx = b""

        def record_rx(self, data):
            self.rx += data

    recorder = FakeRecorder()
    conn = _fake_conn(FakeSerial(data=b"ok"))
    conn._recorder = recorder

    conn.read()
    assert recorder.rx == b"ok"


def test_idle_read_does_not_starve_writes():
    """A quiet port must not hold the serial lock while waiting for data."""
    fake = FakeSerial(read_delay=1.0)
    conn = _fake_conn(fake)

    stop = threading.Event()

    def reader():
        while not stop.is_set():
            conn.read()

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    try:
        assert fake.polled.wait(timeout=2), "reader never polled the port"
        started = time.monotonic()
        conn.write(b"ping")
        elapsed = time.monotonic() - started
    finally:
        stop.set()
        thread.join(timeout=2)

    assert fake.written == b"ping"
    assert fake.read_calls == [], "idle read must not block under the lock"
    assert elapsed < 0.5
