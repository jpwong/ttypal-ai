import time
import threading
from unittest.mock import MagicMock

from ttypal.macro import Macro, FKEY_ESCAPE_MAP, FKEY_NAMES


def test_from_config_empty():
    macro = Macro.from_config({})
    assert macro.bindings == {}


def test_from_config_with_bindings():
    cfg = {"macro": {"F1": ["ls", "pwd"], "F3": ["reboot"]}}
    macro = Macro.from_config(cfg)
    assert macro.has_binding("F1")
    assert macro.has_binding("F3")
    assert not macro.has_binding("F2")


def test_play_sends_commands():
    conn = MagicMock()
    macro = Macro(bindings={"F1": ["cmd1", "cmd2"]})
    result = macro.play("F1", conn)
    assert result is True
    time.sleep(0.6)
    calls = conn.write.call_args_list
    assert len(calls) == 2
    assert calls[0][0][0] == "cmd1\r\n"
    assert calls[1][0][0] == "cmd2\r\n"


def test_play_sleep_command():
    conn = MagicMock()
    macro = Macro(bindings={"F2": ["cmd1", "sleep 0.3", "cmd2"]})
    start = time.monotonic()
    macro.play("F2", conn)
    time.sleep(1.0)
    elapsed = time.monotonic() - start
    calls = conn.write.call_args_list
    assert len(calls) == 2
    assert calls[0][0][0] == "cmd1\r\n"
    assert calls[1][0][0] == "cmd2\r\n"


def test_play_unbound_key():
    conn = MagicMock()
    macro = Macro(bindings={})
    assert macro.play("F5", conn) is False


def test_record_and_stop():
    macro = Macro()
    macro.start_record()
    assert macro.recording is True
    macro.record_cmd("ls")
    macro.record_cmd("pwd")
    macro.record_cmd("")
    cmds = macro.stop_record()
    assert cmds == ["ls", "pwd"]
    assert macro.recording is False


def test_save_binding():
    macro = Macro()
    macro.save_binding("F7", ["hello", "world"])
    assert macro.has_binding("F7")
    assert macro.bindings["F7"] == ["hello", "world"]


def test_fkey_escape_map_covers_all_keys():
    mapped_keys = set(FKEY_ESCAPE_MAP.values())
    for name in FKEY_NAMES:
        assert name in mapped_keys
