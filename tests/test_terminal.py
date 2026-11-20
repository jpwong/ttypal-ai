import ttypal.terminal as terminal_mod
from ttypal.terminal import Terminal


class _FakeStdout:
    def fileno(self):
        return 1

    def write(self, text):
        pass

    def flush(self):
        pass


class _FakeConn:
    def __init__(self, data):
        self.data = data

    def read(self):
        return self.data


class _LoggingStopper:
    def __init__(self, terminal):
        self.terminal = terminal
        self.data = []

    def write(self, data):
        self.data.append(data)
        self.terminal._running = False


def _run_reader(monkeypatch, payload, raw=False):
    conn = _FakeConn(payload)
    terminal = Terminal(conn, logger=None, raw=raw)
    logger = _LoggingStopper(terminal)
    terminal.logger = logger

    writes = []
    monkeypatch.setattr(
        terminal_mod.os, "write", lambda fd, data: writes.append(data) or len(data)
    )
    monkeypatch.setattr(terminal_mod.sys, "stdout", _FakeStdout())

    terminal._running = True
    terminal._reader()

    return writes, logger.data


def test_reader_sanitizes_terminal_but_logs_raw_bytes(monkeypatch):
    writes, logged = _run_reader(monkeypatch, b"Status\x0eUnstaged")

    assert writes == [b"Status^NUnstaged"]
    assert logged == [b"Status\x0eUnstaged"]


def test_reader_raw_mode_forwards_bytes_verbatim(monkeypatch):
    payload = b"Status\x0eUnstaged"
    writes, logged = _run_reader(monkeypatch, payload, raw=True)

    assert writes == [payload]
    assert logged == [payload]


def test_writer_exits_when_stdin_reaches_eof(monkeypatch):
    """A closed stdin must end the session instead of spinning and holding the port."""
    import os
    import threading

    read_fd, write_fd = os.pipe()
    os.close(write_fd)

    class _FakeStdin:
        def fileno(self):
            return read_fd

    monkeypatch.setattr(terminal_mod.sys, "stdin", _FakeStdin())
    monkeypatch.setattr(terminal_mod.termios, "tcgetattr", lambda fd: [])
    monkeypatch.setattr(terminal_mod.termios, "tcsetattr", lambda fd, when, attrs: None)
    monkeypatch.setattr(terminal_mod.tty, "setraw", lambda fd: None)

    terminal = Terminal(_FakeConn(b""), logger=None)
    terminal._running = True

    thread = threading.Thread(target=terminal._writer, daemon=True)
    try:
        thread.start()
        thread.join(2.0)
        assert not thread.is_alive()
    finally:
        os.close(read_fd)

