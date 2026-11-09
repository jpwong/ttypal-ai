from types import SimpleNamespace

from ttypal.main import _resolve_raw_output


def _args(raw):
    return SimpleNamespace(raw=raw)


def test_raw_defaults_off_for_old_config():
    assert _resolve_raw_output(_args(None), {}) is False


def test_raw_reads_terminal_config():
    assert _resolve_raw_output(_args(None), {"terminal": {"raw": True}}) is True


def test_cli_raw_overrides_false_config():
    assert _resolve_raw_output(_args(True), {"terminal": {"raw": False}}) is True


def test_cli_no_raw_overrides_true_config():
    assert _resolve_raw_output(_args(False), {"terminal": {"raw": True}}) is False


def test_raw_ignores_invalid_terminal_section():
    assert _resolve_raw_output(_args(None), {"terminal": "invalid"}) is False
