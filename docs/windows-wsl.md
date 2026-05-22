# Windows 安装指南 (WSL)

ttypal 通过 WSL2 + usbipd-win 在 Windows 上运行。本文档介绍完整的安装和配置流程。

## 前提条件

- Windows 10 (21H2+) 或 Windows 11
- WSL2 已启用，且已安装 Linux 发行版（推荐 Ubuntu 22.04+）

## 第一步：安装 usbipd-win

usbipd-win 将 Windows 主机的 USB 设备桥接到 WSL2 虚拟机。

在 **PowerShell (管理员)** 中执行：

```powershell
winget install usbipd
```

安装完成后重启电脑。

## 第二步：WSL 侧安装 USB 支持

在 **WSL 终端** 中执行：

```bash
sudo apt update
sudo apt install linux-tools-generic hwdata
sudo update-alternatives --install /usr/local/bin/usbip usbip /usr/lib/linux-tools/*-generic/usbip 20
```

## 第三步：安装 ttypal

在 **WSL 终端** 中：

```bash
pip install ttypal-ai
```

如需 ZMODEM 文件传输功能：

```bash
sudo apt install lrzsz
```

## 第四步：将 USB 串口设备桥接到 WSL

### 4.1 插入 USB 串口设备

将 USB 转串口线（如 CH340、CP2102、FTDI）插入 Windows 主机。

### 4.2 查看设备列表

在 **PowerShell (管理员)** 中：

```powershell
usbipd list
```

输出示例：

```
Connected:
BUSID  VID:PID    DEVICE                           STATE
1-3    1a86:7523  USB-SERIAL CH340 (COM3)          Not shared
2-1    0403:6001  USB Serial Converter (COM5)      Not shared
```

记下目标设备的 BUSID（如 `1-3`）。

### 4.3 绑定设备（仅需一次）

```powershell
usbipd bind --busid 1-3
```

### 4.4 附加到 WSL

```powershell
usbipd attach --wsl --busid 1-3
```

### 4.5 在 WSL 中确认

```bash
ls /dev/ttyUSB*
# 或
ls /dev/ttyACM*
```

应显示 `/dev/ttyUSB0` 或 `/dev/ttyACM0`。

### 4.6 设置串口权限

```bash
sudo chmod 666 /dev/ttyUSB0
# 或添加用户到 dialout 组（永久生效）：
sudo usermod -aG dialout $USER
```

## 第五步：配置并使用 ttypal

```bash
# 创建板子配置
ttypal --setup

# 启动守护进程
ttypal-daemon start -b myboard

# 发送命令
ttypal-send --wait "# " "uname -a"

# 查看日志
ttypal-tail -n 30
```

## 每次使用前

USB 设备拔插后需要重新附加到 WSL。在 **PowerShell (管理员)** 中：

```powershell
usbipd attach --wsl --busid 1-3
```

### 自动附加（可选）

创建 PowerShell 脚本 `attach-serial.ps1`，开机或插入设备后执行：

```powershell
# attach-serial.ps1
$busid = "1-3"  # 改为你的设备 BUSID
usbipd attach --wsl --busid $busid
```

可将此脚本添加到 Windows 任务计划程序，在用户登录时自动执行。

## 故障排查

### `usbipd list` 看不到设备

- 确认 USB 线缆正常连接
- 检查 Windows 设备管理器中是否识别到 COM 端口
- 安装设备驱动（CH340 需要 [CH341SER 驱动](http://www.wch.cn/downloads/CH341SER_EXE.html)）

### `usbipd attach` 失败

- 确认以管理员权限运行 PowerShell
- 确认已执行 `usbipd bind`
- 确认 WSL2 正在运行：`wsl --status`

### WSL 中看不到 /dev/ttyUSB*

- 确认 `usbipd attach` 成功（STATE 应显示 `Attached`）
- 运行 `dmesg | tail -20` 查看内核是否识别到设备
- 某些 WSL 内核版本需要更新：`wsl --update`

### 权限不足 (Permission denied)

```bash
sudo chmod 666 /dev/ttyUSB0
```

注意：此权限在设备重新附加后会重置，需要再次设置。永久方案：

```bash
# 创建 udev 规则
sudo tee /etc/udev/rules.d/99-serial.rules << 'EOF'
SUBSYSTEM=="tty", MODE="0666"
EOF
sudo udevadm control --reload-rules
```

### ZMODEM 传输失败

- 确认 WSL 中已安装 lrzsz：`which sz && which rz`
- 确认目标设备也安装了 lrzsz
- RK 平台可能触发 FIQ debugger，参见 [ZMODEM 性能报告](zmodem-bench.md)

## 已知限制

1. **每次拔插需重新附加** — USB 设备断开后 WSL 中的 `/dev/ttyUSB*` 消失，需在 Windows 侧重新执行 `usbipd attach`
2. **延迟略高于原生** — usbipd 桥接引入约 1-2ms 额外延迟，对串口调试无影响
3. **多设备需逐个附加** — 每个 USB 串口设备需要单独 bind 和 attach
