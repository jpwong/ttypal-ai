# 测试用例说明

## test_ai_e2e.py — AI 端到端测试

基于录制回放 (ReplayBackend) 模拟真实设备交互，验证 AI agent 通过 socket 发送命令的完整流程。

| 用例 | 说明 |
|------|------|
| test_ai_send_echo_gets_correct_output | 发送 echo 命令并等待 prompt，验证返回的输出内容正确 |
| test_ai_send_uname_gets_kernel_info | 发送 uname -a 命令，验证返回包含内核信息 |
| test_ai_send_simple_no_wait | 仅发送命令不等待响应 (fire-and-forget)，验证不阻塞 |
| test_ai_send_wait_timeout | 发送命令等待一个不存在的 prompt，验证超时后返回已收集的内容 |

## test_config.py — 板子配置管理

| 用例 | 说明 |
|------|------|
| test_save_and_load | 保存板子配置到 TOML 文件，重新加载后内容一致 |
| test_list_boards | 保存多个配置后 list_boards 返回正确的板子名称列表 |
| test_delete_board | 删除配置文件后 load_board 返回 None |
| test_load_nonexistent | 加载不存在的配置返回 None |

## test_integration.py — 集成测试

使用 ReplayBackend 替代真实串口，验证 socket_server + serial_conn + logger 的协同工作。

| 用例 | 说明 |
|------|------|
| test_socket_send | 通过 Unix socket 发送命令，验证命令被写入串口 |
| test_socket_send_wait | 通过 socket 发送 send_wait 命令，验证从日志中匹配到 prompt 后返回正确输出 |
| test_logger_captures_replay_output | 验证 replay 回放数据正确写入日志文件 |
| test_socket_probe | 通过 socket 发送 probe 命令，验证发送回车并返回设备响应 |

## test_logger.py — 日志记录器

| 用例 | 说明 |
|------|------|
| test_logger_creates_file | Logger 初始化后创建日志文件，写入数据后文件包含内容 |
| test_logger_adds_timestamp | 日志首行有 session 标记，后续行添加时间戳前缀 `[HH:MM:SS]` |
| test_logger_rotation | 写入超过 rotate_size_kb 的数据后自动轮转，产生多个日志文件 |
| test_logger_multiline | 多行数据写入时每行都独立添加时间戳 |

## test_recorder.py — 原始数据录制器

| 用例 | 说明 |
|------|------|
| test_record_and_load | 录制 RX/TX 数据后保存为 JSONL 文件，重新加载内容一致 |
| test_ring_buffer | 超过 ring_size 后旧数据被丢弃，保留最新的 N 条记录 |
| test_empty_data_ignored | 空数据不产生记录 |
| test_record_tx_string | 字符串类型的 TX 数据被正确编码为 hex 录制 |

## test_regression.py — 回归测试

基于真实设备录制的 .rec 文件回放，验证不同场景的输出正确性。

| 用例 | 说明 |
|------|------|
| test_basic_commands_replay | 回放基础命令 (ls, echo) 录制数据，验证 RX 输出非空 |
| test_basic_commands_logger_output | 回放数据经过 logger 写入后日志文件包含预期内容 |
| test_file_ops_replay | 回放文件操作 (cat, ls -la) 录制数据 |
| test_replay_preserves_tx | 回放期间写入的 TX 数据被正确记录 |

## test_replay.py — 回放后端

| 用例 | 说明 |
|------|------|
| test_replay_read | ReplayBackend 按时序返回录制的 RX 数据 |
| test_replay_write_logs_tx | ReplayBackend 的 write 操作记录到 TX 日志 |
| test_replay_is_open | open/close 正确切换 is_open 状态 |

## test_tail.py — 日志读取 (ttypal-tail)

### Session 标记

| 用例 | 说明 |
|------|------|
| test_session_marker_in_new_file | 新日志文件首行包含 `## ttypal-session: <id>` 标记 |
| test_session_marker_consistent_after_rotation | 日志轮转后新文件的 session ID 与同一 Logger 实例一致 |

### 基本读取

| 用例 | 说明 |
|------|------|
| test_tail_basic | 请求最后 N 行返回正确内容 |
| test_tail_empty_dir | 空目录返回空列表 |
| test_tail_session_marker_not_in_output | tail 输出不包含 session 标记行 |

### 跨文件拼接

| 用例 | 说明 |
|------|------|
| test_tail_cross_file_same_session | 同一 session 内多个文件（轮转产生），请求行数跨文件时正确拼接 |
| test_tail_boundary_request_more_than_available | 请求行数超过当前 session 总行数，返回所有可用行不报错 |

### Session 边界隔离

| 用例 | 说明 |
|------|------|
| test_tail_does_not_cross_session_boundary | 两个不同 session，请求大量行数只返回当前 session 的数据 |
| test_tail_no_session_marker_in_old_files | 旧格式日志（无 session 标记）不被当前 session 读取 |

### 无时间戳模式

| 用例 | 说明 |
|------|------|
| test_logger_no_timestamp | timestamp_format="" 时日志不添加时间戳，直接写入原始数据 |
| test_tail_works_without_timestamp | 无时间戳模式下 tail 正确读取和过滤 session 标记 |
| test_tail_cross_session_without_timestamp | 无时间戳模式下 session 边界隔离仍然有效 |

### Daemon 存活检测

| 用例 | 说明 |
|------|------|
| test_daemon_alive_no_pid_file | 无 PID 文件时返回 False |
| test_daemon_alive_stale_pid | PID 文件存在但进程已死时返回 False |
| test_daemon_alive_current_process | PID 文件指向存活进程时返回 True |
| test_daemon_alive_socket_exists | Unix socket 文件存在时返回 True（使用真实 AF_UNIX socket） |

## test_macro.py — 宏录制/播放

| 用例 | 说明 |
|------|------|
| test_from_config_empty | 空配置创建无绑定的 Macro 实例 |
| test_from_config_with_bindings | 从配置加载 F 键绑定 |
| test_play_sends_commands | 播放宏时按序发送命令到串口 |
| test_play_sleep_command | sleep 特殊指令在播放时产生延迟 |
| test_play_unbound_key | 播放未绑定的键返回 False |
| test_record_and_stop | 录制命令并停止后返回正确的命令列表 |
| test_save_binding | 保存绑定后 has_binding 返回 True |
| test_fkey_escape_map_covers_all_keys | F1-F12 所有键都有 escape sequence 映射 |
