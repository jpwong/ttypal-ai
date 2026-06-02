import time
import threading


FKEY_ESCAPE_MAP = {
    "\x1bOP": "F1", "\x1b[11~": "F1",
    "\x1bOQ": "F2", "\x1b[12~": "F2",
    "\x1bOR": "F3", "\x1b[13~": "F3",
    "\x1bOS": "F4", "\x1b[14~": "F4",
    "\x1b[15~": "F5",
    "\x1b[17~": "F6",
    "\x1b[18~": "F7",
    "\x1b[19~": "F8",
    "\x1b[20~": "F9",
    "\x1b[21~": "F10",
    "\x1b[23~": "F11",
    "\x1b[24~": "F12",
}

FKEY_NAMES = [f"F{i}" for i in range(1, 13)]

DEFAULT_DELAY = 0.2


class Macro:
    def __init__(self, bindings=None):
        self.bindings = bindings or {}
        self._recording = False
        self._recorded_cmds = []

    @classmethod
    def from_config(cls, cfg):
        macro_cfg = cfg.get("macro", {})
        bindings = {}
        for key in FKEY_NAMES:
            if key in macro_cfg:
                bindings[key] = macro_cfg[key]
        return cls(bindings)

    def has_binding(self, key_name):
        return key_name in self.bindings

    def play(self, key_name, serial_conn):
        commands = self.bindings.get(key_name)
        if not commands:
            return False

        def _run():
            for cmd in commands:
                if cmd.startswith("sleep "):
                    try:
                        delay = float(cmd[6:])
                        time.sleep(delay)
                    except ValueError:
                        pass
                    continue
                serial_conn.write(cmd + "\r\n")
                time.sleep(DEFAULT_DELAY)

        threading.Thread(target=_run, daemon=True).start()
        return True

    @property
    def recording(self):
        return self._recording

    def start_record(self):
        self._recording = True
        self._recorded_cmds = []

    def record_cmd(self, cmd):
        if self._recording and cmd.strip():
            self._recorded_cmds.append(cmd.strip())

    def stop_record(self):
        self._recording = False
        cmds = list(self._recorded_cmds)
        self._recorded_cmds = []
        return cmds

    def save_binding(self, key_name, commands):
        self.bindings[key_name] = commands
