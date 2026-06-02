import json
import os
import socket
import threading
import time

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

                self.conn.write(payload)

                output = self._wait_for_prompt_after_cmd(
                    payload.strip(), prompt, timeout)
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
                    self.conn.write(payload)
                    output = self._wait_for_prompt_after_cmd(
                        payload.strip(), prompt, timeout)
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

    def _wait_for_prompt_after_cmd(self, cmd_text, prompt, timeout):
        """发送命令后，在日志中找到命令回显，返回回显之后到下一个 prompt 之间的内容"""
        deadline = time.monotonic() + timeout
        log_path = self.logger.current_log

        while time.monotonic() < deadline:
            with open(log_path, "rb") as f:
                content = f.read().decode("utf-8", errors="replace")

            # 去掉时间戳提取纯内容
            lines = content.split("\n")
            plain_lines = []
            for line in lines:
                if line.startswith("[") and "] " in line:
                    plain_lines.append(line[line.index("] ") + 2:])
                else:
                    plain_lines.append(line)
            plain = "\n".join(plain_lines)

            # 找到命令回显的位置
            cmd_pos = plain.find(cmd_text)
            if cmd_pos < 0:
                time.sleep(0.05)
                continue

            # 从命令之后开始找 prompt
            after_cmd = plain[cmd_pos + len(cmd_text):]
            prompt_stripped = prompt.rstrip()
            prompt_pos = after_cmd.find(prompt_stripped)
            if prompt_pos >= 0:
                result = after_cmd[:prompt_pos + len(prompt_stripped)]
                return result.strip("\r\n")

            time.sleep(0.05)

        # 超时：返回命令之后收集到的所有内容
        return after_cmd.strip("\r\n") if "after_cmd" in dir() else ""
