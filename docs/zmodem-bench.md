# ZMODEM 串口文件传输测试报告

## 测试环境

| 项目 | 详情 |
|------|------|
| 主机 | Arch Linux, lrzsz 0.12.20 (`lrzsz-sz` / `lrzsz-rz`) |
| 设备 | RK3562 EVB2, Buildroot, BusyBox lrzsz (`rz` / `sz`) |
| 串口 | /dev/ttyUSB1, 1500000 baud (8N1, no flow control) |
| 传输工具 | ttypal-xfer (ZMODEM via lrzsz 桥接) |
| 测试日期 | 2026-05-22 |

## 性能测试

使用纯 ASCII 数据，避免 RK FIQ debugger 触发（见已知问题）。

### 发送 (主机 → 设备)

| 文件大小 | 耗时 | 速度 | MD5 校验 |
|---------|------|------|---------|
| 1 KB | 0.8s | 1.2 KB/s | OK |
| 10 KB | 0.9s | 10.9 KB/s | OK |
| 100 KB | 1.5s | 65.6 KB/s | OK |
| 512 KB | 4.4s | 116.9 KB/s | OK |
| 1 MB | 7.9s | 129.6 KB/s | OK |
| 2 MB | 14.9s | 137.1 KB/s | OK |
| 4 MB | 29.2s | 140.5 KB/s | OK |

### 接收 (设备 → 主机)

| 文件大小 | 耗时 | 速度 | MD5 校验 |
|---------|------|------|---------|
| 1 KB | 0.9s | 1.1 KB/s | OK |
| 10 KB | 0.9s | 10.6 KB/s | OK |
| 100 KB | 1.6s | 61.1 KB/s | OK |
| 512 KB | 4.9s | 104.4 KB/s | OK |
| 1 MB | 8.9s | 115.0 KB/s | OK |
| 2 MB | 17.2s | 119.1 KB/s | OK |
| 4 MB | 33.6s | 122.0 KB/s | OK |

### 分析

- 大文件发送速度稳定在 **~140 KB/s**，接近 1.5M baud 理论上限 (~150 KB/s) 的 **93%**
- 接收速度略低于发送 (~122 KB/s)，约为理论上限的 **81%**
- 小文件 (<10 KB) 受协议握手开销影响，速度较低
- 所有测试 MD5 校验一致，数据传输完整可靠

## 已知问题

### RK 平台 FIQ Debugger 干扰

**现象:** 传输二进制数据（如 `/dev/urandom` 生成的随机数据）时，数据流中可能包含 RK FIQ debugger 的触发序列，导致板子进入 FIQ debug 模式，传输中断。

**影响:** 板子进入 `debug>` 提示符，串口 shell 不可用。需要输入 `console` 命令退出 FIQ debug 恢复正常。

**规避方法:**
- 传输纯文本或已知安全的二进制数据时不受影响
- 传输任意二进制数据时需评估风险
- 可通过内核配置禁用 FIQ debugger (`CONFIG_FIQ_DEBUGGER=n` 或启动参数 `no_fiq_debugger`)

**根本原因:** RK 平台的 FIQ debugger 监听串口上的特定字节序列（通常是 serial break 或特定魔数），ZMODEM 协议帧中的二进制数据可能恰好匹配该序列。

### XMODEM 不适用于有背景打印的环境

XMODEM 协议缺乏帧同步机制，设备端的背景打印（内核消息、应用日志）会破坏协议帧，导致传输失败。已切换为 ZMODEM 方案（lrzsz 桥接），ZMODEM 具有帧头标识和 CRC32 校验，抗干扰能力更强。
