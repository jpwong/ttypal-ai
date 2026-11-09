import pytest

from ttypal.sanitize import sanitize_bytes, sanitize_text


UNSAFE_CONTROLS = [
    byte for byte in range(0x20) if byte not in (0x07, 0x08, 0x09, 0x0A, 0x0D, 0x1B)
] + [0x7F]


def test_sanitize_bytes_escapes_so_and_si():
    assert sanitize_bytes(b"Status\x0eUnstaged\x0f ok") == b"Status^NUnstaged^O ok"


@pytest.mark.parametrize("byte", UNSAFE_CONTROLS)
def test_sanitize_bytes_escapes_every_unsafe_control(byte):
    expected = "^?" if byte == 0x7F else "^" + chr(byte ^ 0x40)
    assert sanitize_bytes(bytes([byte])) == expected.encode("ascii")


@pytest.mark.parametrize("text", ["你", "状态✓", "a你b好c"])
def test_sanitize_bytes_preserves_utf8_across_chunk_splits(text):
    data = text.encode("utf-8")
    for split in range(len(data) + 1):
        assert sanitize_bytes(data[:split]) + sanitize_bytes(data[split:]) == data


def test_sanitize_bytes_keeps_safe_console_controls():
    data = b"\x07\x08\t\n\r\x1b[31mred\x1b[0m"
    assert sanitize_bytes(data) == data


def test_sanitize_bytes_keeps_utf8():
    data = "状态: 正常 ✓\r\n".encode("utf-8")
    assert sanitize_bytes(data) == data


def test_sanitize_bytes_escapes_other_c0_and_del():
    assert sanitize_bytes(b"\x00\x01\x0c\x18\x1c\x1d\x7f") == b"^@^A^L^X^\\^]^?"


def test_sanitize_bytes_empty():
    assert sanitize_bytes(b"") == b""


def test_sanitize_text_escapes_so_and_si():
    assert sanitize_text("Status\x0eUnstaged\x0f") == "Status^NUnstaged^O"


def test_sanitize_text_keeps_ansi_and_unicode():
    text = "\x1b[32m状态\x1b[0m\n"
    assert sanitize_text(text) == text


def test_sanitize_text_escapes_other_c0_and_del():
    assert sanitize_text("\x00\x01\x0c\x18\x1c\x1d\x7f") == "^@^A^L^X^\\^]^?"
