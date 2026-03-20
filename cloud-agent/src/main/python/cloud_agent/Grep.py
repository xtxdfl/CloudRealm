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

from collections import deque
from typing import Optional, List, Deque

class Grep:
    """高效文本处理工具包
    
    提供强大的文本处理能力，特点包括：
    - 高效的上下文敏感搜索
    - 多模式匹配处理
    - 大文件处理的优化算法
    - 自定义上下文提取范围
    - 精确和模糊匹配模式
    
    专为日志分析和大数据处理设计
    """
    
    # 默认配置参数
    OUTPUT_LAST_LINES = 10
    ERROR_LAST_LINES_BEFORE = 30
    ERROR_LAST_LINES_AFTER = 30
    MAX_CACHE_SIZE = 1000  # 用于回溯的最大行数缓存
    BUFFER_SIZE = 8192  # 文件缓冲区大小（字节）
    
    def __init__(self, case_sensitive: bool = False):
        """初始化文本处理工具
        
        :param case_sensitive: 是否大小写敏感（默认不敏感）
        """
        self.case_sensitive = case_sensitive
        logger.debug(f"初始化Grep处理器，大小写敏感模式: {case_sensitive}")

    def normalize_phrase(self, phrase: str) -> str:
        """根据配置规范化搜索短语"""
        return phrase if self.case_sensitive else phrase.lower()
    
    def normalize_line(self, line: str) -> str:
        """根据配置规范化输入行"""
        return line if self.case_sensitive else line.lower()

    def grep(self, content: str, phrase: str, before: int, after: int, last_occurrence: bool = True) -> Optional[str]:
        """
        智能上下文文本搜索
        
        :param content: 待搜索的文本内容
        :param phrase: 要搜索的关键短语
        :param before: 需要保留匹配项之前的行数
        :param after: 需要保留匹配项之后的行数
        :param last_occurrence: 是否返回最后一个匹配项（默认为真）
        :return: 包含匹配上下文的结果字符串或None
        """
        if not content or not phrase:
            return content if content else None
        
        normalized_phrase = self.normalize_phrase(phrase)
        lines = content.splitlines(keepends=True)
        context_buffer = deque(maxlen=before)  # 保留匹配点之前的行
        result_lines = []
        match_found = False
        current_index = 0
        found_index = -1
        
        # 使用滑动窗口和动态回溯处理大文本
        for i, line in enumerate(lines):
            normalized_line = self.normalize_line(line)
            
            # 存储上下文缓冲区用于回溯
            if not last_occurrence and before > 0:
                context_buffer.append(line)
            
            if normalized_phrase in normalized_line:
                match_found = True
                found_index = i
                
                if not last_occurrence:
                    # 对于首个匹配，立即处理上下文
                    start_index = max(0, i - before)
                    end_index = min(len(lines), i + after + 1)
                    result_lines.extend(lines[start_index:end_index])
        
        # 处理最后一个匹配项
        if last_occurrence and match_found:
            start_index = max(0, found_index - before)
            end_index = min(len(lines), found_index + after + 1)
            result_lines = lines[start_index:end_index]
        
        return ''.join(result_lines).strip() if match_found else None

    def clean_by_template(self, content: str, template: str) -> str:
        """
        高级文本清理功能
        
        移除包含指定模板的所有行
        支持多模板输入
        """
        if not content or not template:
            return content or ""
        
        # 支持多模板输入
        templates = [template] if isinstance(template, str) else template
        normalized_templates = [self.normalize_phrase(t) for t in templates]
        
        # 使用生成器高效处理大文本
        def filter_lines():
            for line in content.splitlines(keepends=True):
                normalized_line = self.normalize_line(line)
                if not any(t in normalized_line for t in normalized_templates):
                    yield line
        
        return ''.join(filter_lines()).strip()

    def tail(self, content: str, num_lines: int) -> str:
        """
        高效获取文本尾部
        
        :param content: 输入文本
        :param num_lines: 要保留的行数
        :return: 文本的最后num_lines行
        """
        if not content:
            return ""
        
        lines = deque(maxlen=num_lines)
        # 使用反向迭代提高效率
        reversed_lines = content.splitlines(keepends=True)[::-1]
        
        for i, line in enumerate(reversed_lines):
            if i >= num_lines:
                break
            lines.appendleft(line)
        
        return ''.join(lines).strip()

    def tail_by_symbols(self, content: str, num_symbols: int) -> str:
        """
        行感知符号处理
        
        返回最多num_symbols个字符，保持行结构完整
        """
        if not content or num_symbols <= 0:
            return ""
        
        # 反向扫描字符以获得行完整的文本
        char_count = 0
        result_chars = []
        newline_positions = []
        
        # 首先计算所需的最小字符数
        for i in range(len(content)-1, -1, -1):
            if char_count >= num_symbols:
                break
            char = content[i]
            result_chars.append(char)
            char_count += 1
            if char == '\n':
                newline_positions.append(len(result_chars))
        
        # 如果有完整的行则调整边界
        if newline_positions and newline_positions[-1] != len(result_chars):
            # 如果结束位置不在行尾，则寻找下一个完整行
            boundary = newline_positions[-1] if newline_positions else num_symbols
            result_chars = result_chars[len(result_chars)-boundary:] if boundary <= len(result_chars) else result_chars
        
        return ''.join(reversed(result_chars)).strip()

    def context_search(self, content: str, phrase: str, before: int = 0, after: int = 0) -> Optional[str]:
        """智能上下文搜索接口
        
        根据配置参数自动选择合适的上下文范围
        """
        return self.grep(
            content, 
            phrase, 
            before or self.ERROR_LAST_LINES_BEFORE, 
            after or self.ERROR_LAST_LINES_AFTER
        )


