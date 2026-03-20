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
from typing import Union, Set, List, Optional, Generator, Callable
from pathlib import Path
from functools import wraps
from time import perf_counter

class StringUtils:
    """高级字符串处理工具集"""
    
    @staticmethod
    def normalize_path(path: str, style: str = 'system') -> str:
        """
        规范化路径字符串的斜杠表示方式
        
        参数:
            path: 原始路径字符串
            style: 可选值 'system' (使用系统默认), 'unix' (使用正斜杠) 或 'windows' (使用反斜杠)
            
        返回:
            规范化后的路径字符串
        """
        # 根据系统确定默认样式
        if style == 'system':
            style = 'windows' if os.name == 'nt' else 'unix'
        
        # 压缩连续的斜杠
        normalized = re.sub(r'[/\\]+', '/' if style == 'unix' else '\\\\', path)
        
        # 确保路径分隔符正确
        if style == 'windows':
            # 确保双反斜杠格式
            normalized = normalized.replace('/', '\\')
            # 保留卷名的冒号
            if ':' in normalized:
                drive, rest = normalized.split(':', 1)
                normalized = f"{drive}:{rest.replace(':', '')}"
        else:
            # 确保正斜杠格式
            normalized = normalized.replace('\\', '/')
        
        return normalized
    
    @staticmethod
    def to_bool(value: Union[str, bool, int, None]) -> bool:
        """
        将各种类型的值解析为布尔值
        
        支持:
            - 字符串: "true", "yes", "on", "y", "t", "1" -> True
            - 字符串: "false", "no", "off", "n", "f", "0" -> False
            - 布尔值: 原样返回
            - 数字: 非零 -> True, 零 -> False
            - None: False
        
        参数:
            value: 要转换的值
            
        返回:
            bool: 转换后的布尔值
            
        异常:
            ValueError: 如果无法转换为布尔值
        """
        if value is None:
            return False
        
        if isinstance(value, bool):
            return value
        
        if isinstance(value, int):
            return value != 0
        
        if not isinstance(value, str):
            raise ValueError(f"无法将类型 {type(value).__name__} 转换为布尔值")
        
        cleaned = value.strip().lower()
        if cleaned in ("true", "yes", "on", "y", "t", "1", "enable", "active"):
            return True
        if cleaned in ("false", "no", "off", "n", "f", "0", "disable", "inactive"):
            return False
        
        raise ValueError(f'无法解释值 "{value}" 为布尔值')
    
    @staticmethod
    def to_int(value: Union[str, int, float, None]) -> Optional[int]:
        """
        将各种类型的值解析为整型
        
        参数:
            value: 要转换的值
            
        返回:
            int: 转换后的整数值，或None（如果输入为None）
            
        异常:
            ValueError: 如果无法转换为整数
        """
        if value is None:
            return None
            
        if isinstance(value, (int, float)):
            return int(value)
            
        if isinstance(value, str):
            cleaned = value.strip()
            # 支持十六进制和二进制格式
            if cleaned.startswith("0x"):
                return int(cleaned, 16)
            if cleaned.startswith("0b"):
                return int(cleaned, 2)
            return int(cleaned)
        
        raise ValueError(f'无法解释值 "{value}" 为整数')
    
    @staticmethod
    def to_float(value: Union[str, int, float, None]) -> Optional[float]:
        """
        将各种类型的值解析为浮点型
        
        参数:
            value: 要转换的值
            
        返回:
            float: 转换后的浮点数值，或None（如果输入为None）
            
        异常:
            ValueError: 如果无法转换为浮点数
        """
        if value is None:
            return None
            
        if isinstance(value, float):
            return value
            
        if isinstance(value, int):
            return float(value)
            
        if isinstance(value, str):
            cleaned = value.strip()
            return float(cleaned)
        
        raise ValueError(f'无法解释值 "{value}" 为浮点数')
    
    @staticmethod
    def chunk_text(
        text: str, 
        chunk_max_size: int, 
        strategy: str = 'line', 
        line_delimiter: str = '\n'
    ) -> List[str]:
        """
        将文本分割成最大尺寸的块，尽可能保持内容逻辑完整性
        
        参数:
            text: 输入文本
            chunk_max_size: 每个块的最大尺寸（字符数）
            strategy: 分割策略 ('line' - 按行分割, 'word' - 按词分割, 'sentence' - 按句子分割)
            line_delimiter: 行分隔符（默认为换行符）
            
        返回:
            字符串列表: 分割后的文本块
        """
        if chunk_max_size <= 0:
            raise ValueError("块尺寸必须大于0")
        
        if not text:
            return ['']
        
        # 选择分割策略
        if strategy == 'word':
            chunks = StringUtils._chunk_by_word(text, chunk_max_size)
        elif strategy == 'sentence':
            chunks = StringUtils._chunk_by_sentence(text, chunk_max_size)
        else:  # 默认按行分割
            chunks = StringUtils._chunk_by_line(text, chunk_max_size, line_delimiter)
        
        return chunks
    
    @staticmethod
    def _chunk_by_line(text: str, chunk_max_size: int, delimiter: str = '\n') -> List[str]:
        """按行分割文本"""
        lines = text.split(delimiter)
        chunks = []
        current_chunk = []
        current_size = 0
        
        for line in lines:
            # 每行的大小（包括分隔符）
            line_size = len(line) + len(delimiter)
            
            # 单行超过最大块大小
            if len(line) > chunk_max_size:
                # 按最大块大小分行
                sub_chunks = [
                    line[i:i+chunk_max_size] 
                    for i in range(0, len(line), chunk_max_size)
                ]
                for sub in sub_chunks:
                    chunks.append(sub)
                # 重置当前块
                current_size = 0
                current_chunk = []
                continue
                
            # 检查是否需要开始新块
            if current_size + line_size > chunk_max_size:
                chunks.append(delimiter.join(current_chunk).rstrip(delimiter))
                current_chunk = [line]
                current_size = line_size
            else:
                current_chunk.append(line)
                current_size += line_size
                
        # 添加最后一个块
        if current_chunk:
            chunks.append(delimiter.join(current_chunk).rstrip(delimiter))
            
        return chunks
    
    @staticmethod
    def _chunk_by_word(text: str, chunk_max_size: int) -> List[str]:
        """按单词分割文本"""
        import textwrap
        # 使用textwrap按词分割
        return textwrap.wrap(text, width=chunk_max_size, break_long_words=True)
    
    @staticmethod
    def _chunk_by_sentence(text: str, chunk_max_size: int) -> List[str]:
        """按句子分割文本"""
        # 使用正则表达式分割句子
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = []
        current_size = 0
        
        for sentence in sentences:
            if not sentence:
                continue
                
            # 句子大小（包括后续添加的空格）
            sentence_size = len(sentence) + 1
            
            # 单个句子超过最大块大小
            if len(sentence) > chunk_max_size:
                # 按行分割句子
                sub_chunks = StringUtils._chunk_by_word(sentence, chunk_max_size)
                chunks.extend(sub_chunks)
                # 重置当前块
                current_size = 0
                current_chunk = []
                continue
                
            # 检查是否需要开始新块
            if current_size + sentence_size > chunk_max_size and current_chunk:
                chunks.append(' '.join(current_chunk))
                current_chunk = [sentence]
                current_size = sentence_size
            else:
                current_chunk.append(sentence)
                current_size += sentence_size
                
        # 添加最后一个块
        if current_chunk:
            chunks.append(' '.join(current_chunk))
            
        return chunks
    
    @staticmethod
    def set_operation(
        a: Optional[str], 
        b: Optional[str], 
        operation: str = 'intersection',
        ignore_case: bool = True,
        sep: str = ',',
        clean_func: Callable[[str], str] = str.strip
    ) -> Set[str]:
        """
        对两个分隔符分隔的字符串集合执行集合操作
        
        参数:
            a: 第一个字符串集合
            b: 第二个字符串集合
            operation: 集合操作类型 ('intersection', 'union', 'difference', 'symmetric_difference')
            ignore_case: 是否忽略大小写
            sep: 集合分隔符
            clean_func: 清理元素的函数
            
        返回:
            操作结果的字符串集合
        """
        # 预处理空值
        a = a or ''
        b = b or ''
        
        # 规范化大小写
        if ignore_case:
            a = a.lower()
            b = b.lower()
        
        # 分割并清理元素
        set_a = {clean_func(item) for item in a.split(sep) if clean_func(item)}
        set_b = {clean_func(item) for item in b.split(sep) if clean_func(item)}
        
        # 执行集合操作
        if operation == 'union':
            result_set = set_a | set_b
        elif operation == 'difference':
            result_set = set_a - set_b
        elif operation == 'symmetric_difference':
            result_set = set_a ^ set_b
        else:  # 默认为交集
            result_set = set_a & set_b
        
        return result_set
    
    @staticmethod
    def compare_sets(
        a: Optional[str], 
        b: Optional[str], 
        ignore_case: bool = True, 
        sep: str = ',',
        ignore_order: bool = True,
        ignore_duplicates: bool = True,
        clean_func: Callable[[str], str] = str.strip
    ) -> int:
        """
        比较两个分隔符分隔的字符串集合是否相等
        
        参数:
            a: 第一个字符串集合
            b: 第二个字符串集合
            ignore_case: 是否忽略大小写
            sep: 集合分隔符
            ignore_order: 是否忽略元素顺序
            ignore_duplicates: 是否忽略重复元素
            clean_func: 清理元素的函数
            
        返回:
            0: 两集合完全相同
            1: a包含b
            2: b包含a
            3: 两集合有交集但互不包含
            4: 无交集
        """
        # 预处理空值
        a = a or ''
        b = b or ''
        
        # 规范化大小写
        if ignore_case:
            a = a.lower()
            b = b.lower()
        
        # 分割并清理元素
        list_a = [clean_func(item) for item in a.split(sep) if clean_func(item)]
        list_b = [clean_func(item) for item in b.split(sep) if clean_func(item)]
        
        # 处理重复项
        if ignore_duplicates:
            set_a = set(list_a)
            set_b = set(list_b)
        else:
            # 需要保留顺序和重复项时使用列表
            set_a = list_a
            set_b = list_b
        
        # 比较集合
        if not ignore_order and not ignore_duplicates:
            # 需要精确匹配顺序和重复项
            if list_a == list_b:
                return 0
        else:
            # 忽略顺序或重复项的情况
            if set_a == set_b:
                return 0
        
        # 判断包含关系
        if ignore_duplicates:
            a_contains_b = set_b.issubset(set_a)
            b_contains_a = set_a.issubset(set_b)
        else:
            # 需要处理重复项的包含关系
            from collections import Counter
            cnt_a = Counter(list_a)
            cnt_b = Counter(list_b)
            
            a_contains_b = all(cnt_a[x] >= cnt_b[x] for x in cnt_b)
            b_contains_a = all(cnt_b[x] >= cnt_a[x] for x in cnt_a)
        
        # 返回比较结果
        if a_contains_b and not b_contains_a:
            return 1
        elif b_contains_a and not a_contains_b:
            return 2
        elif len(set_a if ignore_duplicates else set(list_a)) & set(list_b):
            return 3
        else:
            return 4
    
    @staticmethod
    def timed(method):
        """方法执行时间测量装饰器"""
        @wraps(method)
        def timed_wrapper(*args, **kwargs):
            start_time = perf_counter()
            result = method(*args, **kwargs)
            end_time = perf_counter()
            elapsed = (end_time - start_time) * 1000  # 毫秒
            print(f"{method.__name__} 执行时间: {elapsed:.4f} ms")
            return result
        return timed_wrapper
    
    @staticmethod
    def generate_text_chunks(
        text: str, 
        chunk_size: int = 4096,
        min_chunk_size: int = 1024,
        strategy: str = 'smart'
    ) -> Generator[str, None, None]:
        """
        生成文本块的生成器，智能分割文本
        
        参数:
            text: 输入文本
            chunk_size: 目标块大小（字符数）
            min_chunk_size: 最小块大小（字符数）
            strategy: 分割策略 ('character', 'line', 'smart')
            
        返回:
            文本块生成器
        """
        if chunk_size <= 0:
            raise ValueError("块尺寸必须大于0")
        
        if not text:
            yield ""
            return
        
        # 选择分割策略
        if strategy == 'character':
            yield from StringUtils._generate_character_chunks(text, chunk_size)
        elif strategy == 'line':
            yield from StringUtils._generate_line_chunks(text, chunk_size)
        else:  # smart 分割策略
            yield from StringUtils._generate_smart_chunks(text, chunk_size, min_chunk_size)
    
    @staticmethod
    def _generate_character_chunks(text: str, chunk_size: int) -> Generator[str, None, None]:
        """按固定字符数分割"""
        for i in range(0, len(text), chunk_size):
            yield text[i:i+chunk_size]
    
    @staticmethod
    def _generate_line_chunks(text: str, chunk_size: int) -> Generator[str, None, None]:
        """按行分割，尽可能保持块大小"""
        lines = text.split('\n')
        chunk = []
        current_length = 0
        
        for line in lines:
            if current_length + len(line) + 1 > chunk_size and chunk:
                yield '\n'.join(chunk)
                chunk = []
                current_length = 0
            
            # 如果某一行太大，需要分割
            if len(line) > chunk_size:
                # 分割大行
                for i in range(0, len(line), chunk_size):
                    chunk.append(line[i:i+chunk_size])
                    if len(chunk) >= 10:  # 避免一次添加太多
                        yield '\n'.join(chunk)
                        chunk = []
                        current_length = 0
                current_length += len(line) % chunk_size
            else:
                chunk.append(line)
                current_length += len(line) + 1  # 加上换行符长度
        
        # 处理最后一块
        if chunk:
            yield '\n'.join(chunk)
    
    @staticmethod
    def _generate_smart_chunks(text: str, chunk_size: int, min_chunk_size: int) -> Generator[str, None, None]:
        """
        智能文本分块算法：
          1. 尝试在段落边界分割
          2. 其次是句子边界
          3. 最后是在词语边界
        """
        # 首先尝试按段落分割
        paragraphs = re.split(r'\n\s*\n', text)
        chunk = []
        current_length = 0
        
        for para in paragraphs:
            para_len = len(para)
            
            # 检查添加后是否会超过块大小
            if current_length > 0 and current_length + para_len > chunk_size:
                yield '\n\n'.join(chunk)
                chunk = [para]
                current_length = para_len + 2  # 两个换行符
                continue
                
            # 如果单个段落太大
            if para_len > chunk_size:
                if chunk:  # 先输出已有块
                    yield '\n\n'.join(chunk)
                    chunk = []
                    current_length = 0
                
                # 分割大段落
                if '\n' in para:  # 如果有内嵌换行，优先按行分割
                    for part in StringUtils._generate_line_chunks(para, chunk_size):
                        yield part
                else:  # 否则按句子分割
                    sentences = re.split(r'(?<=[.!?])\s+', para)
                    sent_chunk = []
                    sent_length = 0
                    
                    for sent in sentences:
                        sent_len = len(sent)
                        # 检查是否输出当前句子块
                        if sent_length > 0 and sent_length + sent_len > min_chunk_size:
                            yield ' '.join(sent_chunk)
                            sent_chunk = [sent]
                            sent_length = sent_len + 1  # 空格
                        else:
                            sent_chunk.append(sent)
                            sent_length += sent_len + 1
                    
                    if sent_chunk:
                        yield ' '.join(sent_chunk)
            else:
                # 添加段落到当前块
                chunk.append(para)
                current_length += para_len + 2  # 两个换行符
        
        # 输出最后一块
        if chunk:
            yield '\n\n'.join(chunk)

