import json
import tempfile
from pathlib import Path

from ttypal.recorder import Recorder


def test_record_and_load(tmp_path):
    rec_file = tmp_path / "test.rec"
    recorder = Recorder(output_path=str(rec_file))

    recorder.record_rx(b"hello")
    recorder.record_tx(b"world")
    recorder.close()

    events = Recorder.load(str(rec_file))
    assert len(events) == 2
    assert events[0]["dir"] == "rx"
    assert events[0]["hex"] == b"hello".hex()
    assert events[1]["dir"] == "tx"
    assert events[1]["hex"] == b"world".hex()
    assert events[1]["t"] >= events[0]["t"]


def test_ring_buffer(tmp_path):
    recorder = Recorder(ring_size=5)
    for i in range(10):
        recorder.record_rx(bytes([i]))
    ring = recorder.get_ring()
    assert len(ring) == 5
    assert ring[0]["hex"] == bytes([5]).hex()
    assert ring[-1]["hex"] == bytes([9]).hex()


def test_empty_data_ignored(tmp_path):
    rec_file = tmp_path / "test.rec"
    recorder = Recorder(output_path=str(rec_file))
    recorder.record_rx(b"")
    recorder.record_tx(b"")
    recorder.close()

    events = Recorder.load(str(rec_file))
    assert len(events) == 0


def test_record_tx_string(tmp_path):
    rec_file = tmp_path / "test.rec"
    recorder = Recorder(output_path=str(rec_file))
    recorder.record_tx("ls\r\n")
    recorder.close()

    events = Recorder.load(str(rec_file))
    assert events[0]["hex"] == b"ls\r\n".hex()
