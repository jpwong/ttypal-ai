"""Make serial output safe to print on a terminal.

The serial link is a byte-exact pipe, so a noisy link or binary junk from the
board can contain C0 control bytes that change terminal state.  A lone SO
(0x0E, LS1) is especially damaging: it shifts the terminal into DEC Special
Graphics and everything printed afterwards is rendered as line-drawing glyphs
until an SI (0x0F) arrives.

These helpers are only for display paths; callers decide what to log or record.
The default policy keeps bytes that console output legitimately needs (BEL, BS,
TAB, LF, CR and ESC for ANSI sequences) and renders other C0 bytes plus DEL in
caret notation.  Bytes >= 0x80 are left untouched so valid UTF-8 stays intact.
ESC sequences themselves are passed through, including DEC charset designations;
use ``--raw`` for full TUI fidelity and avoid feeding untrusted binary output to
a terminal.
"""

import re


# All C0 controls except BEL, BS, TAB, LF, CR and ESC, plus DEL.
_UNSAFE_CONTROLS = r"\x00-\x06\x0b\x0c\x0e-\x1a\x1c-\x1f\x7f"
_BYTE_CONTROL_RE = re.compile(b"[" + _UNSAFE_CONTROLS.encode("ascii") + b"]")
_TEXT_CONTROL_RE = re.compile("[" + _UNSAFE_CONTROLS + "]")


def _caret(byte):
    if byte == 0x7F:
        return "^?"
    return "^" + chr(byte ^ 0x40)


def sanitize_bytes(data):
    """Return bytes safe to write to a terminal, or ``data`` unchanged."""
    if not data:
        return data

    def replace(match):
        return _caret(match.group()[0]).encode("ascii")

    return _BYTE_CONTROL_RE.sub(replace, data)


def sanitize_text(text):
    """Return text safe to write to a terminal, or ``text`` unchanged."""
    if not text:
        return text
    return _TEXT_CONTROL_RE.sub(lambda match: _caret(ord(match.group())), text)
