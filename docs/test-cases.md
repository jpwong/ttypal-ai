# 测试用例说明

## test_ai_e2e.py — AI 端到端测试

基于录制回放 (ReplayBackend) 模拟真实设备交互，验证 AI agent 通过 socket 发送命令的完整流程。

| 用例 | 说明 |
|------|------|
| test_ai_send_echo_gets_correct_output | 回放数据在 mark 之后到达时，发送 echo 命令并等待 prompt，验证返回输出正确 |
| test_ai_send_uname_gets_kernel_info | 回放数据在 mark 之后到达时，发送 uname -a 命令，验证返回包含内核信息 |
| test_ai_send_simple_no_wait | 仅发送命令不等待响应 (fire-and-forget)，验证不阻塞 |
| test_ai_send_wait_timeout | 发送命令等待一个不存在的 prompt，验证返回结构化超时错误并保留已收集内容 |

## test_client.py — Python Client API

验证 `TtypalClient` 的公开 API、socket I/O、协议校验和异常映射。

| 用例 | 说明 |
|------|------|
| test_constructor_rejects_multiple_selectors | 构造器拒绝同时传入多个 session/board/socket selector |
| test_send_wait_success | `send_wait()` 生成正确请求并返回 daemon output |
| test_daemon_error_maps_to_daemon_error | daemon 普通错误映射为 `TtypalDaemonError` |
| test_wait_timeout_preserves_output | daemon `wait_timeout` 映射为 `TtypalTimeoutError` 并保留 partial output |
| test_missing_socket_maps_to_socket_not_found | socket 文件缺失映射为 `TtypalSocketNotFound` |
| test_refused_connection_maps_to_connection_error | socket 拒绝连接映射为 `TtypalConnectionError` |
| test_invalid_json_maps_to_protocol_error | 非 JSON 响应映射为 `TtypalProtocolError` |
| test_malformed_response_maps_to_protocol_error | 缺少 `status` 的响应映射为 `TtypalProtocolError` |

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

## test_cli_e2e.py — CLI 端到端测试

使用 ReplayBackend 模拟设备，通过 socket 和 subprocess 验证 `ttypal-send` / `ttypal-tail` / `ttypal-daemon` 行为。

| 用例 | 说明 |
|------|------|
| test_wait_marker_in_truncated_long_command_echo | 长命令回显被截断且回显中包含完成标记时，`send_wait` 等待真正单独输出的完成标记后再返回 |
| test_wait_escapes_terminal_control_bytes | 设备输出含 SO 时 `ttypal-send --wait` 默认显示 `^N`，`--raw` 保留原始控制字节 |
| test_tail_escapes_terminal_control_bytes | 日志含 SO 时 `ttypal-tail` 默认显示 `^N`，`--raw` 保留原始控制字节 |
| test_ttypal_help | `ttypal --help` 暴露 `--raw`/`--no-raw` |

## test_socket_wait.py — send_wait 日志匹配

| 用例 | 说明 |
|------|------|
| test_wait_for_prompt_after_cmd_returns_command_output | 使用发送前日志偏移等待 prompt 时，返回命令回显之后的输出 |
| test_wait_for_prompt_after_cmd_times_out_instead_of_empty_success | mark 后只有命令回显、没有 prompt 时，返回未匹配结果而不是误判成功 |
| test_wait_for_prompt_after_cmd_uses_byte_mark_with_unicode_prefix | mark 前存在 UTF-8 多字节字符时，按字节偏移切片并正确返回命令输出 |
| test_wait_for_prompt_after_unseen_echo_accepts_prefixed_prompt | 命令不回显（如输入密码）时，仍能识别 `~ # ` 这类带前缀的 prompt |
| test_wait_for_prompt_after_unseen_echo_accepts_ansi_colored_prompt | 命令不回显时，ANSI 彩色 prompt 也能识别 |
| test_wait_for_prompt_after_unseen_echo_accepts_bracket_prompt | 命令不回显时，`[root@board] # ` 这类方括号 prompt 不被误剥离 |
| test_wait_for_prompt_after_cmd_accepts_late_prompt | 慢认证场景等待并返回命令后的新 prompt，而不是旧 prompt |
| test_wait_for_prompt_after_unseen_echo_ignores_prompt_inside_echo | 命令不回显时，命令行内部的 prompt 文本不会被误判为完成 |
| test_wait_for_prompt_after_cmd_ignores_old_prompt_without_new_output | mark 后长时间无新输出（慢认证）时，不会用 mark 前的旧 prompt 提前完成 |
| test_wait_for_string_accepts_prompt_at_end | 日志末尾已有的 prompt 可立即匹配 |
| test_wait_for_string_accepts_ansi_colored_prompt | ANSI 彩色 prompt 位于日志末尾时可匹配 |
| test_to_plain_preserves_text_between_osc_sequences | 多个 OSC 8 超链接序列之间的正常文本不会被 ANSI 正则吞掉 |
| test_wait_for_string_does_not_strip_untimestamped_bracket_line | 无时间戳日志中的 `[  OK  ]` 行不会被当成时间戳前缀剥掉 |
| test_wait_for_string_does_not_strip_numeric_bracket_line | `[1]` 这类 job control 行不会被误认为时间戳 |
| test_wait_for_string_accepts_prompt_followed_by_timestamped_blank | prompt 后只有带时间戳的空行时仍视为日志末尾 |
| test_wait_for_string_with_real_logger_timestamps | 使用真实 Logger 时间戳格式时末尾判断正确 |
| test_wait_for_string_ignores_stale_prompt_followed_by_output | 回看窗口中的旧 prompt 后面出现新输出时不再匹配 |
| test_wait_for_string_target_spanning_request_boundary | 目标字符串跨越请求边界、在请求后补全时仍能匹配 |
| test_wait_for_string_matches_new_output | 请求之后新写入的字符串可以匹配 |
| test_wait_for_string_drains_old_file_on_rotation | 日志轮转前刚写入旧文件的末尾内容不会丢失 |
| test_wait_for_string_rejects_old_tail_when_new_file_has_output | 轮转后新文件已有输出时，旧文件末尾的旧目标不再算匹配 |

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

