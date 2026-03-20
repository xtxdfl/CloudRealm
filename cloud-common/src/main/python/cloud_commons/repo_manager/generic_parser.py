#!/usr/bin/env python3
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

import re
from abc import ABC, abstractmethod
from typing import Any, Dict, Generator, Iterable, List, Optional, Tuple, Union

# 预编译高效正则表达式
ANSI_ESCAPE = re.compile(r"""
    \x1B          # ESC 字符
    \[            # [
    [0-?]{0,2}    # 可选参数
    [ -/]*        # 可选参数
    [@-~]         # 字符范围
""", re.VERBOSE)

# 控制字符处理映射表
CONTROL_CHAR_MAP = {
    0: None,    1: None,    2: None,    3: None,    4: None, 
    5: None,    6: None,    7: None, # '\a' 铃声
    8: None,    # '\b' 退格
    9: None,    # '\t' 水平制表符 - 保留
    10: None,   # '\n' 换行 - 保留
    11: None,   # '\v' 垂直制表符
    12: None,   # '\f' 换页
    13: None,   # '\r' 回车 - 保留
    14: None,    15: None,    16: None,    17: None,    18: None, 
    19: None,    20: None,    21: None,    22: None,    23: None, 
    24: None,    25: None,    26: None,    27: None,    28: None, 
    29: None,    30: None,    31: None
}


