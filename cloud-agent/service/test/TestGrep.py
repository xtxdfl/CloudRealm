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

import os
import re
import sys
import unittest
from unittest.mock import patch, MagicMock
from Grep import Grep

# 测试日志内容
TEST_LOG_CONTENT = """
DEBUG: Starting transaction processing
INFO: User authentication successful
WARN: Deprecated API detected
ERROR: Database connection failed
DEBUG: Attempting to reconnect
INFO: Reconnection successful after 5 seconds
CRITICAL: System overload detected
DEBUG: Performing system cleanup
INFO: Cleanup completed successfully
""".strip().split("\n")

# 错误日志内容
ERROR_LOG_CONTENT = """
DEBUG: Initializing system components
INFO: Loading configuration file
DEBUG: Executing scheduled task 123
ERROR: Security violation detected
WARN: Resource allocation failed
ERROR: Permission denied for user 'admin'
DEBUG: Creating recovery point
CRITICAL: Data corruption detected!
INFO: Alert sent to administrator
""".strip().split("\n")


class GrepTestBase(unittest.TestCase):
    """Grep功能测试基类，提供通用工具方法"""
    
    @classmethod
    def setUpClass(cls):
        # 初始化Grep实例
        cls.grep = Grep()
        
        # 准备测试日志内容
        cls.good_log = os.linesep.join(TEST_LOG_CONTENT)
        cls.error_log = os.linesep.join(ERROR_LOG_CONTENT)
        
        # 创建大型日志文件?0,000行）
        cls.large_log = os.linesep.join([f"Log line {i}" for i in range(1, 10001)])
    
    def setUp(self):
        # 重置环境变量（如果需要）
        pass
    
    def assert_grep_match(self, pattern, content, before=0, after=0, expected=None):
        """辅助断言方法，验证grep结果是否符合预期"""
        result = self.grep.grep(content, pattern, before, after)
        if expected is None:
            self.assertIsNone(result)
        elif isinstance(expected, list):
            self.assertEqual(result, os.linesep.join(expected))
        else:
            self.assertEqual(result, expected)


class GrepFunctionalityTests(GrepTestBase):
    """测试grep核心功能"""
    
    def test_basic_grep_match(self):
        """测试基本匹配功能"""
        result = self.grep.grep(self.good_log, "ERROR")
        expected = [
            "ERROR: Database connection failed"
        ]
        self.assert_grep_match("ERROR", self.good_log, expected=os.linesep.join(expected))
    
    def test_case_sensitivity(self):
        """测试大小写敏感匹?""
        # 默认大小写敏?        result_sensitive = self.grep.grep(self.good_log, "error")
        self.assertIsNone(result_sensitive)
        
        # 使用正则表达式进行不区分大小写匹?        result_insensitive = self.grep.grep(self.good_log, "(?i)error")
        expected = [
            "ERROR: Database connection failed"
        ]
        self.assert_grep_match("(?i)error", self.good_log, expected=os.linesep.join(expected))
    
    def test_context_lines(self):
        """测试上下文行数控?""
        # 前后??        expected = [
            "WARN: Deprecated API detected",
            "ERROR: Database connection failed",
            "DEBUG: Attempting to reconnect",
            "INFO: Reconnection successful after 5 seconds"
        ]
        self.assert_grep_match("ERROR", self.good_log, before=1, after=1, expected=os.linesep.join(expected))
    
    def test_multi_match_context(self):
        """测试多匹配点上下文处?""
        # 在ERROR出现的行周围各加1?        expected = [
            "INFO: Loading configuration file",
            "ERROR: Security violation detected",
            "WARN: Resource allocation failed",
            "WARN: Resource allocation failed",
            "ERROR: Permission denied for user 'admin'",
            "DEBUG: Creating recovery point"
        ]
        self.assert_grep_match("ERROR", self.error_log, before=1, after=1, expected=os.linesep.join(expected))
    
    def test_no_match(self):
        """测试无匹配情?""
        self.assert_grep_match("THIS_PATTERN_DOES_NOT_EXIST", self.good_log, expected=None)
    
    def test_empty_content(self):
        """测试空内容处?""
        self.assert_grep_match("pattern", "", expected=None)


class TailFunctionalityTests(GrepTestBase):
    """测试tail功能"""
    
    def test_tail_basic(self):
        """测试基本tail功能"""
        # 获取最??        result = self.grep.tail(self.good_log, 3)
        expected = [
            "DEBUG: Performing system cleanup",
            "INFO: Cleanup completed successfully"
        ]
        self.assertEqual(result, os.linesep.join(expected))
    
    def test_tail_more_than_lines(self):
        """测试请求行数超过总行?""
        # 请求行数 (20) > 总行?9)
        result = self.grep.tail(self.good_log, 20)
        self.assertEqual(result, self.good_log.strip())
    
    def test_tail_zero_lines(self):
        """测试请求0行的情况"""
        result = self.grep.tail(self.good_log, 0)
        self.assertEqual(result, "")
    
    def test_tail_large_file(self):
        """测试大文件tail功能"""
        # 获取大型日志的最?00?        result = self.grep.tail(self.large_log, 100)
        expected_lines = [f"Log line {i}" for i in range(9901, 10001)]
        self.assertEqual(result, os.linesep.join(expected_lines))
    
    def test_tail_none_content(self):
        """测试None内容处理"""
        result = self.grep.tail(None, 10)
        self.assertEqual(result, "")


