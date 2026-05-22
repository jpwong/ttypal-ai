# Linux 安装指南

ttypal 在 Linux 上原生运行，这是主要开发和测试平台。

## 安装

```bash
pip install ttypal-ai
```

如需 ZMODEM 文件传输功能：

```bash
# Debian/Ubuntu
sudo apt install lrzsz

# Arch Linux
sudo pacman -S lrzsz

# Fedora/RHEL
sudo dnf install lrzsz
```

## 串口设备识别

插入 USB 转串口线后：

```bash
ls /dev/ttyUSB* /dev/ttyACM*
```

常见设备名：

| 芯片 | 设备路径 |
|------|----------|
| CH340/CH341 | `/dev/ttyUSB0` |
| CP2102/CP2104 | `/dev/ttyUSB0` |
| FTDI | `/dev/ttyUSB0` |
| CDC ACM (原生 USB) | `/dev/ttyACM0` |

多个设备按插入顺序编号：`ttyUSB0`, `ttyUSB1`, ...

查看设备详情：

```bash
# 查看内核识别日志
dmesg | grep -i tty

# 查看设备信息
udevadm info /dev/ttyUSB0
```

## 串口权限

默认情况下普通用户无法访问串口设备。推荐方案：

```bash
# 将用户添加到 dialout 组（需重新登录生效）
sudo usermod -aG dialout $USER
```

临时方案：

```bash
sudo chmod 666 /dev/ttyUSB0
```

永久方案（udev 规则）：

```bash
sudo tee /etc/udev/rules.d/99-serial.rules << 'EOF'
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", MODE="0666"   # CH340
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", MODE="0666"   # CP2102
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", MODE="0666"   # FTDI
EOF
sudo udevadm control --reload-rules
sudo udevadm trigger
```

## 配置并使用

```bash
# 创建板子配置
ttypal --setup
# port 填写 /dev/ttyUSB0

# 交互模式
ttypal -b myboard

# 启动守护进程（AI 自动化）
ttypal-daemon start -b myboard

# 发送命令
ttypal-send --wait "# " "uname -a"

# 查看日志
ttypal-tail -n 30
```

## 驱动

主流 Linux 内核已内置所有常见 USB 串口芯片驱动，即插即用：

- **CH340/CH341** — `ch341` 模块（内核 2.6+）
- **CP2102/CP2104** — `cp210x` 模块
- **FTDI** — `ftdi_sio` 模块
- **PL2303** — `pl2303` 模块

确认驱动已加载：

```bash
lsmod | grep -E "ch341|cp210x|ftdi_sio|pl2303"
```

## 固定设备名（可选）

多设备环境下 `ttyUSB0` / `ttyUSB1` 编号不稳定。用 udev 规则创建固定符号链接：

```bash
# 查看设备属性
udevadm info -a /dev/ttyUSB0 | grep -E "idVendor|idProduct|serial"

# 创建规则
sudo tee /etc/udev/rules.d/99-ttypal.rules << 'EOF'
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", SYMLINK+="ttypal-myboard"
EOF
sudo udevadm control --reload-rules
sudo udevadm trigger
```

之后可在 ttypal 配置中使用 `/dev/ttypal-myboard` 作为 port，不受插入顺序影响。

## 故障排查

### 设备未出现在 /dev/ 下

1. 检查 USB 线缆（部分线缆仅供充电）
2. `dmesg | tail -20` 查看内核日志
3. `lsusb` 确认 USB 设备已识别
4. 确认驱动模块已加载：`lsmod | grep ch341`

### Permission denied

```bash
# 检查当前用户组
groups
# 如果没有 dialout，添加后重新登录
sudo usermod -aG dialout $USER
```

### ttypal 连接后无输出

- 确认波特率正确（常见值：115200, 9600, 1500000）
- 确认没有其他程序占用该串口：

```bash
fuser /dev/ttyUSB0
# 或
lsof /dev/ttyUSB0
```

- 检查设备是否已断开：`dmesg | tail`

### brltty 冲突 (Ubuntu)

Ubuntu 预装的 brltty（盲文显示器服务）会抢占 CP2102 和 FTDI 设备，导致设备插入后立即消失。

```bash
# 确认是否被 brltty 抢占
dmesg | grep -i brltty

# 禁用 brltty
sudo systemctl stop brltty
sudo systemctl disable brltty
# 或直接卸载
sudo apt remove brltty
```