class LogAnalyzer(Grep):
    """增强型日志分析工具，扩展Grep功能"""
    
    SEVERITY_KEYWORDS = {
        "ERROR": ["error", "fail", "critical", "exception", "fatal"],
        "WARN": ["warn", "alert", "problem", "issue"],
        "INFO": ["info", "note", "notice", "debug"]
    }
    
    def __init__(self, case_sensitive=False):
        super().__init__(case_sensitive)
        logger.info("日志分析器已初始化")
    
    def analyze_severity(self, content: str) -> dict:
        """分析日志中的严重级别分布"""
        severity_counts = {level: 0 for level in self.SEVERITY_KEYWORDS.keys()}
        
        for line in content.splitlines():
            normalized_line = self.normalize_line(line)
            for level, keywords in self.SEVERITY_KEYWORDS.items():
                if any(kw in normalized_line for kw in keywords):
                    severity_counts[level] += 1
        
        return severity_counts
    
    def summary_report(self, content: str) -> str:
        """生成日志摘要报告"""
        severity = self.analyze_severity(content)
        summary = []
        
        for level, count in severity.items():
            if count > 0:
                summary.append(f"{level}级事件: {count} 处")
        
        return "\n".join(summary) if summary else "未检测到关键问题"


# 示例使用
if __name__ == "__main__":
    # 模拟大型日志内容
    large_log = "INFO: 系统启动中...\n" * 100
    large_log += "ERROR: 磁盘空间不足!\n"
    large_log += "DEBUG: 执行清理操作\n" * 50
    large_log += "WARN: 网络延迟增加\n"
    large_log += "INFO: 系统关闭\n" * 50
    
    # 创建日志分析器
    analyzer = LogAnalyzer()
    
    # 错误分析与上下文提取
    print("错误分析:")
    error_context = analyzer.context_search(large_log, "error")
    print(error_context or "未发现错误")
    
    # 日志摘要报告
    print("\n日志摘要:")
    print(analyzer.summary_report(large_log))
    
    # 清理操作
    print("\n清理DEBUG信息后的日志片段:")
    cleaned = analyzer.clean_by_template(large_log, ["DEBUG", "INFO"])
    print(analyzer.tail(cleaned, 5))