class SymbolTailTests(GrepTestBase):
    """测试按字符数tail功能"""
    
    def test_tail_by_symbols_basic(self):
        """测试基本字符tail功能"""
        test_string = "1234567890"
        # 取最?个字?        result = self.grep.tail_by_symbols(test_string, 5)
        self.assertEqual(result, "67890")
    
    def test_tail_by_symbols_exact(self):
        """测试精确字符数匹?""
        test_string = "abcdefghij"
        result = self.grep.tail_by_symbols(test_string, 10)
        self.assertEqual(result, test_string)
    
    def test_tail_by_symbols_overflow(self):
        """测试字符数超过内容长?""
        test_string = "short"
        result = self.grep.tail_by_symbols(test_string, 100)
        self.assertEqual(result, test_string)
    
    def test_tail_by_symbols_empty(self):
        """测试空内容处?""
        result = self.grep.tail_by_symbols("", 10)
        self.assertEqual(result, "")
    
    def test_tail_by_symbols_none(self):
        """测试None内容处理"""
        result = self.grep.tail_by_symbols(None, 10)
        self.assertEqual(result, "")


class CleanByTemplateTests(GrepTestBase):
    """测试按模板清理功?""
    
    def test_clean_debug_lines(self):
        """测试清理debug?""
        # 清理所有DEBUG?        result = self.grep.cleanByTemplate(self.good_log, "DEBUG")
        expected_lines = [
            line for line in TEST_LOG_CONTENT 
            if not line.startswith("DEBUG:")
        ]
        expected = os.linesep.join(expected_lines)
        self.assertEqual(result.strip(), expected)
    
    def test_clean_info_and_debug(self):
        """测试组合模式清理"""
        # 清理所有DEBUG和INFO?        pattern = "DEBUG:|INFO:"
        result = self.grep.cleanByTemplate(self.good_log, pattern)
        expected_lines = [
            line for line in TEST_LOG_CONTENT 
            if not re.match(r"DEBUG:|INFO:", line)
        ]
        expected = os.linesep.join(expected_lines)
        self.assertEqual(result.strip(), expected)
    
    def test_clean_nonexistent_pattern(self):
        """测试清理不存在的模式"""
        # 清理不存在的模式 - 应返回原始内?        result = self.grep.cleanByTemplate(self.good_log, "NONEXISTENT")
        self.assertEqual(result, self.good_log)
    
    def test_clean_all_lines(self):
        """测试清理所有行"""
        # 清理所有行 - 应返回空字符?        result = self.grep.cleanByTemplate(self.good_log, ".*")
        self.assertEqual(result, "")
    
    def test_clean_empty_content(self):
        """测试清理空内?""
        result = self.grep.cleanByTemplate("", "pattern")
        self.assertEqual(result, "")


