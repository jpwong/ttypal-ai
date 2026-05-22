import os
import select
import shutil
import subprocess
import threading
import time


def _find_command(name):
    for cmd in [name, f"lrzsz-{name}"]:
        path = shutil.which(cmd)
        if path:
            return path
    return None


class ZmodemTransfer:
    def __init__(self, serial_conn, log):
        self.conn = serial_conn
        self.logger = log
        self._serial = serial_conn._serial

    def send_file(self, filepath, timeout=120):
        if not os.path.isfile(filepath):
            return {"status": "error", "message": f"文件不存在: {filepath}"}

        sz_path = _find_command("sz")
        if not sz_path:
            return {"status": "error", "message": "主机未安装 lrzsz (sz 命令不存在)"}

        file_size = os.path.getsize(filepath)

        self.logger.pause()
        self.conn.pause()
        time.sleep(0.2)
        self._flush_input()

        try:
            self._serial.write(b"rz\r\n")
            time.sleep(0.5)
            self._flush_input()

            proc = subprocess.Popen(
                [sz_path, "--zmodem", filepath],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            ok = self._bridge(proc, timeout)

            if ok and proc.returncode == 0:
                return {"status": "ok", "bytes_sent": file_size}
            else:
                stderr = proc.stderr.read().decode(errors="replace").strip()
                return {"status": "error", "message": stderr or f"ZMODEM 传输失败 (rc={proc.returncode})"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
        finally:
            self._serial.timeout = 0.1
            self.conn.resume()
            self.logger.resume()

    def receive_file(self, remote_file, local_dir, timeout=120):
        rz_path = _find_command("rz")
        if not rz_path:
            return {"status": "error", "message": "主机未安装 lrzsz (rz 命令不存在)"}

        os.makedirs(local_dir, exist_ok=True)

        self.logger.pause()
        self.conn.pause()
        time.sleep(0.2)
        self._flush_input()

        try:
            self._serial.write(f"sz {remote_file}\r\n".encode())
            time.sleep(0.5)
            self._flush_input()

            proc = subprocess.Popen(
                [rz_path, "--zmodem", "--overwrite"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=local_dir,
            )

            ok = self._bridge(proc, timeout)

            if ok and proc.returncode == 0:
                basename = os.path.basename(remote_file)
                local_path = os.path.join(local_dir, basename)
                if os.path.exists(local_path):
                    received_size = os.path.getsize(local_path)
                    return {"status": "ok", "bytes_received": received_size, "path": local_path}
                return {"status": "ok", "path": local_dir}
            else:
                stderr = proc.stderr.read().decode(errors="replace").strip()
                return {"status": "error", "message": stderr or "ZMODEM 接收失败"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
        finally:
            self._serial.timeout = 0.1
            self.conn.resume()
            self.logger.resume()

    def _bridge(self, proc, timeout):
        deadline = time.monotonic() + timeout
        done = threading.Event()

        def serial_to_proc():
            while not done.is_set():
                if time.monotonic() > deadline:
                    break
                self._serial.timeout = 0.02
                waiting = self._serial.in_waiting
                data = self._serial.read(max(waiting, 1))
                if data:
                    try:
                        proc.stdin.write(data)
                        proc.stdin.flush()
                    except (BrokenPipeError, OSError):
                        break

        def proc_to_serial():
            while not done.is_set():
                if time.monotonic() > deadline:
                    break
                try:
                    # 用 select 避免阻塞在 read 上
                    r, _, _ = select.select([proc.stdout], [], [], 0.1)
                    if r:
                        data = proc.stdout.read1(4096)
                        if not data:
                            break
                        self._serial.write(data)
                except (OSError, AttributeError, ValueError):
                    break

        t_read = threading.Thread(target=serial_to_proc, daemon=True)
        t_write = threading.Thread(target=proc_to_serial, daemon=True)
        t_read.start()
        t_write.start()

        remaining = deadline - time.monotonic()
        try:
            proc.wait(timeout=max(remaining, 0))
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

        done.set()
        t_read.join(timeout=2)
        t_write.join(timeout=2)

        try:
            proc.stdin.close()
        except Exception:
            pass

        return proc.returncode == 0

    def _flush_input(self):
        while self._serial.in_waiting:
            self._serial.read(self._serial.in_waiting)
