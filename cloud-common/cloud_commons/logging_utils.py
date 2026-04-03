#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import sys
from typing import Optional, Callable

# ANSI 颜色代码 (终端支持时使用)
COLORS = {
    'reset': "\033[0m",
    'bold': "\033[1m",
    'red': "\033[31m",
    'green': "\033[32m",
    'yellow': "\033[33m",
    'blue': "\033[34m",
    'magenta': "\033[35m",
    'cyan': "\033[36m"
}

class LogConfig:
    """集中管理日志配置的类"""
    def __init__(self):
        self.verbose = False
        self.silent = False
        self.debug_mode = 0
        self.use_colors = sys.stdout.isatty()
        self.log_hook = None  # 自定义日志钩子函数
    
    def enable_debug_flag(self, flag: int):
        """启用特定的调试标志"""
        self.debug_mode |= flag
    
    def disable_debug_flag(self, flag: int):
        """禁用特定的调试标志"""
        self.debug_mode &= ~flag
    
    def has_debug_flag(self, flag: int) -> bool:
        """检查是否启用了特定的调试标志"""
        return bool(self.debug_mode & flag)

# 全局日志配置实例
_CONFIG = LogConfig()

def get_config() -> LogConfig:
    """获取全局日志配置实例"""
    return _CONFIG

def set_log_hook(hook: Callable[[str, str], None]):
    """设置自定义日志钩子函数"""
    _CONFIG.log_hook = hook

# 兼容旧API的获取与设置函数
def get_verbose() -> bool:
    return _CONFIG.verbose

def set_verbose(new_val: bool):
    _CONFIG.verbose = new_val

def get_silent() -> bool:
    return _CONFIG.silent

def set_silent(new_val: bool):
    _CONFIG.silent = new_val

def get_debug_mode() -> int:
    return _CONFIG.debug_mode

def set_debug_mode(new_val: int):
    _CONFIG.debug_mode = new_val

def set_debug_mode_from_options(options) -> None:
    """从命令行选项设置调试模式"""
    debug_flags = 0
    try:
        if options.debug:
            debug_flags |= 1  # 基础调试标志
    except AttributeError:
        pass
    
    try:
        if options.suspend_start:
            debug_flags |= 2  # 挂起启动标志
    except AttributeError:
        pass
    
    set_debug_mode(debug_flags)

def _format_message(msg: str, level: str, color: Optional[str] = None, bold: bool = False) -> str:
    """格式化日志消息，添加前缀、颜色和样式"""
    prefix = f"{level}: " if level else ""
    
    if _CONFIG.use_colors:
        parts = []
        if color:
            parts.append(color)
        if bold:
            parts.append(COLORS['bold'])
        parts.append(prefix)
        parts.append(msg)
        parts.append(COLORS['reset'])
        return "".join(parts)
    
    return prefix + msg

def _log_message(
    level: str, 
    msg: str, 
    color: Optional[str] = None, 
    bold: bool = False, 
    file=sys.stdout
) -> None:
    """记录消息的核心函数"""
    if _CONFIG.silent and level != "ERROR":
        return  # 在静默模式下抑制非错误信息
    
    # 调用日志钩子（如果有）
    if _CONFIG.log_hook:
        _CONFIG.log_hook(level, msg)
    
    # 格式化并输出消息
    formatted_msg = _format_message(msg, level, color, bold) if level else msg
    print(formatted_msg, file=file)

def print_info_msg(msg: str, forced: bool = False) -> None:
    """打印信息级日志"""
    if forced or _CONFIG.verbose or _CONFIG.debug_mode != 0:
        _log_message("INFO", msg, COLORS['green'] if _CONFIG.use_colors else None, False)

def print_error_msg(msg: str) -> None:
    """打印错误级日志"""
    _log_message("ERROR", msg, COLORS['red'], True, sys.stderr)

def print_warning_msg(msg: str, bold: bool = False) -> None:
    """打印警告级日志"""
    _log_message("WARNING", msg, COLORS['yellow'], bold)

def print_debug_msg(msg: str) -> None:
    """打印调试级日志（仅在调试模式启用时显示）"""
    if _CONFIG.debug_mode != 0:
        _log_message("DEBUG", msg, COLORS['blue'], False)

def print_success_msg(msg: str) -> None:
    """打印成功消息（新函数）"""
    if not _CONFIG.silent:
        prefix = "✅ " if _CONFIG.use_colors else "[SUCCESS] "
        _log_message(None, prefix + msg, COLORS['green'], True)

def print_status(msg: str, status: str = "WORKING") -> None:
    """打印状态消息（新函数）"""
    if not _CONFIG.silent:
        icons = {
            "WORKING": "🔄 ",
            "DONE": "✅ ",
            "WAITING": "⏳ ",
            "ERROR": "❌ ",
            "WARNING": "⚠️ ",
        }
        icon = icons.get(status.upper(), "• ") if _CONFIG.use_colors else "[STATUS] "
        _log_message(None, f"{icon} {msg}")

def print_progress_bar(
    current: int, 
    total: int, 
    prefix: str = "Progress", 
    length: int = 40
) -> None:
    """在终端显示进度条（新函数）"""
    if _CONFIG.silent or total <= 0:
        return
    
    percent = current * 100 // total
    filled = length * current // total
    bar = '█' * filled + '.' * (length - filled)
    
    color = COLORS.get('reset', '')
    if percent < 30:
        color = COLORS['red'] if _CONFIG.use_colors else ""
    elif percent < 70:
        color = COLORS['yellow'] if _CONFIG.use_colors else ""
    else:
        color = COLORS['green'] if _CONFIG.use_colors else ""
    
    # 移动光标到行首并清空行
    sys.stdout.write(f"\r\033[K{prefix} |{color}{bar}{COLORS.get('reset', '')}| {percent}% ({current}/{total})")
    sys.stdout.flush()
    
    # 完成后换行
    if current == total:
        sys.stdout.write("\n")

def get_debug_suspend_enabled() -> bool:
    """检查是否启用了挂起启动调试标志（位1）"""
    return _CONFIG.has_debug_flag(2)  # 0b10

def get_debug_mode_enabled() -> bool:
    """检查是否启用了基础调试标志（位0）"""
    return _CONFIG.has_debug_flag(1)  # 0b01

# === 示例用法 ===
if __name__ == "__main__":
    # 测试日志输出
    set_verbose(True)
    set_debug_mode(3)  # 启用所有调试标志
    
    print_info_msg("系统初始化开始...")
    print_debug_msg("调试信息：加载配置文件")
    print_warning_msg("警告：磁盘空间低于阈值")
    print_error_msg("错误：无法连接到数据库")
    
    # 显示进度条
    for i in range(1, 101):
        print_progress_bar(i, 100)
        import time
        time.sleep(0.02)
    
    print_status("数据验证完成", "DONE")
    print_success_msg("所有操作成功完成")
    
    # 检查调试标志
    if get_debug_suspend_enabled():
        print_debug_msg("DEBUG: 挂起启动功能已启用")
    
    if get_debug_mode_enabled():
        print_debug_msg("DEBUG: 基础调试模式已启用")

