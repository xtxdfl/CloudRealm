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
import sys
import io
import zipfile
import tempfile
import unittest
import hashlib
import logging
import configparser
from unittest.mock import MagicMock, patch, mock_open
import shutil

# 禁用标准输出重定?DISABLE_STDOUT_PATCH = True

# SUT (System Under Test)
from FileCache import FileCache, CachingException
from cloudConfig import cloudConfig

class FileCacheTestBase(unittest.TestCase):
    """文件缓存系统测试基类，提供通用工具方法"""
    
    def setUp(self):
        """创建测试环境"""
        # 禁用标准输出重定向（可选）
        if not DISABLE_STDOUT_PATCH:
            self.stdout_patch = patch('sys.stdout', new_callable=io.StringIO)
            self.stdout_patch.start()
        
        # 创建临时缓存目录
        self.cache_dir = tempfile.mkdtemp(prefix="cloud_cache_test_")
        
        # 创建基础配置文件
        self.config = configparser.ConfigParser()
        self._init_test_config()
        
        # 初始化文件缓存实?        self.file_cache = FileCache(self.config)
        
        # 创建测试资源
        self._create_test_archive()
    
    def tearDown(self):
        """清理测试环境"""
        # 恢复标准输出
        if not DISABLE_STDOUT_PATCH and hasattr(self, 'stdout_patch'):
            self.stdout_patch.stop()
        
        # 移除临时目录
        shutil.rmtree(self.cache_dir, ignore_errors=True)
        if os.path.exists(self.test_archive_path):
            os.remove(self.test_archive_path)
    
    def _init_test_config(self):
        """初始化测试配?""
        self.config['agent'] = {
            'prefix': self.cache_dir,
            'cache_dir': os.path.join(self.cache_dir, "agent_cache"),
            'tolerate_download_failures': 'true'
        }
        self.config[cloudConfig.cloud_PROPERTIES_CATEGORY] = {
            FileCache.ENABLE_AUTO_AGENT_CACHE_UPDATE_KEY: 'true'
        }
    
    def _create_test_archive(self):
        """创建测试用的ZIP压缩?""
        self.test_archive_path = os.path.join(self.cache_dir, "test_archive.zip")
        self.test_archive_content = {
            "file1.txt": "This is file 1 content",
            "subdir/file2.txt": "This is file 2 content"
        }
        
        with zipfile.ZipFile(self.test_archive_path, 'w') as archive:
            for path, content in self.test_archive_content.items():
                archive.writestr(path, content)
        
        # 计算哈希?        with open(self.test_archive_path, 'rb') as f:
            self.test_archive_hash = hashlib.md5(f.read()).hexdigest()
    
    def _create_cache_directory(self, path, content="test"):
        """在缓存中创建目录结构"""
        full_path = os.path.join(self.config['agent']['cache_dir'], path)
        os.makedirs(full_path, exist_ok=True)
        
        # 创建哈希文件
        hash_file = os.path.join(full_path, FileCache.HASH_SUM_FILENAME)
        with open(hash_file, 'w') as f:
            f.write(content)


