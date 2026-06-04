import json
import os
import socket
import threading
import time

from .logger import SESSION_MARKER_PREFIX
from .zmodem_transfer import ZmodemTransfer


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

            req = json.loads(line)
            cmd = req.get("cmd", "send")

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

                output = self._wait_for_prompt_after_cmd(
                    payload.strip(), prompt, timeout, mark)
                resp = {"status": "ok", "output": output}

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
                    resp = {"status": "error", "message": f"等待 '{expect}' 超时"}

            elif cmd == "expect_send_wait":
                expect = req["expect"]
                payload = req["data"]
                prompt = req.get("prompt", self.default_prompt)
                timeout = req.get("timeout", 10)
                if not payload.endswith("\n"):
                    payload += "\r\n"

                ok = self._wait_for_string(expect, timeout)
                if not ok:
                    resp = {"status": "error", "message": f"等待 '{expect}' 超时"}
                else:
                    mark = os.path.getsize(self.logger.current_log)
                    self.conn.write(payload)
                    output = self._wait_for_prompt_after_cmd(
                        payload.strip(), prompt, timeout, mark)
                    resp = {"status": "ok", "output": output}

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

            elif cmd == "xmodem_recv" or cmd == "zmodem_recv":
                remote_file = req["remote_file"]
                local_path = req.get("local_path", "/tmp")
                timeout = req.get("timeout", 120)

                xfer = ZmodemTransfer(self.conn, self.logger)
                resp = xfer.receive_file(remote_file, local_path, timeout=timeout)

            else:
                resp = {"status": "error", "message": f"unknown cmd: {cmd}"}

            client.sendall(json.dumps(resp).encode() + b"\n")
        except Exception as e:
            try:
                client.sendall(json.dumps({"status": "error", "message": str(e)}).encode() + b"\n")
            except Exception:
                pass
        finally:
            client.close()

    def _wait_for_string(self, target, timeout):
        """等待日志中出现指定字符串（检查最近内容）"""
        deadline = time.monotonic() + timeout
        log_path = self.logger.current_log
        file_size = os.path.getsize(log_path)
        # 从文件末尾往前看最多 4KB，覆盖最近输出
        look_back = min(file_size, 4096)
        start_pos = file_size - look_back

        while time.monotonic() < deadline:
            with open(log_path, "rb") as f:
                f.seek(start_pos)
                content = f.read().decode("utf-8", errors="replace")

            if target in content:
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

    def _wait_for_prompt_after_cmd(self, cmd_text, prompt, timeout, mark=0):
        """发送命令后，在日志中找到命令回显，返回回显之后到下一个 prompt 之间的内容。
        mark: 发送命令前的日志偏移，优先在此之后搜索回显；仅当 mark 后持续无新数据时才扩大到全量。"""
        deadline = time.monotonic() + timeout
        log_path = self.logger.current_log
        cmd_clean = cmd_text.replace("\r", "")
        cmd_lines = [l for l in cmd_clean.split("\n") if l.strip()]
        if len(cmd_lines) > 1:
            cmd_clean = cmd_lines[-1]
        after_cmd = ""
        empty_count = 0

        while time.monotonic() < deadline:
            with open(log_path, "rb") as f:
                content = f.read().decode("utf-8", errors="replace")

            def _to_plain(text):
                lines = text.split("\n")
                plain_lines = []
                for line in lines:
                    if line.startswith(SESSION_MARKER_PREFIX):
                        continue
                    if line.startswith("[") and "] " in line:
                        plain_lines.append(line[line.index("] ") + 2:])
                    else:
                        plain_lines.append(line)
                return self._normalize_echo("\n".join(plain_lines))

            after_mark = content[mark:] if mark > 0 else content
            use_full = mark > 0 and not after_mark.strip() and empty_count >= 10
            if mark > 0 and not after_mark.strip():
                empty_count += 1
            else:
                empty_count = 0

            base = content if use_full else (after_mark if mark > 0 else content)
            plain = _to_plain(base)

            cmd_pos = plain.rfind(cmd_clean)

            if cmd_pos >= 0:
                after_cmd = plain[cmd_pos + len(cmd_clean):]
            else:
                after_cmd = plain

            prompt_stripped = prompt.rstrip()
            if cmd_pos >= 0:
                prompt_pos = after_cmd.find(prompt_stripped)
            else:
                prompt_pos = after_cmd.rfind(prompt_stripped)
            if prompt_pos >= 0:
                if use_full or (mark > 0 and after_mark.strip()):
                    result = after_cmd[:prompt_pos + len(prompt_stripped)]
                    return result.strip("\r\n")

            time.sleep(0.05)

        return after_cmd.strip("\r\n") if cmd_pos >= 0 else ""
