#!/usr/bin/env python3
"""
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASFT licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Advanced Log Viewer Utility
"""

import os
import re
import logging
from contextlib import ExitStack
from resource_management.core.logger import StructuredLogger
from resource_management.core.resources.system import Execute
from resource_management.libraries.functions.format import format
from typing import Optional, List, Union, Pattern

# 初始化结构化日志记录器
logger = StructuredLogger(__name__)

# 配置常量
DEFAULT_LINES_COUNT = 40
MAX_LOG_FILES = 50
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB

def inspect_logs(
    log_dir: str,
    log_owner: str,
    *,
    lines_count: int = DEFAULT_LINES_COUNT,
    file_pattern: Union[str, List[str], Pattern] = "*",
    context_lines: int = 0,
    grep_pattern: Optional[str] = None,
    include_filters: Optional[List[str]] = None,
    exclude_filters: Optional[List[str]] = None,
    time_range: Optional[str] = None,
    compressed_files: bool = False,
    traceback_only: bool = False,
    max_depth: int = 1,
    output_mode: str = "text"
) -> None:
    """
    在异常处理期间检查和分析日志文件
    
    此功能在服务启动/停止失败时提供智能日志查看：
    1. 支持多种日志文件匹配模式
    2. 提供灵活的日志过滤选项
    3. 包含安全限制和日志轮转处理
    4. 支持结构化输出格式
    
    :param log_dir: 日志目录路径
    :param log_owner: 日志文件属主用户
    :param lines_count: 每文件显示行数 (默认40)
    :param file_pattern: 文件名匹配模式 (字符串、列表或正则)
    :param context_lines: 关键词匹配上下文行数 (默认0)
    :param grep_pattern: 内容搜索模式 (正则表达式)
    :param include_filters: 文件包含过滤列表
    :param exclude_filters: 文件排除过滤列表
    :param time_range: 时间范围过滤 (例如: "5m", "1h", "2023-01-01")
    :param compressed_files: 是否处理压缩文件 (默认False)
    :param traceback_only: 是否仅显示traceback (默认False)
    :param max_depth: 目录搜索深度 (默认1 - 只当前目录)
    :param output_mode: 输出格式 ("text", "json", "summary")
    
    使用示例:
        # 基本使用
        inspect_logs("/var/log/hdfs", "hdfs", lines_count=50)
        
        # 高级诊断
        inspect_logs("/var/log/yarn", "yarn", 
                    file_pattern="yarn-*.log",
                    grep_pattern="ERROR|CRITICAL",
                    context_lines=3,
                    time_range="10m",
                    output_mode="summary")
    """
    # 验证输入参数
    lines_count = validate_positive(lines_count, DEFAULT_LINES_COUNT)
    
    # 创建安全访问令牌
    token = create_log_session_token(log_dir, log_owner)
    
    # 构建日志查看命令
    cmd = construct_log_view_command(
        log_dir=log_dir,
        file_pattern=file_pattern,
        lines_count=lines_count,
        context_lines=context_lines,
        grep_pattern=grep_pattern,
        include_filters=include_filters,
        exclude_filters=exclude_filters,
        time_range=time_range,
        compressed_files=compressed_files,
        traceback_only=traceback_only,
        max_depth=max_depth,
        output_mode=output_mode
    )
    
    # 执行日志查看并保存结果
    output_dir = None
    with secure_execution_context(log_owner, token):
        try:
            if output_mode == "structured":
                output_dir = manage_output_storage()
                cmd += f" > {os.path.join(output_dir, 'log_results.json')}"
            
            Execute(
                command=cmd,
                logoutput=True,
                timeout=120,
                tries=1,
                user=log_owner,
                environment={"LOG_TOKEN": token}
            )
            
            # 对于结构化输出，执行额外处理
            if output_dir:
                process_structured_output(output_dir)
        except Exception as ex:
            logger.error("日志查看操作失败", 
                         error=str(ex),
                         command=cmd,
                         log_dir=log_dir)
        finally:
            cleanup_resources(token)