class ConfigurationTests(FileCacheTestBase):
    """测试文件缓存配置处理功能"""
    
    def test_config_validation(self):
        """测试配置参数的解析和验证"""
        # 验证前缀路径
        self.assertEqual(self.file_cache.config['agent']['prefix'], self.cache_dir)
        
        # 验证缓存目录
        expected_cache_dir = os.path.join(self.cache_dir, "agent_cache")
        self.assertEqual(self.file_cache.config['agent']['cache_dir'], expected_cache_dir)
        self.assertTrue(os.path.exists(expected_cache_dir))
        
        # 验证容错设置
        self.assertEqual(self.file_cache.config['agent']['tolerate_download_failures'], 'true')
        
        # 验证自动更新设置
        self.assertEqual(
            self.file_cache.config[cloudConfig.cloud_PROPERTIES_CATEGORY].get(
                FileCache.ENABLE_AUTO_AGENT_CACHE_UPDATE_KEY),
            'true'
        )
    
    def test_config_update_tolerance(self):
        """测试缓存更新容错配置的影?""
        # 禁用容错
        self.config.set('agent', 'tolerate_download_failures', 'false')
        cache = FileCache(self.config)
        
        with patch.object(FileCache, 'fetch_url', side_effect=CachingException):
            with self.assertRaises(CachingException):
                cache.provide_directory("test_base", "update_test", "http://server")
        
        # 启用容错
        self.config.set('agent', 'tolerate_download_failures', 'true')
        cache = FileCache(self.config)
        
        with patch.object(FileCache, 'fetch_url', side_effect=CachingException):
            # 不应该抛出异?            try:
                result = cache.provide_directory("test_base", "update_test", "http://server")
                self.assertTrue(os.path.isdir(result))
            except CachingException:
                self.fail("CachingException should be handled when tolerance is enabled")
    
    def test_cache_update_option(self):
        """测试缓存更新开关配置的影响"""
        # 禁用自动更新
        self.config.set(cloudConfig.cloud_PROPERTIES_CATEGORY,
                      FileCache.ENABLE_AUTO_AGENT_CACHE_UPDATE_KEY, 'false')
        cache = FileCache(self.config)
        
        # 尝试提供目录 - 不应进行更新
        with patch.object(FileCache, 'fetch_url') as fetch_mock:
            result = cache.provide_directory("test_base", "update_test", "http://server")
            self.assertFalse(fetch_mock.called)


class DirectoryProvisionTests(FileCacheTestBase):
    """测试目录提供功能"""
    
    def test_service_directory_provision(self):
        """测试服务目录的提供逻辑"""
        command = {
            "commandParams": {
                "service_package_folder": "stacks/HDP/2.1.1/services/ZOOKEEPER/package"
            },
            "cloudLevelParams": {"jdk_location": "https://repo.example.com"}
        }
        
        # 提供目录
        result = self.file_cache.get_service_base_dir(command)
        
        # 验证路径结构
        expected_path = os.path.join(
            self.config['agent']['cache_dir'],
            "stacks", "HDP", "2.1.1", "services", "ZOOKEEPER", "package"
        )
        self.assertEqual(result, expected_path)
    
    def test_hook_directory_provision(self):
        """测试钩子目录的提供逻辑"""
        # 测试有效命令
        valid_command = {
            "clusterLevelParams": {"hooks_folder": "stack-hooks/CUSTOM_HOOK"},
            "cloudLevelParams": {"jdk_location": "https://repo.example.com"}
        }
        
        result = self.file_cache.get_hook_base_dir(valid_command)
        expected_path = os.path.join(
            self.config['agent']['cache_dir'], "stack-hooks/CUSTOM_HOOK"
        )
        self.assertEqual(result, expected_path)
        
        # 测试无效命令
        invalid_command = {
            "clusterLevelParams": {},
            "cloudLevelParams": {"jdk_location": "https://repo.example.com"}
        }
        
        result = self.file_cache.get_hook_base_dir(invalid_command)
        self.assertIsNone(result)
    
    def test_custom_resources_handling(self):
        """测试自定义资源目录的提供逻辑"""
        command = {
            "commandParams": {"custom_folder": "dashboards"},
            "cloudLevelParams": {"jdk_location": "https://repo.example.com"}
        }
        
        result = self.file_cache.get_custom_resources_subdir(command)
        expected_path = os.path.join(
            self.config['agent']['cache_dir'], "dashboards"
        )
        self.assertEqual(result, expected_path)


class CacheOperationTests(FileCacheTestBase):
    """测试缓存核心操作功能"""
    
    @patch.object(FileCache, 'read_hash_sum')
    @patch.object(FileCache, 'fetch_url')
    def test_cache_directory_provision(self, fetch_mock, read_hash_mock):
        """测试按需提供缓存目录的功?""
        # 模拟远程哈希变化
        read_hash_mock.return_value = "old_hash"
        fetch_mock.return_value = io.BytesIO(b"new_content")
        
        # 计算新哈?        fetch_mock.return_value.seek(0)
        new_hash = hashlib.md5(fetch_mock.return_value.getvalue()).hexdigest()
        
        # 调用提供目录方法
        target_path = self.file_cache.provide_directory(
            "test_base", "test_dir", "https://repo.example.com"
        )
        full_path = os.path.join(self.config['agent']['cache_dir'], "test_base", "test_dir")
        
        # 验证路径正确
        self.assertEqual(target_path, full_path)
        
        # 验证方法调用
        self.assertEqual(fetch_mock.call_count, 2)  # 获取哈希 + 获取内容
        self.assertTrue(os.path.isdir(full_path))
        self.assertEqual(
            self.file_cache.read_hash_sum(full_path), 
            new_hash
        )
    
    @patch.object(FileCache, 'unpack_archive')
    @patch.object(FileCache, 'fetch_url')
    def test_cache_directory_up_to_date(self, fetch_mock, unpack_mock):
        """测试缓存目录已是最新时跳过更新"""
        # 在缓存中创建目录
        cache_dir = os.path.join("test_base", "cached_dir")
        self._create_cache_directory(cache_dir, self.test_archive_hash)
        
        # 模拟远程哈希匹配
        with patch.object(FileCache, 'build_download_url') as build_mock:
            build_mock.return_value = "https://repo.example.com/hash_url"
            fetch_mock.return_value = io.BytesIO(self.test_archive_hash.encode())
            
            # 提供目录
            result = self.file_cache.provide_directory(
                "test_base", "cached_dir", "https://repo.example.com"
            )
            
            # 验证路径
            expected_path = os.path.join(self.config['agent']['cache_dir'], cache_dir)
            self.assertEqual(result, expected_path)
            
            # 验证解压未被调用（使用现有目录）
            unpack_mock.assert_not_called()
    
    def test_url_building(self):
        """测试URL构建逻辑"""
        result = self.file_cache.build_download_url(
            "https://repo.example.com/resources", 
            "stacks/HDP/3.0/services", 
            "package.zip"
        )
        self.assertEqual(
            result, 
            "https://repo.example.com/resources/stacks/HDP/3.0/services/package.zip"
        )
    
    def test_url_building_edge_cases(self):
        """测试边界情况下的URL构建"""
        # 缺少尾部斜杠
        result = self.file_cache.build_download_url(
            "https://repo.example.com",
            "custom/actions",
            "action.zip"
        )
        self.assertEqual(
            result,
            "https://repo.example.com/custom/actions/action.zip"
        )
        
        # 含查询参?        result = self.file_cache.build_download_url(
            "https://repo.example.com/api?token=xyz",
            "downloads",
            "file.tgz"
        )
        self.assertEqual(
            result,
            "https://repo.example.com/api/downloads/file.tgz?token=xyz"
        )
    
    @patch('urllib.request.urlopen')
    def test_file_download(self, urlopen_mock):
        """测试文件下载功能"""
        # 创建模拟响应
        mock_response = MagicMock()
        mock_response.read.side_effect = [
            b"first part ", 
            b"second part", 
            b""  # 退出条?        ]
        urlopen_mock.return_value = mock_response
        
        # 执行下载
        buffer = self.file_cache.fetch_url("https://repo.example.com/test.zip")
        
        # 验证结果
        self.assertEqual(buffer.getvalue(), b"first part second part")
        self.assertEqual(mock_response.read.call_count, 3)
        
        # 测试连接失败
        urlopen_mock.side_effect = Exception("Connection error")
        with self.assertRaises(CachingException):
            self.file_cache.fetch_url("https://repo.example.com/invalid")

    def test_hash_management(self):
        """测试哈希值读写功?""
        test_dir = os.path.join(self.config['agent']['cache_dir'], "hash_test")
        os.makedirs(test_dir, exist_ok=True)
        
        # 写入哈希
        test_hash = "test_hash_value"
        self.file_cache.write_hash_sum(test_dir, test_hash)
        
        # 读取哈希
        result = self.file_cache.read_hash_sum(test_dir)
        self.assertEqual(result, test_hash)
        
        # 测试读取不存在文?        non_existent_dir = os.path.join(self.config['agent']['cache_dir'], "not_exist")
        result = self.file_cache.read_hash_sum(non_existent_dir)
        self.assertIsNone(result)
        
        # 测试写入失败
        with patch("builtins.open", side_effect=PermissionError):
            with self.assertRaises(CachingException):
                self.file_cache.write_hash_sum("/root/protected_dir", "hash")


class DirectoryManagementTests(FileCacheTestBase):
    """测试目录管理功能"""
    
    def test_directory_invalidation(self):
        """测试缓存目录重置逻辑"""
        # 创建不同类型的测试目?        file_path = os.path.join(self.config['agent']['cache_dir'], "test_file.txt")
        with open(file_path, 'w') as f:
            f.write("test content")
        
        dir_path = os.path.join(self.config['agent']['cache_dir'], "test_dir")
        os.makedirs(dir_path, exist_ok=True)
        
        # 重置文件
        self.file_cache.invalidate_directory(file_path)
        self.assertTrue(os.path.exists(file_path))  # 应该重新创建
        self.assertFalse(os.path.isdir(file_path))  # 应该是文?        
        # 重置目录
        self.file_cache.invalidate_directory(dir_path)
        self.assertTrue(os.path.isdir(dir_path))  # 目录应该重新创建
        self.assertEqual(len(os.listdir(dir_path)), 0)  # 目录应为?        
        # 重置不存在路?        non_existent = os.path.join(self.config['agent']['cache_dir'], "no_such_path")
        self.file_cache.invalidate_directory(non_existent)
        self.assertTrue(os.path.isdir(non_existent))  # 应该创建目录
    
    @patch('os.makedirs')
    def test_directory_invalidation_errors(self, makedirs_mock):
        """测试目录重置错误处理"""
        # 创建失败
        makedirs_mock.side_effect = PermissionError("No permission")
        with self.assertRaises(CachingException):
            self.file_cache.invalidate_directory("/root/protected_dir")


class ArchiveHandlingTests(FileCacheTestBase):
    """测试压缩包处理功?""
    
    def test_archive_unpacking(self):
        """测试ZIP解压功能"""
        test_dir = tempfile.mkdtemp(dir=self.cache_dir)
        
        # 提供测试归档文件
        with open(self.test_archive_path, 'rb') as archive_file:
            self.file_cache.unpack_archive(archive_file, test_dir)
        
        # 验证提取的文?        for path, expected_content in self.test_archive_content.items():
            extracted_path = os.path.join(test_dir, path)
            self.assertTrue(os.path.exists(extracted_path))
            
            with open(extracted_path, 'r') as f:
                self.assertEqual(f.read(), expected_content)
    
    @patch('cloud_agent.FileCache.zipfile.ZipFile')
    def test_archive_unpacking_errors(self, zipfile_mock):
        """测试归档解压错误处理"""
        # 模拟损坏的ZIP文件
        zipfile_mock.return_value.extractall.side_effect = zipfile.BadZipFile
        
        with open(self.test_archive_path, 'rb') as archive_file:
            with self.assertRaises(CachingException):
                self.file_cache.unpack_archive(archive_file, "/tmp/some_dir")
        
        # 模拟权限问题
        zipfile_mock.return_value.extractall.side_effect = PermissionError
        
        with open(self.test_archive_path, 'rb') as archive_file:
            with self.assertRaises(CachingException):
                self.file_cache.unpack_archive(archive_file, "/root/protected_dir")


class ConcurrencyTests(FileCacheTestBase):
    """测试并发访问功能"""
    
    @patch.object(FileCache, 'fetch_url')
    def test_concurrent_directory_access(self, fetch_mock):
        """测试多线程下的缓存目录访?""
        # 模拟真实ZIP内容
        fetch_mock.return_value = open(self.test_archive_path, 'rb')
        
        # 多个线程访问同一目录
        dir_lock = threading.Lock()
        results = {}
        target_dir = "concurrent_dir"
        
        def worker(thread_id):
            try:
                path = self.file_cache.provide_directory(
                    "base", target_dir, "https://repo.example.com"
                )
                with dir_lock:
                    results[thread_id] = path
            except Exception as e:
                with dir_lock:
                    results[thread_id] = str(e)
        
        threads = []
        for i in range(5):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # 所有线程应收到相同路径
        base_path = os.path.join(
            self.config['agent']['cache_dir'], "base", target_dir
        )
        for path in results.values():
            self.assertEqual(path, base_path)
        
        # 应只下载一?        self.assertEqual(fetch_mock.call_count, 2)  # 哈希+内容

    @patch.object(FileCache, 'fetch_url')
    def test_concurrent_directory_update(self, fetch_mock):
        """测试多线程下的缓存目录更?""
        # 第一阶段：首次访?        fetch_mock.return_value = open(self.test_archive_path, 'rb')
        
        # 提供目录创建缓存
        path = self.file_cache.provide_directory(
            "base", "update_dir", "https://repo.example.com"
        )
        
        # 第二阶段：模拟更?        fetch_mock.reset_mock()
        fetch_mock.side_effect = [
            io.BytesIO(b"new_hash"),  # 新哈?            open(self.test_archive_path, 'rb')  # 新内?        ]
        
        # 多个线程同时访问
        dir_lock = threading.Lock()
        results = {}
        
        def worker(thread_id):
            try:
                path = self.file_cache.provide_directory(
                    "base", "update_dir", "https://repo.example.com"
                )
                with dir_lock:
                    results[thread_id] = path
            except Exception as e:
                with dir_lock:
                    results[thread_id] = str(e)
        
        threads = []
        for i in range(5):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # 全部线程都应成功返回
        base_path = os.path.join(
            self.config['agent']['cache_dir'], "base", "update_dir"
        )
        for path in results.values():
            self.assertEqual(path, base_path)
        
        # 应只下载一次新内容
        self.assertEqual(fetch_mock.call_count, 2)  # 哈希+内容


if __name__ == "__main__":
    unittest.main()
