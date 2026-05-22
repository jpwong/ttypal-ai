# macOS 安装指南

ttypal 在 macOS 上原生运行，无需额外适配。

## 安装

```bash
pip install ttypal-ai
```

如需 ZMODEM 文件传输功能：

```bash
brew install lrzsz
```

## 串口设备识别

插入 USB 转串口线后，设备出现在 `/dev/` 下：

```bash
ls /dev/cu.* /dev/tty.*
```

常见设备名：

| 芯片 | 设备路径 |
|------|----------|
| CH340 | `/dev/cu.usbserial-*` |
| CP2102 | `/dev/cu.SLAB_USBtoUART` |
| FTDI | `/dev/cu.usbserial-*` |
| CDC ACM (原生 USB) | `/dev/cu.usbmodem*` |

> **`cu.*` vs `tty.*`：** macOS 下两者都指向同一设备。ttypal 使用 `cu.*` 即可（不会等待 DCD 信号）。

## 驱动安装

macOS 12+ 内置了大多数 USB 串口芯片的驱动，通常即插即用。如果设备未识别：

| 芯片 | 驱动 |
|------|------|
| CH340/CH341 | [WCH 官方驱动](http://www.wch.cn/downloads/CH341SER_MAC_ZIP.html) |
| CP2102 | [Silicon Labs 驱动](https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers) |
| FTDI | macOS 内置 AppleUSBFTDI，通常无需额外安装 |

安装第三方驱动后需在 **系统设置 → 隐私与安全性** 中允许加载。

## 配置并使用

```bash
# 创建板子配置
ttypal --setup
# port 填写 /dev/cu.usbserial-XXX

# 交互模式
ttypal -b myboard

# 启动守护进程（AI 自动化）
ttypal-daemon start -b myboard

# 发送命令
ttypal-send --wait "# " "uname -a"

# 查看日志
ttypal-tail -n 30
```

## 串口权限

macOS 默认允许当前用户访问 `/dev/cu.*` 设备，通常无需额外设置。

如果遇到权限问题：

```bash
sudo chmod 666 /dev/cu.usbserial-XXX
```

## 故障排查

### 设备未出现在 /dev/ 下

1. 检查 USB 线缆（部分线缆仅供充电，无数据线）
2. 查看系统信息：**Apple 菜单 → 关于本机 → 系统报告 → USB**，确认设备已识别
3. 安装对应芯片驱动（见上表）
4. macOS Ventura+ 安装驱动后需重启

### System Extension Blocked

安装 CH340 或 CP2102 驱动后系统阻止加载：

1. 打开 **系统设置 → 隐私与安全性**
2. 底部会显示被阻止的扩展，点击 **允许**
3. 重启电脑

### ttypal 连接后无输出

- 确认波特率正确（常见值：115200, 9600, 1500000）
- 确认使用 `cu.*` 而非 `tty.*` 设备名
- 确认没有其他程序占用该串口（如 `screen`、`minicom`）：

```bash
lsof /dev/cu.usbserial-XXX
```

### ZMODEM 传输失败

- 确认已安装 lrzsz：`which sz && which rz`
- 确认目标设备也安装了 lrzsz
- Homebrew 安装的 lrzsz 路径为 `/opt/homebrew/bin/sz`（Apple Silicon）或 `/usr/local/bin/sz`（Intel），确认在 PATH 中
