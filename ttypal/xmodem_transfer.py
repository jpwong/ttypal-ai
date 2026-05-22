import os
import time

from xmodem import XMODEM


class XmodemTransfer:
    def __init__(self, serial_conn, log):
        self.conn = serial_conn
        self.logger = log
        self._serial = serial_conn._serial

    def _getc(self, size, timeout=1):
        end = time.monotonic() + timeout
        data = b""
        while len(data) < size:
            remaining = end - time.monotonic()
            if remaining <= 0:
                break
            self._serial.timeout = min(remaining, 0.5)
            chunk = self._serial.read(size - len(data))
            if chunk:
                data += chunk
        if data:
            self._debug(f"getc({size}): {data.hex()}")
        else:
            self._debug(f"getc({size}): timeout")
        return data or None

    def _putc(self, data, timeout=1):
        self._serial.write(data)
        return len(data)

    def _debug(self, msg):
        with open("/tmp/ttypal-xmodem-debug.log", "a") as f:
            f.write(f"{time.time():.3f} {msg}\n")

    def _flush_input(self):
        while self._serial.in_waiting:
            self._serial.read(self._serial.in_waiting)

    def _do_send(self, filepath, timeout=60):
        """执行 XMODEM 发送（调用前需已暂停 reader 并清空缓冲区）"""
        if not os.path.isfile(filepath):
            return {"status": "error", "message": f"文件不存在: {filepath}"}

        file_size = os.path.getsize(filepath)
        try:
            modem = XMODEM(self._getc, self._putc)
            with open(filepath, "rb") as f:
                success = modem.send(f, timeout=timeout, retry=32)

            if success:
                return {"status": "ok", "bytes_sent": file_size}
            else:
                return {"status": "error", "message": "XMODEM 传输失败"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
        finally:
            self._serial.timeout = 0.1

    def _do_recv(self, filepath, timeout=60):
        """执行 XMODEM 接收（调用前需已暂停 reader 并清空缓冲区）"""
        try:
            modem = XMODEM(self._getc, self._putc)
            with open(filepath, "wb") as f:
                success = modem.recv(f, timeout=timeout, retry=16)

            if success:
                received_size = os.path.getsize(filepath)
                return {"status": "ok", "bytes_received": received_size}
            else:
                if os.path.exists(filepath):
                    os.unlink(filepath)
                return {"status": "error", "message": "XMODEM 接收失败"}
        except Exception as e:
            if os.path.exists(filepath):
                os.unlink(filepath)
            return {"status": "error", "message": str(e)}
        finally:
            self._serial.timeout = 0.1

    def send_file(self, filepath, timeout=60):
        """完整流程：暂停 reader → 发送 → 恢复（用于 CLI 直连模式）"""
        self.logger.pause()
        self.conn.pause()
        time.sleep(0.1)
        self._flush_input()
        try:
            return self._do_send(filepath, timeout)
        finally:
            self.conn.resume()
            self.logger.resume()

    def receive_file(self, filepath, timeout=60):
        """完整流程：暂停 reader → 接收 → 恢复"""
        self.logger.pause()
        self.conn.pause()
        time.sleep(0.1)
        self._flush_input()
        try:
            return self._do_recv(filepath, timeout)
        finally:
            self.conn.resume()
            self.logger.resume()