# =============== 高级用例示例 ===============
def process_large_log_file():
    """处理大型日志文件示例"""
    # 模拟大日志文件
    large_log = "系统启动...\n" * 5000 + "错误: 内存不足\n" * 1000
    
    # 使用智能分块处理
    for chunk in StringUtils.generate_text_chunks(large_log, chunk_size=1024, strategy='smart'):
        # 在实际中，这里可以是发送到日志分析系统或存储到分片文件中
        print(f"处理日志块: {len(chunk)}字符")

def format_complex_path():
    """复杂路径格式化示例"""
    messy_path = "C://///Program\\Files\\\\App\\Logs//debug.log"
    
    # 规范化路径为当前系统格式
    cleaned_path = StringUtils.normalize_path(messy_path)
    print(f"原始路径: {messy_path}")
    print(f"清理后: {cleaned_path}")
    
    # 明确指定格式
    unix_path = StringUtils.normalize_path(messy_path, style='unix')
    windows_path = StringUtils.normalize_path(messy_path, style='windows')
    print(f"Unix格式: {unix_path}")
    print(f"Windows格式: {windows_path}")

def evaluate_set_operations():
    """复杂集合操作示例"""
    users_csv = " Alice, Bob, Charlie, Dave , Eve "
    roles_csv = "admin, moderator, user, bob, alice"
    
    # 找出共同用户
    common = StringUtils.set_operation(users_csv, roles_csv, 
                                       operation='intersection',
                                       clean_func=lambda x: x.capitalize())
    print(f"共同用户: {common}")
    
    # 找出仅出现在用户列表中的项
    only_users = StringUtils.set_operation(users_csv, roles_csv, operation='difference')
    print(f"唯一用户: {only_users}")
    
    # 比较两个权限列表
    config1 = "admin, user, editor"
    config2 = "USER, admin, publisher"
    result = StringUtils.compare_sets(config1, config2, ignore_case=True)
    states = ["完全相同", "A包含B", "B包含A", "有交集但不互含", "无交集"]
    print(f"权限集比较: {states[result]}")

if __name__ == "__main__":
    # 执行演示
    print("--- 路径标准化演示 ---")
    format_complex_path()
    
    print("\n--- 大型文本处理演示 ---")
    process_large_log_file()
    
    print("\n--- 集合运算演示 ---")
    evaluate_set_operations()
