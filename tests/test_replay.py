import json
import time
from pathlib import Path

from ttypal.recorder import Recorder
from ttypal.replay_backend import ReplayBackend


def _create_recording(tmp_path, events):
    rec_file = tmp_path / "session.rec"
    with open(rec_file, "w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")
    return str(rec_file)


def test_replay_read(tmp_path):
    rec_path = _create_recording(tmp_path, [
        {"t": 0.0, "dir": "rx", "hex": b"hello\r\n".hex()},
        {"t": 0.1, "dir": "rx", "hex": b"world\r\n".hex()},
    ])

    backend = ReplayBackend(rec_path, realtime=False)
    backend.open()
    time.sleep(0.1)

    data = backend.read()
    assert b"hello" in data or b"world" in data
    backend.close()


def test_replay_write_logs_tx(tmp_path):
    rec_path = _create_recording(tmp_path, [
        {"t": 0.0, "dir": "rx", "hex": b"# ".hex()},
    ])

    backend = ReplayBackend(rec_path, realtime=False)
    backend.open()
    backend.write("ls\r\n")
    backend.write(b"pwd\r\n")
    assert backend.sent_data == b"ls\r\npwd\r\n"
    backend.close()


def test_replay_is_open(tmp_path):
    # Use multiple events with realtime delay to keep replay alive
    rec_path = _create_recording(tmp_path, [
        {"t": 0.0, "dir": "rx", "hex": b"x".hex()},
        {"t": 0.5, "dir": "rx", "hex": b"y".hex()},
    ])

    backend = ReplayBackend(rec_path, realtime=True)
    assert not backend.is_open
    backend.open()
    time.sleep(0.05)
    assert backend.is_open
    backend.close()