## test_serial_conn.py — 串口连接与锁

| 用例 | 说明 |
|------|------|
| test_lock_file_readonly_still_acquires_flock | 其他用户遗留的只读 lock 文件仍可通过只读 fd 获取 flock |
| test_lock_file_contention_raises_runtime_error | 同一串口已有实例持锁时，第二个实例启动失败 |
| test_read_returns_available_data | 有数据时一次读出全部可用字节 |
| test_read_honours_size_limit | 传入 size 时最多返回 size 字节，剩余数据保留到下次读取 |
| test_read_zero_returns_all_available | `read(0)` 与旧行为一致，读取全部可用字节 |
| test_read_records_rx_data | 读到的数据交给 recorder 记录 |
| test_idle_read_does_not_starve_writes | 串口空闲时 reader 不持锁阻塞等待，writer 不会被饿死（回归：probe 在安静控制台上超时） |

## test_sanitize.py — 终端控制字节转义

验证显示路径对 C0 控制字节的处理：不安全字节不会进入终端，日志内容不受该过滤器影响。

| 用例 | 说明 |
|------|------|
| test_sanitize_bytes_escapes_so_and_si | 裸 SO/SI 被转义为 `^N`/`^O`，不会进入终端 |
| test_sanitize_bytes_escapes_every_unsafe_control | 所有不安全的 C0 字节和 DEL 都按 caret 形式转义 |
| test_sanitize_bytes_keeps_safe_console_controls | BEL/BS/TAB/LF/CR/ESC 原样保留，ANSI 序列可用 |
| test_sanitize_bytes_keeps_utf8 | UTF-8 多字节序列不受影响 |
| test_sanitize_bytes_preserves_utf8_across_chunk_splits | 多字节 UTF-8 在任意分块边界拆分后仍不被破坏 |
| test_sanitize_bytes_escapes_other_c0_and_del | 其他 C0 控制字节和 DEL 使用 caret 形式显示 |
| test_sanitize_bytes_empty | 空数据直接返回 |
| test_sanitize_text_escapes_so_and_si | 文本路径（tail/send 输出）同样转义 SO/SI |
| test_sanitize_text_keeps_ansi_and_unicode | 文本路径保留 ANSI 序列和 Unicode |
| test_sanitize_text_escapes_other_c0_and_del | 文本路径转义其他 C0 和 DEL |

## test_terminal.py — 交互终端输出

| 用例 | 说明 |
|------|------|
| test_reader_sanitizes_terminal_but_logs_raw_bytes | 交互模式终端输出转义 SO，日志仍收到原始字节 |
| test_reader_raw_mode_forwards_bytes_verbatim | `raw=True` 时终端输出与日志都保持原始字节 |

## test_main.py — raw 模式解析

| 用例 | 说明 |
|------|------|
| test_raw_defaults_off_for_old_config | 旧配置没有 `[terminal]` 时默认转义 |
| test_raw_reads_terminal_config | `[terminal] raw = true` 时启用 raw |
| test_cli_raw_overrides_false_config | `--raw` 覆盖配置中的 false |
| test_cli_no_raw_overrides_true_config | `--no-raw` 覆盖配置中的 true |
| test_raw_ignores_invalid_terminal_section | `[terminal]` 类型异常时安全回退到转义模式 |

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

### 控制字节转义

| 用例 | 说明 |
|------|------|
| test_follow_sanitizes_control_bytes | `-f` 实时跟踪输出时 SO 被转义为 `^N` |
| test_follow_raw_mode_forwards_control_bytes | `follow(raw=True)` 保留原始控制字节 |

### Daemon 存活检测

| 用例 | 说明 |
|------|------|
| test_daemon_alive_no_pid_file | 无 PID 文件时返回 False |
| test_daemon_alive_stale_pid | PID 文件存在但进程已死时返回 False |
| test_daemon_alive_current_process | PID 文件指向存活进程时返回 True |
| test_daemon_alive_socket_exists | Unix socket 文件存在时返回 True |
| test_daemon_alive_permission_denied_pid | PID 指向其他用户进程导致 `kill(pid, 0)` 返回 EPERM 时视为运行中 |

## test_cli_headless.py — ttypal-daemon 命令

| 用例 | 说明 |
|------|------|
| test_read_pid_permission_denied_is_running | 读取 PID 时遇到 EPERM 不删除 PID 文件，并返回该 PID |
| test_read_pid_unlink_permission_denied_does_not_raise | 清理僵尸 PID 文件时无删除权限不抛异常 |
| test_stop_permission_denied_does_not_remove_session | 停止其他用户 daemon 无权限时给出提示，不清理 session |
| test_stop_waits_for_exit_before_cleanup | stop 发送 SIGTERM 后等待进程退出，再清理 PID 和 session 元数据 |
| test_stop_timeout_keeps_session_metadata | stop 等待退出超时时报告超时，并保留 PID 和 session 元数据 |
| test_status_session_ignores_stale_metadata | `status -S` 遇到 stale session 元数据时报告未运行 |

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
