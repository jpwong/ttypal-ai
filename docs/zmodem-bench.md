# ZMODEM 串口文件传输测试报告

## 测试环境

| 项目 | 详情 |
|------|------|
| 主机 | Arch Linux, lrzsz 0.12.20 (`lrzsz-sz` / `lrzsz-rz`) |
| 设备 | RK3562 EVB2, Buildroot, BusyBox lrzsz (`rz` / `sz`) |
| 串口 | /dev/ttyUSB1, 1500000 baud (8N1, no flow control) |
| 传输工具 | ttypal-xfer (ZMODEM via lrzsz 桥接) |
| 测试日期 | 2026-06-02 (v0.3.0, sz -e 修复后) |

## 性能测试

### 发送 (主机 → 设备) — 随机二进制数据

| 文件大小 | 耗时 | 速度 | MD5 校验 | 结果 |
|---------|------|------|---------|------|
| 20 B | 0.8s | — | OK | PASS |
| 10 KB | 0.9s | 10.9 KB/s | OK | PASS |
| 50 KB | — | — | OK | PASS |
| 100 KB | 1.6s | 62.5 KB/s | OK | PASS |
| 2 MB | 15.4s | 132.9 KB/s | OK | PASS |
| 4 MB | 74s | — | — | FAIL (FIQ) |

### 发送 (主机 → 设备) — 纯 ASCII 数据

| 文件大小 | 耗时 | 速度 | MD5 校验 | 结果 |
|---------|------|------|---------|------|
| 1 KB | 0.8s | 1.2 KB/s | OK | PASS |
| 10 KB | 0.9s | 10.9 KB/s | OK | PASS |
| 100 KB | 1.5s | 66.7 KB/s | OK | PASS |
| 512 KB | 63s | — | — | FAIL (FIQ) |

### 接收 (设备 → 主机) — 随机二进制数据 (sz -e)

| 文件大小 | 耗时 | 速度 | MD5 校验 | 结果 |
|---------|------|------|---------|------|
| 1 KB | 0.4s | 2.4 KB/s | OK | PASS |
| 10 KB | 0.6s | 16.7 KB/s | OK | PASS |
| 50 KB | — | — | OK | PASS |
| 100 KB | 1.4s | 71.4 KB/s | OK | PASS |
| 512 KB | 5.5s | 93.1 KB/s | OK | PASS |
| 1 MB | 11.2s | 91.4 KB/s | OK | PASS |

### 分析

- 发送方向 100KB 以内稳定通过，大文件有概率触发 FIQ debugger
- 接收方向（`sz -e` ZDLE 全转义）1MB 通过，比发送方向更稳定
- 小文件 (<10 KB) 受协议握手开销影响，速度较低
- 大文件发送速度约 130 KB/s，接收约 90 KB/s
- FIQ 触发是概率性的，同一文件可能时过时不过

## 已知问题

### RK 平台 FIQ Debugger 干扰

**现象:** 传输过程中设备进入 FIQ debug 模式（`debug>` 提示符），传输中断。

**根本原因:** FIQ debugger 监听串口 RX 上的特定字节序列。触发源可能是文件数据本身，也可能是 ZMODEM 协议帧（CRC-32、帧头等二进制字段）。文件越大，流过串口的字节越多，命中触发序列的概率越高。目前没有有效的软件层面规避方法。

**影响范围:**
- 发送 (put): >100KB 有概率触发
- 接收 (get): `sz -e` 转义后 1MB 通过，但更大文件也可能触发

**恢复方法:** 设备进入 `debug>` 后输入 `console` 退出。

**规避方法:**
- 文件 <100KB 基本可靠
- 大文件优先使用网络传输 (TFTP/SCP)
- 彻底解决：内核配置 `CONFIG_FIQ_DEBUGGER=n` 或启动参数 `no_fiq_debugger`

### sz -e 修复 (v0.3.0)

**问题:** 接收文件时（设备 `sz` → 主机 `rz`），设备 tty 的 `onlcr` 标志将数据中的 `\x0a` (LF) 转换为 `\x0d\x0a` (CRLF)，导致二进制文件校验失败。

**修复:** `receive_file` 调用设备端 `sz` 时加 `-e` 参数（ZDLE-escape 所有控制字符），绕过 tty 转换。修复后二进制文件 1MB 以内校验一致。

### XMODEM 不适用于有背景打印的环境

XMODEM 协议缺乏帧同步机制，设备端的背景打印（内核消息、应用日志）会破坏协议帧，导致传输失败。已切换为 ZMODEM 方案（lrzsz 桥接），ZMODEM 具有帧头标识和 CRC32 校验，抗干扰能力更强。
