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

Enhanced URL Path Extraction Utility
"""

import re
from urllib.parse import urlparse
from resource_management.libraries.functions.is_empty import is_empty

__all__ = ["get_path_from_url", "parse_url_components"]

# 增强的URL解析正则表达式
URL_PATTERN = re.compile(
    r"^"
    r"(?:(?P<scheme>[a-zA-Z][a-zA-Z0-9+.\-]*)://)?"  # 协议(可选)
    r"(?:(?P<username>[^:]+?)(?::(?P<password>[^@]*?))?@)?"  # 用户名密码(可选)
    r"(?P<host>"  # 主机部分
        r"(?:\[[a-fA-F0-9:]+\]|"  # IPv6地址 (如 [::1])
        r"[\w\.\-]+"  # 常规域名
    r")"
    r"(?::(?P<port>\d{1,5}))?"  # 端口(可选)
    r"(?P<path>/[^?#]*)?"  # 路径部分(必须以斜杠开头，可选)
    r"(?:\?(?P<query>[^#]*))?"  # 查询字符串(可选)
    r"(?:#(?P<fragment>.*))?"  # 片段标识(可选)
    r"$", 
    re.IGNORECASE
)

def parse_url_components(url, default_port=None):
    """解析URL字符串并返回结构化组件
    
    参数:
        url: 需要解析的URL字符串
        default_port: 当URL中未提供端口时的默认端口
        
    返回:
        dict: 包含解析后组件的字典，键包括:
            'scheme' (协议), 'username' (用户名), 'password' (密码), 
            'host' (主机), 'port' (端口), 'path' (路径), 
            'query' (查询字符串), 'fragment' (片段标识)
    """
    if is_empty(url):
        return {
            "scheme": None,
            "username": None,
            "password": None,
            "host": None,
            "port": default_port,
            "path": None,
            "query": None,
            "fragment": None
        }
    
    # 首先尝试使用标准库解析
    try:
        parsed = urlparse(url)
        return {
            "scheme": parsed.scheme if parsed.scheme else None,
            "username": parsed.username,
            "password": parsed.password,
            "host": parsed.hostname,
            "port": parsed.port if parsed.port is not None else default_port,
            "path": parsed.path if parsed.path else '/',
            "query": parsed.query,
            "fragment": parsed.fragment
        }
    except ValueError:
        # 如果标准库无法解析，尝试使用增强正则表达式
        match = URL_PATTERN.match(url.strip())
        if match:
            components = match.groupdict()
            # 处理端口转换
            if components['port']:
                try:
                    components['port'] = int(components['port'])
                except (ValueError, TypeError):
                    components['port'] = default_port
            
            # 处理空路径
            if not components['path']:
                components['path'] = '/'
            
            return components
    
    # 无法解析的情况
    return {
        "scheme": None,
        "username": None,
        "password": None,
        "host": None,
        "port": default_port,
        "path": None,
        "query": None,
        "fragment": None
    }

def get_path_from_url(url):
    """从URL中提取路径部分
    
    参数:
        url: 需要解析的URL字符串
        
    返回:
        str: URL的路径部分，如果URL无效或路径不存在则返回None
    """
    if is_empty(url):
        return None
    
    # 纯数字端口号处理
    if url.isdigit():
        return None
    
    # 解析URL组件
    components = parse_url_components(url)
    
    # 返回路径部分
    if components and 'path' in components and components['path']:
        return components['path']
    
    return None


# ------------------- 高级用例扩展 -------------------
def get_normalized_path(url, remove_trailing_slash=True):
    """获取规范化后的路径（去除查询参数和片段）"""
    path = get_path_from_url(url)
    if path:
        # 移除查询参数和片段标识（如果有）
        path = path.split('?')[0]
        path = path.split('#')[0]
        
        # 可选：移除尾部斜杠
        if remove_trailing_slash and path.endswith('/') and path != '/':
            path = path.rstrip('/')
    
    return path

def extract_filename_from_url(url, include_extension=True):
    """从URL路径中提取文件名"""
    path = get_normalized_path(url, remove_trailing_slash=True)
    if not path or path == '/':
        return None
    
    # 获取最后一部分作为文件名
    filename = path.split('/')[-1]
    
    # 移除扩展名（可选）
    if not include_extension:
        filename = filename.split('.')[0]
    
    return filename

def is_same_base_url(url1, url2):
    """检查两个URL是否具有相同的基础地址（不考虑路径和查询参数）"""
    comp1 = parse_url_components(url1)
    comp2 = parse_url_components(url2)
    
    return (
        comp1['scheme'] == comp2['scheme'] and
        comp1['host'] == comp2['host'] and
        comp1['port'] == comp2['port']
    )

# ------------------- 单元测试助手 -------------------
def run_path_extraction_tests():
    """运行URL解析测试用例"""
    test_cases = [
        # (输入URL, 预期路径输出, 描述)
        ("https://example.com/path/to/resource", "/path/to/resource", "标准HTTPS URL"),
        ("http://user:pass@example.com:8080/api/v1/data.json?query=1#section", "/api/v1/data.json", "含认证参数的URL"),
        ("ftp://ftp.example.com/downloads/archive.tar.gz", "/downloads/archive.tar.gz", "FTP URL"),
        ("hdfs://namenode:8020/user/hadoop/input", "/user/hadoop/input", "HDFS URL"),
        ("//cdn.example.com/assets/image.png", "/assets/image.png", "协议相对URL"),
        ("/local/path/without/host", "/local/path/without/host", "无主机路径"),
        ("example.com:8080", None, "仅有主机和端口"),
        ("12345", None, "纯数字端口"),
        ("[2001:db8::1]:8080/api", "/api", "IPv6地址URL"),
        ("https://example.com", "/", "无路径URL"),
        ("/", "/", "根路径"),
        ("", None, "空输入"),
        (None, None, "None输入"),
        ("https://example.com/path/with spaces", "/path/with spaces", "含空格的路径"),
        ("http://example.com/有中文/路径/", "/有中文/路径/", "含Unicode字符的路径"),
        ("app://custom.scheme/path/to/resource", "/path/to/resource", "自定义协议Scheme")
    ]
    
    passed = 0
    failed = 0
    
    print("=" * 80)
    print("URL 路径提取测试报告")
    print("=" * 80)
    
    for i, (input_url, expected, description) in enumerate(test_cases, 1):
        result = get_path_from_url(input_url)
        status = "PASS" if result == expected else "FAIL"
        
        if status == "PASS":
            passed += 1
        else:
            failed += 1
        
        print(f"测试 #{i} [{status}] - {description}")
        print(f"输入: {input_url}")
        print(f"期望: {expected!r}")
        print(f"实际: {result!r}")
        print("-" * 80)
    
    print(f"\n测试结果: 通过 {passed}, 失败 {failed}, 总数 {passed + failed}")
    return failed == 0


if __name__ == "__main__":
    # 执行自测
    success = run_path_extraction_tests()
    
    # 退出状态码：成功为0，失败为1
    exit(0 if success else 1)

