import os

import pytest

from ttypal.serial_conn import SerialConnection


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