class GenericParser(ABC):
    """
    高级解析器基础组件
    - 自动输出清理
    - 流处理优化
    - 增强错误恢复
    - 统一日志接口
    """
    
    # 静态配置参数
    STRIP_CONTROL_CHARS = True    # 是否移除控制字符
    MAX_LINE_LENGTH = 8192        # 最大行长度
    VALID_ENCODINGS = ['utf-8', 'latin-1', 'ascii']  # 支持编码
    
    @classmethod
    def clean_line(
        cls,
        line: Union[bytes, str],
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        高级输出清理引擎
        1. 移除ANSI转义代码
        2. 处理多种编码
        3. 清除控制字符
        4. 智能截断
        
        :param line: 输入行 (bytes或str)
        :param context: 处理上下文
        :return: 清理后的字符串
        """
        # 字节解码
        if isinstance(line, bytes):
            encoding = None
            
            # 尝试检测正确编码
            for enc in cls.VALID_ENCODINGS:
                try:
                    decoded = line.decode(enc)
                    encoding = enc
                    break
                except UnicodeDecodeError:
                    continue
                    
            # 回退使用错误恢复解码
            if not encoding:
                decoded = line.decode('utf-8', errors='replace')
            line = decoded
        
        # ANSI转义序列移除
        cleaned = ANSI_ESCAPE.sub('', line)
        
        # 控制字符处理
        if cls.STRIP_CONTROL_CHARS:
            cleaned = ''.join(
                c for c in cleaned 
                if ord(c) > 31 or ord(c) in (9, 10, 13)  # 保留制表、换行、回车
            )
        
        # 长度截断防止DoS攻击
        if len(cleaned) > cls.MAX_LINE_LENGTH:
            # 智能截断: 查找最近的空格
            end_pos = cls.MAX_LINE_LENGTH
            if ' ' in cleaned[cls.MAX_LINE_LENGTH-50:cls.MAX_LINE_LENGTH]:
                end_pos = cleaned.rfind(' ', 0, cls.MAX_LINE_LENGTH)
            if end_pos <= 0:
                end_pos = cls.MAX_LINE_LENGTH
                
            cleaned = cleaned[:end_pos] + ' [TRUNCATED]'
        
        return cleaned

    @staticmethod
    @abstractmethod
    def config_reader(
        stream: Iterable[str],
        context: Optional[Dict[str, Any]] = None
    ) -> Generator[Tuple[str, Any], None, None]:
        """
        配置读取器抽象方法
        :param stream: 文本输入流
        :param context: 解析上下文
        :return: (键, 值) 生成器
        """
        raise NotImplementedError("Subclasses must implement this method")

    @staticmethod
    @abstractmethod
    def packages_reader(
        stream: Iterable[str],
        context: Optional[Dict[str, Any]] = None
    ) -> Generator[Union[Tuple[str, str, str], Dict[str, Any]], None, None]:
        """
        包信息读取器抽象方法
        :param stream: 文本输入流
        :param context: 解析上下文
        :return: 包信息生成器
        """
        raise NotImplementedError("Subclasses must implement this method")

    @staticmethod
    @abstractmethod
    def packages_installed_reader(
        stream: Iterable[str],
        context: Optional[Dict[str, Any]] = None
    ) -> Generator[Tuple[str, str], None, None]:
        """
        已安装包读取器抽象方法
        :param stream: 文本输入流
        :param context: 解析上下文
        :return: (包名, 版本) 生成器
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    @classmethod
    def _parse_error_handler(
        cls, 
        error: Exception, 
        line: str, 
        line_no: int, 
        context: Dict[str, Any]
    ) -> None:
        """解析错误处理框架"""
        # 错误上下文增强
        context.setdefault('errors', []).append({
            'line_number': line_no,
            'line_content': line[:200] + '...' if len(line) > 200 else line,
            'error_type': type(error).__name__,
            'error_msg': str(error)
        })
        
        # 错误阈值处理
        max_errors = context.get('max_errors', 10)
        if len(context['errors']) > max_errors:
            raise RuntimeError(
                f"Too many parsing errors ({max_errors+1} reached). Terminating."
            ) from error
        
        # 错误重试策略
        retry_attempt = context.get(f'retry_{type(error).__name__}', 0)
        if retry_attempt < 3:
            context[f'retry_{type(error).__name__}'] = retry_attempt + 1
            # 这里可以添加重试逻辑
        else:
            # 无法恢复的错误处理
            cls._log_error(
                f"Unrecoverable parser error at line {line_no}: {str(error)}", 
                context
            )
    
    @classmethod
    def _log_error(cls, msg: str, context: Dict[str, Any]) -> None:
        """增强的错误日志记录"""
        # 集成到现有日志系统
        if context.get('logger'):
            context['logger'].error(msg)
        else:
            # 简单错误输出
            print(f"[ERROR] {msg}")
    
    @classmethod
    def _log_warning(cls, msg: str, context: Dict[str, Any]) -> None:
        """增强的警告日志记录"""
        # 集成到现有日志系统
        if context.get('logger'):
            context['logger'].warning(msg)
        elif context.get('log_level', 0) >= 1:
            print(f"[WARN] {msg}")
    
    @classmethod
    def streaming_parser(
        cls,
        stream: Iterable[Union[bytes, str]],
        parser_type: str,
        context: Optional[Dict[str, Any]] = None,
        chunk_size: int = 1024,
        max_lines: int = 1000000
    ) -> Generator[Any, None, None]:
        """
        高级流式解析引擎 - 处理大型输入
        :param stream: 原始输入流（字节或字符串）
        :param parser_type: 解析器类型 ('config', 'packages', 'installed')
        :param context: 解析上下文
        :param chunk_size: 缓冲区块大小
        :param max_lines: 最大处理行数
        :return: 解析结果生成器
        """
        context = context or {}
        parser_map = {
            'config': cls.config_reader,
            'packages': cls.packages_reader,
            'installed': cls.packages_installed_reader
        }
        
        if parser_type not in parser_map:
            raise ValueError(f"Invalid parser type: {parser_type}")
        
        parser = parser_map[parser_type]
        buffer = ""
        line_count = 0
        chunk_counter = 0
        
        for item in stream:
            # 字节流处理
            if isinstance(item, bytes):
                chunk_counter += 1
                try:
                    # 性能优化: 大块解码
                    buffer += item.decode(
                        'utf-8', 
                        errors='replace' if context.get('strict_encoding') else 'ignore'
                    )
                except UnicodeDecodeError as ude:
                    cls._log_error(f"Unicode decode error: {str(ude)}", context)
                    continue
            
            # 文本流处理
            else:
                buffer += item
                
                # 防止内存消耗失控的智能缓冲
                while '\n' in buffer and len(buffer) > chunk_size * 100:
                    cls._parse_chunk(parser, buffer, context, max_lines)
                    buffer = buffer[buffer.find('\n') + 1:]
        
        # 处理剩余缓冲区内容
        if buffer:
            yield from cls._parse_chunk(parser, buffer, context, max_lines)
    
    @classmethod
    def _parse_chunk(
        cls,
        parser: callable,
        text: str,
        context: Dict[str, Any],
        max_lines: int
    ) -> Generator[Any, None, None]:
        """
        智能区块解析器
        - 逐行处理
        - 错误隔离
        - 性能监控
        """
        lines = text.splitlines()
        processed = 0
        
        for line_no, raw_line in enumerate(lines):
            if processed >= max_lines:
                cls._log_warning(
                    f"Reached maximum line limit ({max_lines}). Truncating output.", 
                    context
                )
                return
            
            try:
                # 高级行清理
                cleaned_line = cls.clean_line(raw_line, context)
                
                # 上下文感知行跳过
                if cls._should_skip_line(cleaned_line, context):
                    continue
                    
                # 调用具体解析器
                parsed_items = parser([cleaned_line], context)
                
                # 返回生成器结果
                if isinstance(parsed_items, Generator):
                    for item in parsed_items:
                        yield item
                elif parsed_items:
                    yield from parsed_items
                    
            except Exception as e:
                cls._parse_error_handler(e, raw_line, line_no, context)
                continue
            
            finally:
                processed += 1
    
    @classmethod
    def _should_skip_line(
        cls, 
        line: str, 
        context: Dict[str, Any]
    ) -> bool:
        """
        智能行跳过机制
        - 空行检测
        - 注释行检测
        - 模式排除
        """
        # 空行跳过
        if not line.strip():
            return True
            
        # 注释行跳过
        if context.get('ignore_comments', True):
            comment_chars = context.get('comment_chars', ['#', ';'])
            if any(line.strip().startswith(c) for c in comment_chars):
                return True
        
        # 模式排除
        exclude_patterns = context.get('exclude_patterns', [])
        for pattern in exclude_patterns:
            if re.search(pattern, line):
                return True
        
        return False
    
    @classmethod
    def profile_parser(
        cls,
        input_data: Union[str, List[str]],
        parser_type: str,
        context: Optional[Dict[str, Any]] = None,
        iterations: int = 100
    ) -> Dict[str, Union[float, List[Dict]]]:
        """
        解析器性能分析工具
        :param input_data: 测试数据集
        :param parser_type: 解析器类型
        :param context: 运行上下文
        :param iterations: 测试迭代次数
        :return: 性能指标
        """
        # 性能分析实现
        import time
        import sys
        import memory_profiler
        from collections import defaultdict
        
        context = context or {}
        results = defaultdict(list)
        
        # 准备输入数据
        if isinstance(input_data, str):
            data = input_data.splitlines()
        else:
            data = input_data
        
        # 获取解析器函数
        parser_map = {
            'config': cls.config_reader,
            'packages': cls.packages_reader,
            'installed': cls.packages_installed_reader
        }
        
        if parser_type not in parser_map:
            raise ValueError(f"Invalid parser type: {parser_type}")
        
        parser = parser_map[parser_type]
        
        # 运行性能测试
        baseline_memory = memory_profiler.memory_usage()[0]
        
        for i in range(iterations):
            # 内存分析
            start_mem = memory_profiler.memory_usage()[0]
            mem_prof = memory_profiler.memory_usage(
                proc=(parser, (data, context), {}),
                max_iterations=1
            )
            end_mem = max(mem_prof) if mem_prof else start_mem
            mem_delta = end_mem - baseline_memory
            
            # 时间分析
            start_time = time.perf_counter()
            count = 0
            for _ in parser(data, context):
                count += 1
            elapsed = time.perf_counter() - start_time
            
            # 保存结果
            results['iterations'].append({
                'number': i,
                'time': elapsed,
                'memory': mem_delta,
                'items': count,
                'throughput': count / elapsed if elapsed > 0 else float('inf')
            })
        
        # 计算汇总统计
        if iterations > 0:
            avg_time = sum(r['time'] for r in results['iterations']) / iterations
            avg_mem = sum(r['memory'] for r in results['iterations']) / iterations
            avg_items = sum(r['items'] for r in results['iterations']) / iterations
            avg_tput = sum(r['throughput'] for r in results['iterations']) / iterations
            
            results['summary'] = {
                'avg_time': avg_time,
                'avg_memory': avg_mem,
                'avg_items': avg_items,
                'avg_throughput': avg_tput,
                'iterations': iterations,
                'input_size': len(data)
            }
        
        return results