class EdgeCaseTests(GrepTestBase):
    """测试边界情况和容错处?""
    
    def test_pattern_special_characters(self):
        """测试特殊字符模式匹配"""
        # 包含正则表达式特殊字符的模式
        test_content = "This is a line with [special] characters ^ and $"
        pattern = "\[special\]"
        
        result = self.grep.grep(test_content, pattern)
        self.assertEqual(result, test_content)
        
        # 未转义的特殊字符
        with self.assertRaises(re.error):
            self.grep.grep(test_content, "[special]")
    
    def test_multibyte_characters(self):
        """测试多字节字符处?""
        content = "English: Hello\nJapanese: こんにちは\nRussian: Привет"
        pattern = "Japanese"
        
        # 使用UTF-8编码的多字节字符
        result = self.grep.grep(content, pattern, before=0, after=0)
        self.assertEqual(result, "Japanese: こんにち?)
        
        # 按字符tail
        tail_result = self.grep.tail_by_symbols(content, 15)
        self.assertEqual(tail_result, "ussian: Привет")
    
    def test_large_before_after_context(self):
        """测试超大上下文范?""
        # 前后上下文远大于实际内容
        result = self.grep.grep(self.error_log, "ERROR", before=100, after=100)
        self.assertEqual(result.strip(), self.error_log.strip())
    
    def test_invalid_negative_arguments(self):
        """测试负值参数处?""
        # 负数的before/after参数应被转换?
        with self.assertLogs(level="WARNING") as log:
            result = self.grep.grep(self.good_log, "ERROR", before=-2, after=-5)
        
        # 验证警告信息和结?        self.assertIn("Warning", log.output[0])
        expected = [
            "ERROR: Database connection failed"
        ]
        self.assertEqual(result, "\n".join(expected))
    
    def test_very_large_input(self):
        """测试超大规模输入处理"""
        # 创建10MB大小的日志内?        large_content = ("A" * 1000 + os.linesep) * 10000  # 10,000?* 1000字符
        
        # 执行grep操作
        result = self.grep.grep(large_content, "AAA")
        
        # 验证结果正确性（AAA出现在每行）
        self.assertTrue("AAA" in result)
        self.assertEqual(len(result.split(os.linesep)), 100)
        
        # 测试tail操作
        tail_result = self.grep.tail(large_content, 50)
        self.assertEqual(len(tail_result.split(os.linesep)), 50)


class PerformanceTests(GrepTestBase):
    """测试性能表现"""
    
    @patch("time.perf_counter")
    def test_grep_performance(self, timer_mock):
        """测试grep函数性能"""
        # 设置计时?        timer_mock.side_effect = [0, 0.5]  # 开始时?，结束时?.5
        
        # 执行grep
        result = self.grep.grep(self.large_log, "9999")
        
        # 验证性能指标
        self.assertIn("9999", result)
        self.assertLess(timer_mock.call_count, 100)  # 确保没有过多时间调用
    
    def test_large_file_tail_performance(self):
        """测试大文件tail性能"""
        # 1GB文件模拟
        large_content = ("A" * 1000 + os.linesep) * 1000000  # 1,000,000?        
        # 执行tail操作
        result = self.grep.tail(large_content, 100)
        
        # 验证结果正确?        self.assertEqual(len(result), len("A" * 1000) * 100 + len(os.linesep) * 99)
    
    def test_cleanByTemplate_performance(self):
        """测试cleanByTemplate性能"""
        # 创建100,000行日?        large_log = os.linesep.join([f"Line {i}: DEBUG: This is a debug line" for i in range(100000)])
        
        # 清理DEBUG?        result = self.grep.cleanByTemplate(large_log, "DEBUG")
        
        # 验证所有行都被清理（应返回空字符串?        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