def construct_log_view_command(
    log_dir: str,
    file_pattern: Union[str, List[str], Pattern],
    lines_count: int,
    context_lines: int,
    grep_pattern: Optional[str],
    include_filters: Optional[List[str]],
    exclude_filters: Optional[List[str]],
    time_range: Optional[str],
    compressed_files: bool,
    traceback_only: bool,
    max_depth: int,
    output_mode: str
) -> str:
    """
    构建安全的日志查看命令
    
    返回结果示例:
        "log_viewer --path /var/log/hdfs --pattern '*hdfs*.log' --lines 50 --grep ERROR --json"
    """
    # 基本命令结构
    cmd_chain = []
    
    # 文件查找部分
    find_cmd = f"find {shell_quote(log_dir)} -maxdepth {max_depth} -type f"
    
    # 处理文件名模式
    if isinstance(file_pattern, str):
        name_filters = [escape_log_pattern(file_pattern)]
    elif isinstance(file_pattern, list):
        name_filters = [f"-name {escape_log_pattern(p)}" for p in file_pattern]
    else:
        name_filters = ["-regex", file_pattern.pattern]
    
    for pattern in name_filters:
        if pattern.startswith("-name"):
            find_cmd += f" {pattern}"
        else:
            find_cmd += f" {pattern}"
    
    # 添加时间过滤
    if time_range:
        time_filter = convert_time_range_to_find(time_range)
        find_cmd += f" {time_filter}"
    
    # 处理包含/排除过滤器
    if include_filters:
        find_cmd += " " + " ".join([f"-path '{f}'" for f in include_filters])
    if exclude_filters:
        find_cmd += " " + " ".join([f"-not -path '{f}'" for f in exclude_filters])
    
    # 文件数量限制和安全检查
    find_cmd += f" | head -n {MAX_LOG_FILES}"
    cmd_chain.append(find_cmd)
    
    # 日志处理部分
    processor = "log_processor"
    if grep_pattern:
        processor += f" --grep {shell_quote(grep_pattern)}"
    
    if context_lines > 0:
        processor += f" --context {context_lines}"
    
    if lines_count > 0:
        processor += f" --lines {lines_count}"
    
    if traceback_only:
        processor += " --traceback-only"
    
    if compressed_files:
        processor += " --support-compressed"
    
    if output_mode == "json":
        processor += " --json"
    
    cmd_chain.append(f'xargs -I {{}} sh -c "{processor} --file \'\\{\\}\\'"')
    
    return " | ".join(cmd_chain)

def validate_positive(value: int, default: int) -> int:
    """确保数值为有效正整数"""
    if not isinstance(value, int) or value <= 0:
        logger.warning(f"无效数值 '{value}'，使用默认值 {default}")
        return default
    return min(value, 1000)  # 限制最大行数

def create_log_session_token(log_dir: str, owner: str) -> str:
    """为日志访问创建唯一安全令牌"""
    import hashlib, time, random
    token_data = f"{log_dir}:{owner}:{time.time()}:{random.random()}"
    token = hashlib.sha256(token_data.encode("utf-8")).hexdigest()[:16]
    logger.info(f"创建日志访问令牌", token=token, log_dir=log_dir)
    return token

def shell_quote(value: str) -> str:
    """安全转义shell命令中的字符串"""
    from shlex import quote
    return quote(value)

def escape_log_pattern(pattern: str) -> str:
    """转义日志模式中的特殊字符"""
    # 允许通配符，但转义其他特殊字符
    pattern = pattern.replace('[', '[[]').replace(']', '[]]')
    pattern = pattern.replace('(', '[.]').replace(')', '[)]')
    return pattern

def convert_time_range_to_find(time_range: str) -> str:
    """
    将人类可读时间范围转换为find命令选项
    
    支持格式:
      "5m"     -> 最后5分钟
      "2h"     -> 最后2小时
      "24h"    -> 最后24小时
      "2023-01-01" -> 特定日期
    """
    if time_range.endswith('m'):
        minutes = int(time_range[:-1])
        return f"-mmin -{minutes}"
    elif time_range.endswith('h'):
        hours = int(time_range[:-1])
        return f"-mmin -{hours * 60}"
    elif re.match(r"\d{4}-\d{2}-\d{2}", time_range):
        return f"-newermt '{time_range} 00:00:00' -not -newermt '{time_range} 23:59:59'"
    else:
        logger.warning(f"不支持的时间范围格式: {time_range}")
        return ""

def manage_output_storage() -> str:
    """为结构化日志输出创建临时存储目录"""
    from tempfile import mkdtemp
    output_dir = mkdtemp(prefix="logview_")
    os.chmod(output_dir, 0o700)
    return output_dir

def secure_execution_context(user: str, token: str):
    """为日志查看创建安全执行环境"""
    return ExecutionContextManager(user, token)

class ExecutionContextManager:
    """资源管理上下文用于日志安全访问"""
    def __init__(self, user: str, token: str):
        self.user = user
        self.token = token
        
    def __enter__(self):
        # 创建临时凭证文件
        with open(f"/tmp/log_token_{self.token}", "w") as token_file:
            token_file.write(self.token)
        os.chown(token_file.name, os.getuid(), os.getgid())
        return self
        
    def __exit__(self, exc_type, exc_value, traceback):
        # 清理凭证文件
        if os.path.exists(f"/tmp/log_token_{self.token}"):
            os.unlink(f"/tmp/log_token_{self.token}")

def process_structured_output(output_dir: str):
    """处理结构化日志输出"""
    result_file = os.path.join(output_dir, "log_results.json")
    if not os.path.exists(result_file):
        return
    
    # 分析日志结果
    from collections import defaultdict
    error_patterns = {
        'critical': r'CRITICAL|FATAL|EMERGENCY',
        'error': r'ERROR|ERR|FAILED',
        'warning': r'WARNING|WARN',
        'exception': r'Traceback|Exception|Caused by'
    }
    
    stats = defaultdict(int)
    with open(result_file) as f:
        import json
        log_data = json.load(f)
    
    # 扫描错误模式
    for entry in log_data.get('entries', []):
        content = entry.get('content', '').lower()
        for category, pattern in error_patterns.items():
            if re.search(pattern, content, re.IGNORECASE):
                stats[category] += 1
    
    # 生成诊断报告
    report = {
        "total_entries": len(log_data.get('entries', [])),
        "error_stats": dict(stats),
        "top_errors": extract_top_messages(log_data, error_patterns['error'], 5)
    }
    
    logger.info("日志诊断报告", 
                total_files=log_data.get('file_count', 0),
                report=report)

def extract_top_messages(log_data: dict, pattern: str, top_n: int) -> list:
    """提取最常见的错误消息"""
    from collections import Counter
    messages = Counter()
    
    for entry in log_data.get('entries', []):
        if "content" in entry and re.search(pattern, entry["content"], re.IGNORECASE):
            cleaned = re.sub(r'\[.*?\]|\d{4}-\d{2}-\d{2}', '', entry["content"]).strip()
            if cleaned:
                messages[cleaned] += 1
    
    return messages.most_common(top_n)

def cleanup_resources(token: str):
    """清理日志检查资源"""
    # 删除临时令牌文件（上下文管理器已处理）
    # 可扩展清理其他资源

# ------------------- 使用场景示例 -------------------
if __name__ == "__main__":
    # 基本使用场景 - 显示最近日志
    inspect_logs("/var/log/hdfs", "hdfs")
    
    # 错误诊断场景 - 搜索特定错误
    inspect_logs("/var/log/yarn", "yarn", 
                file_pattern="yarn-resourcemanager-*.log",
                grep_pattern="ERROR|CRITICAL",
                context_lines=5,
                lines_count=100)
    
    # 时间过滤场景 - 检查最近10分钟的日志
    inspect_logs("/var/log/kafka", "kafka",
                time_range="10m",
                output_mode="summary")
    
    # 高级诊断 - 结构化JSON输出
    inspect_logs("/var/log/zookeeper", "zookeeper",
                traceback_only=True,
                compressed_files=True,
                output_mode="json")
