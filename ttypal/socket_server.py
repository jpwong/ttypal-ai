import json
import os
import re
import socket
import threading
import time
from dataclasses import dataclass

from .logger import SESSION_MARKER_PREFIX
from .zmodem_transfer import ZmodemTransfer


ANSI_ESCAPE_RE = re.compile(
    r"\x1b(?:\[[0-9;:?]*[ -/]*[@-~]|\][^\x07\x1b]*?(?:\x07|\x1b\\))"
)
# Numeric logger timestamps with a time component, e.g.
# "[261109 17:50:30.374] " or "[17:50:30.374] ".
LOG_TIMESTAMP_RE = re.compile(r"^\[\d[\d /.,+-]*:\d[\d /:.,+-]*\] ")


@dataclass
class WaitResult:
    matched: bool
    output: str


class SocketServer:
    def __init__(self, serial_conn, logger, socket_path, default_prompt="# "):
        self.conn = serial_conn
        self.logger = logger
        self.socket_path = socket_path
        self.default_prompt = default_prompt
        self._server = None
        self._thread = None
        self._running = False

    def start(self):
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(self.socket_path)
        self._server.listen(5)
        self._server.settimeout(1)
        self._running = True
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._server:
            self._server.close()
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

    def _accept_loop(self):
        while self._running:
            try:
                client, _ = self._server.accept()
                threading.Thread(target=self._handle, args=(client,), daemon=True).start()
            except socket.timeout:
                continue
            except OSError:
                break

    def _handle(self, client):
        try:
            data = b""
            while True:
                chunk = client.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b"\n" in data:
                    break

            line = data.strip()
            if not line:
                return

            try:
                req = json.loads(line)
            except json.JSONDecodeError as e:
                client.sendall(json.dumps({
                    "status": "error",
                    "code": "bad_request",
                    "message": f"invalid JSON: {e}",
                }).encode() + b"\n")
                return
            if not isinstance(req, dict):
                client.sendall(json.dumps({
                    "status": "error",
                    "code": "bad_request",
                    "message": "request must be a JSON object",
                }).encode() + b"\n")
                return
            cmd = req.get("cmd", "send")

            try:
                if cmd == "send":
                    payload = req["data"]
                    if not payload.endswith("\n"):
                        payload += "\r\n"
                    self.conn.write(payload)
                    resp = {"status": "ok"}

                elif cmd == "send_wait":
                    payload = req["data"]
                    prompt = req.get("prompt", self.default_prompt)
                    timeout = req.get("timeout", 10)
                    if not payload.endswith("\n"):
                        payload += "\r\n"

                    mark = os.path.getsize(self.logger.current_log)
                    self.conn.write(payload)

                    result = self._wait_for_prompt_after_cmd(
                        payload.strip(), prompt, timeout, mark)
                    if result.matched:
                        resp = {"status": "ok", "output": result.output}
                    else:
                        resp = {
                            "status": "error",
                            "code": "wait_timeout",
                            "message": f"等待 prompt '{prompt}' 超时",
                            "output": result.output,
                        }

                elif cmd == "expect_send":
                    expect = req["expect"]
                    payload = req["data"]
                    timeout = req.get("timeout", 10)
                    if not payload.endswith("\n"):
                        payload += "\r\n"

                    ok = self._wait_for_string(expect, timeout)
                    if ok:
                        self.conn.write(payload)
                        resp = {"status": "ok"}
                    else:
                        resp = {
                            "status": "error",
                            "code": "wait_timeout",
                            "message": f"等待 '{expect}' 超时",
                        }

                elif cmd == "expect_send_wait":
                    expect = req["expect"]
                    payload = req["data"]
                    prompt = req.get("prompt", self.default_prompt)
                    timeout = req.get("timeout", 10)
                    if not payload.endswith("\n"):
                        payload += "\r\n"

                    ok = self._wait_for_string(expect, timeout)
                    if not ok:
                        resp = {
                            "status": "error",
                            "code": "wait_timeout",
                            "message": f"等待 '{expect}' 超时",
                        }
                    else:
                        mark = os.path.getsize(self.logger.current_log)
                        self.conn.write(payload)
                        result = self._wait_for_prompt_after_cmd(
                            payload.strip(), prompt, timeout, mark)
                        if result.matched:
                            resp = {"status": "ok", "output": result.output}
                        else:
                            resp = {
                                "status": "error",
                                "code": "wait_timeout",
                                "message": f"等待 prompt '{prompt}' 超时",
                                "output": result.output,
                            }

                elif cmd == "probe":
                    timeout = req.get("timeout", 2)
                    log_path = self.logger.current_log
                    mark = os.path.getsize(log_path)
                    self.conn.write(b"\r\n")
                    time.sleep(timeout)
                    with open(log_path, "rb") as f:
                        f.seek(mark)
                        new_data = f.read().decode("utf-8", errors="replace")
                    lines = []
                    for line in new_data.split("\n"):
                        if line.startswith("[") and "] " in line:
                            line = line[line.index("] ") + 2:]
                        if line.strip():
                            lines.append(line)
                    resp = {"status": "ok", "output": "\n".join(lines)}

                elif cmd == "xmodem_send" or cmd == "zmodem_send":
                    filepath = req["file"]
                    timeout = req.get("timeout", 120)

                    xfer = ZmodemTransfer(self.conn, self.logger)
                    resp = xfer.send_file(filepath, timeout=timeout)
                    if resp.get("status") != "ok":
                        resp.setdefault("code", "transfer_failed")

                elif cmd == "xmodem_recv" or cmd == "zmodem_recv":
                    remote_file = req["remote_file"]
                    local_path = req.get("local_path", "/tmp")
                    timeout = req.get("timeout", 120)

                    xfer = ZmodemTransfer(self.conn, self.logger)
                    resp = xfer.receive_file(remote_file, local_path, timeout=timeout)
                    if resp.get("status") != "ok":
                        resp.setdefault("code", "transfer_failed")

                else:
                    resp = {
                        "status": "error",
                        "code": "unknown_command",
                        "message": f"unknown cmd: {cmd}",
                    }
            except KeyError as e:
                resp = {
                    "status": "error",
                    "code": "bad_request",
                    "message": f"missing field: {e.args[0]}",
                }

            client.sendall(json.dumps(resp).encode() + b"\n")
        except Exception as e:
            try:
                client.sendall(json.dumps({
                    "status": "error",
                    "code": "internal_error",
                    "message": str(e),
                }).encode() + b"\n")
            except Exception:
                pass
        finally:
            client.close()

    def _wait_for_string(self, target, timeout):
        """等待日志中出现指定字符串（检查最近内容）

        回看窗口中的旧内容只有在它位于日志末尾时才算匹配。否则重新开机等
        场景会立刻命中重启前的 prompt，导致后续命令发得太早。
        """
        deadline = time.monotonic() + timeout
        log_path = self.logger.current_log
        initial_size = os.path.getsize(log_path)
        # 从文件末尾往前看最多 4KB，覆盖最近输出
        look_back = min(initial_size, 4096)
        start_pos = initial_size - look_back
        new_offset = initial_size - start_pos
        target_bytes = target.encode("utf-8")

        def _matched(raw, offset):
            pos = raw.rfind(target_bytes)
            if pos < 0:
                return False
            # A match that completes after the request is fresh. A match
            # that straddles the boundary also counts as fresh.
            if pos + len(target_bytes) > offset:
                return True
            tail = raw[pos + len(target_bytes):].decode(
                "utf-8", errors="replace")
            return not self._to_plain(tail).strip()

        while time.monotonic() < deadline:
            current_log = self.logger.current_log
            if current_log != log_path:
                # Log rotated while waiting. Drain the old file first so a
                # target written just before the rotation is not lost. Include
                # any data already written to the new file: if it follows the
                # old target, the target is no longer at the end of the console.
                try:
                    with open(log_path, "rb") as f:
                        f.seek(start_pos)
                        old_raw = f.read()
                except OSError:
                    old_raw = b""
                try:
                    with open(current_log, "rb") as f:
                        new_raw = f.read()
                except OSError:
                    new_raw = b""
                if _matched(old_raw + new_raw, new_offset):
                    return True
                log_path = current_log
                start_pos = 0
                new_offset = 0

            with open(log_path, "rb") as f:
                f.seek(start_pos)
                raw = f.read()

            if _matched(raw, new_offset):
                return True
            time.sleep(0.05)
        return False

    @staticmethod
    def _normalize_echo(text):
        """去除终端折行回显伪影：\\r 及折行点重复字符 (X\\rX → X)"""
        result = []
        i = 0
        while i < len(text):
            if text[i] == "\r":
                if result and i + 1 < len(text) and text[i + 1] == result[-1]:
                    i += 1
                i += 1
            else:
                result.append(text[i])
                i += 1
        return "".join(result)

    @classmethod
    def _to_plain(cls, text):
        """去掉 ANSI 序列、时间戳/session 标记并归一化终端回显。"""
        text = ANSI_ESCAPE_RE.sub("", text)
        lines = text.split("\n")
        plain_lines = []
        for line in lines:
            if line.startswith(SESSION_MARKER_PREFIX):
                continue
            if LOG_TIMESTAMP_RE.match(line):
                plain_lines.append(line[line.index("] ") + 2:])
            else:
                plain_lines.append(line)
        return cls._normalize_echo("\n".join(plain_lines))

    def _wait_for_prompt_after_cmd(self, cmd_text, prompt, timeout, mark=0):
        """发送命令后，在日志中找到命令回显，返回回显之后到下一个 prompt 之间的内容。
        mark: 发送命令前的日志偏移，只在这个位置之后搜索命令输出。"""
        deadline = time.monotonic() + timeout
        log_path = self.logger.current_log
        rotated = False
        if mark > os.path.getsize(log_path):
            # The mark came from a rotated-away log file.
            mark = 0
            rotated = True
        cmd_clean = cmd_text.replace("\r", "")
        cmd_lines = [l for l in cmd_clean.split("\n") if l.strip()]
        if len(cmd_lines) > 1:
            cmd_clean = cmd_lines[-1]
        after_cmd = ""

        def _find_echo_end(text, command):
            pos = text.rfind(command)
            if pos >= 0:
                return pos + len(command), True

            # Serial consoles may drop or redraw the beginning of long echoed
            # input lines. A sufficiently long command suffix is still a usable
            # echo boundary and prevents fallback matching inside the echo.
            min_suffix = min(len(command), 32)
            if len(command) < min_suffix:
                return -1, False
            for start in range(1, len(command) - min_suffix + 1):
                suffix = command[start:]
                pos = text.rfind(suffix)
                if pos >= 0:
                    return pos + len(suffix), True
            return -1, False

        while time.monotonic() < deadline:
            current_log = self.logger.current_log
            if current_log != log_path:
                log_path = current_log
                mark = 0
                rotated = True

            with open(log_path, "rb") as f:
                raw_content = f.read()

            after_mark_raw = raw_content[mark:] if mark > 0 else raw_content
            after_mark = after_mark_raw.decode("utf-8", errors="replace")
            plain = self._to_plain(after_mark)

            cmd_end, matched_echo = _find_echo_end(plain, cmd_clean)

            if matched_echo:
                after_cmd = plain[cmd_end:]
            else:
                after_cmd = plain

            prompt_stripped = prompt.rstrip()

            def _find_prompt(text, require_line_end=False):
                variants = [prompt]
                if prompt_stripped and prompt_stripped != prompt:
                    variants.append(prompt_stripped)

                best = -1
                for value in variants:
                    if not value:
                        continue
                    start = 0
                    while True:
                        pos = text.find(value, start)
                        if pos < 0:
                            break
                        if require_line_end:
                            line_end = text.find("\n", pos)
                            if line_end < 0:
                                line_end = len(text)
                            if text[pos + len(value):line_end].strip():
                                start = pos + 1
                                continue
                        if best < 0 or pos < best:
                            best = pos
                        break
                return best

            if matched_echo:
                prompt_pos = _find_prompt(after_cmd)
            else:
                # If the complete command echo was not found (e.g. a password
                # prompt), the echoed command itself must not be mistaken for
                # completion. Requiring the prompt to end its line still allows
                # prefixed prompts such as "~ # " or "root@board:/# ".
                prompt_pos = _find_prompt(after_cmd, require_line_end=True)
            if prompt_pos >= 0:
                # Never complete on a prompt that predates the command. This
                # matters for slow authentication: after 0.5s without new log
                # data the old code fell back to the full log and matched an
                # old prompt before the password response arrived.
                if rotated or (mark > 0 and plain.strip()):
                    result = after_cmd[:prompt_pos + len(prompt_stripped)]
                    return WaitResult(True, result.strip("\r\n"))

            time.sleep(0.05)

        return WaitResult(False, after_cmd.strip("\r\n") if matched_echo else "")
