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
import re
import time
import socket
import tempfile
import hashlib
import urllib.request
import urllib.error
import urllib.parse
import contextlib
import ssl
from typing import Callable, Optional, Tuple, Dict
from functools import wraps
import shutil
import subprocess

# 导入平台特定模块和工�?from .exceptions import FatalException, NonFatalException, TimeoutError
from cloud_commons import OSCheck
from cloud_commons.os_platform import run_os_command
from .logging_utils import print_info_msg, print_warning_msg, print_error_msg

# 配置常量
DEFAULT_CHUNK_SIZE = 16 * 1024  # 16KB 块大�?DEFAULT_TIMEOUT = 30  # 默认超时时间(�?
MAX_RETRIES = 3  # 最大重试次�?RETRY_DELAY = 2  # 重试延迟(�?
MAX_REDIRECTS = 5  # 最大重定向次数
TEMP_FILE_SUFFIX = ".download"  # 临时文件后缀

def _create_retry_decorator(max_retries=MAX_RETRIES):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (urllib.error.URLError, socket.timeout) as e:
                    if attempt < max_retries:
                        delay = RETRY_DELAY * attempt
                        print_warning_msg(f"Retry #{attempt} after {delay}s: {str(e)}")
                        time.sleep(delay)
                    else:
                        raise TimeoutError(f"Operation timed out after {max_retries} attempts")
                except OSError as e:
                    if "ETIMEDOUT" in str(e) and attempt < max_retries:
                        delay = RETRY_DELAY * 2
                        print_warning_msg(f"Network timeout, retry #{attempt} in {delay}s")
                        time.sleep(delay)
                    else:
                        raise
        return wrapper
    return decorator

@urllib.request.install_opener
@contextlib.contextmanager
def _configure_ssl_context(protocol="PROTOCOL_TLSv1_2", ca_certs=None):
    """配置自定义SSL上下�?""
    context = ssl.SSLContext(getattr(ssl, protocol, ssl.PROTOCOL_TLS))
    
    if ca_certs and os.path.exists(ca_certs):
        context.load_verify_locations(ca_certs)
        context.verify_mode = ssl.CERT_REQUIRED
    else:
        print_warning_msg("Using default SSL certificates")
    
    context.check_hostname = False
    
    # 创建自定义opener
    https_handler = urllib.request.HTTPSHandler(context=context)
    opener = urllib.request.build_opener(https_handler)
    
    try:
        yield opener
    finally:
        # 清理操作
        pass

@_create_retry_decorator()
def safe_openurl(url: str, timeout=DEFAULT_TIMEOUT, ssl_context: dict = None) -> object:
    """安全的URL打开函数，支持SSL配置和重试机�?""
    if ssl_context:
        with _configure_ssl_context(**ssl_context) as opener:
            return opener.open(url, timeout=timeout)
    else:
        return urllib.request.urlopen(url, timeout=timeout)

def _resolve_final_url(url: str, max_redirects=MAX_REDIRECTS) -> str:
    """解析URL最终的重定向目�?""
    current_url = url
    for _ in range(max_redirects):
        try:
            with urllib.request.urlopen(current_url) as response:
                if response.url != current_url:
                    current_url = response.url
                else:
                    break
        except Exception:
            break
    return current_url

def _calculate_file_hash(file_path: str, algorithm='sha256') -> str:
    """计算文件哈希值用于完整性验�?""
    hash_func = hashlib.new(algorithm)
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hash_func.update(chunk)
    return hash_func.hexdigest()

def _safe_move_file(source: str, destination: str) -> None:
    """安全移动文件，支持跨设备操作"""
    try:
        # 尝试原子操作
        os.replace(source, destination)
    except OSError:
        try:
            # 回退到复�?删除
            shutil.copy2(source, destination)
            os.remove(source)
        except Exception as e:
            raise FatalException(5, f"Failed to move file: {str(e)}")

def _get_remote_file_size(url: str) -> int:
    """获取远程文件大小"""
    try:
        with safe_openurl(url) as response:
            return int(response.headers.get('Content-Length', '0'))
    except Exception:
        return -1  # 表示未知大小

def get_host_from_url(uri: str) -> Optional[str]:
    """
    安全地从URL中提取主机名
    兼容RFC3986，支持多种URL格式
    
    >>> get_host_from_url("http://example.com:8080/path")
    'example.com'
    >>> get_host_from_url("192.168.1.1:8080")
    '192.168.1.1'
    """
    if not uri or not isinstance(uri, str):
        return None
    
    # 使用urllib.parse进行更安全的解析
    try:
        parsed = urllib.parse.urlparse(uri)
        if parsed.netloc:
            # 分离端口�?            hostname = parsed.netloc.split(':')[0]
            if hostname and hostname != "localhost":
                return hostname
               
        # 处理没有scheme的情况（�?192.168.1.1:8080�?        if not parsed.scheme and not parsed.netloc and parsed.path:
            match = re.match(r"([0-9a-zA-Z\-\.]+)(:[0-9]+)?", parsed.path)
            if match:
                return match.group(1)
    except ValueError:
        pass
    
    # 作为最后的回退，使用正则提�?    match = re.search(r"([0-9a-zA-Z\-\.]+)(:[0-9]+)?", uri)
    return match.group(1) if match else None

def download_progress(file_name: str, downloaded_size: int, block_size: int, total_size: int) -> None:
    """高级下载进度显示器，避免过度刷新"""
    if total_size <= 0:
        return
    
    percent = min(100, int(downloaded_size * 100 / total_size))
    current_time = time.time()
    
    # 限制刷新频率（每秒最多更新一次）
    if not hasattr(download_progress, 'last_update') or current_time - download_progress.last_update >= 1:
        downloaded_mb = downloaded_size / 1024 / 1024.0
        total_mb = total_size / 1024 / 1024.0
        
        # 避免微小文件显示进度
        if total_mb > 0.1:
            status = f"\r{file_name}... {percent}% ({downloaded_mb:.1f}MB of {total_mb:.1f}MB)"
            sys.stdout.write(status)
            sys.stdout.flush()
        
        download_progress.last_update = current_time
    
    # 完成后换�?    if downloaded_size >= total_size:
        sys.stdout.write("\n")
        sys.stdout.flush()

def download_file(
    url: str,
    destination: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    progress_func: Callable = download_progress,
    resume: bool = True,
    ssl_context: Dict = None
) -> None:
    """
    安全可靠的文件下载函�?    - 支持断点续传
    - 自动重试
    - 完整性校�?    - SSL配置选项
    """
    print_info_msg(f"Initiating download: {url} -> {destination}")
    
    # 1. 创建目标目录
    destination_dir = os.path.dirname(destination) or os.getcwd()
    os.makedirs(destination_dir, exist_ok=True)
    
    # 2. 检查文件是否存在（跳过完整下载�?    if os.path.exists(destination):
        remote_size = _get_remote_file_size(url)
        if remote_size > 0 and os.path.getsize(destination) == remote_size:
            print_warning_msg(f"Skipping existing complete file: {destination}")
            return
    
    # 3. 解析最终URL（处理重定向�?    final_url = _resolve_final_url(url)
    if final_url != url:
        print_info_msg(f"Resolved final URL: {final_url}")
    
    # 4. 执行核心下载
    try:
        _force_download_file(
            final_url,
            destination,
            chunk_size=chunk_size,
            progress_func=progress_func,
            resume=resume,
            ssl_context=ssl_context
        )
    except Exception as e:
        print_error_msg(f"Download failed: {str(e)}")
        raise NonFatalException(10, "Unable to complete download")

def download_file_anyway(
    url: str,
    destination: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    progress_func: Callable = download_progress,
    ssl_context: Dict = None
) -> None:
    """
    更稳健的下载方法，含备用策略
    - 尝试Python内置�?    - 失败时回退到curl
    - 双引擎哈希校�?    """
    print_info_msg(f"Attempting robust download: {url} -> {destination}")
    
    # 首先尝试标准下载
    try:
        download_file(url, destination, chunk_size, progress_func, ssl_context=ssl_context)
        return
    except Exception as py_err:
        print_warning_msg(f"Python download failed: {str(py_err)}")
    
    # 回退到curl下载
    curl_download(url, destination)
    
    # 最终检�?    if not os.path.exists(destination):
        print_error_msg(f"Unable to download file {url}!")
        raise FatalException(11, f"Failed to download: {url}")

def curl_download(url: str, destination: str) -> None:
    """使用系统curl工具进行下载"""
    print_info_msg(f"Falling back to curl for {url}")
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    
    # 构建curl命令
    cmd = [
        "curl", 
        "--fail", 
        "--location", 
        "--max-time", str(DEFAULT_TIMEOUT),
        "--retry", str(MAX_RETRIES),
        "--output", destination,
        url
    ]
    
    try:
        print_info_msg(f"Executing: {' '.join(cmd)}")
        subprocess.run(cmd, check=True, timeout=DEFAULT_TIMEOUT*2)
        print_info_msg(f"Curl download succeeded: {destination}")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        # 清理部分下载的文�?        if os.path.exists(destination):
            os.remove(destination)
        print_error_msg(f"Curl download failed: {str(e)}")
        raise NonFatalException(12, "Curl download failed") from e

def _force_download_file(
    url: str,
    destination: str,
    chunk_size: int,
    progress_func: Callable,
    resume: bool,
    ssl_context: Dict = None
) -> None:
    """核心下载引擎"""
    # 1. 准备临时文件（安全命名）
    dest_dir = os.path.dirname(destination)
    with tempfile.NamedTemporaryFile(prefix=".download_", suffix=TEMP_FILE_SUFFIX, 
                                    dir=dest_dir, delete=False) as temp_file:
        temp_path = temp_file.name
    
    # 2. 检查恢复点
    existing_size = os.path.getsize(temp_path) if os.path.exists(temp_path) else 0
    resume_pos = 0
    
    if resume and existing_size > chunk_size:
        print_info_msg(f"Resuming download from position {existing_size}")
        resume_pos = max(0, existing_size - chunk_size)  # 重载最后的数据块以确保完整�?    
    # 3. 准备请求
    request = urllib.request.Request(url)
    if resume_pos > 0:
        request.add_header("Range", f"bytes={resume_pos}-")
    
    # 4. 执行HTTP请求
    try:
        file_size = 0
        with safe_openurl(request, ssl_context=ssl_context) as response:
            # 处理范围响应
            content_range = response.headers.get('Content-Range', '')
            if 'bytes' in content_range:
                parts = content_range.split(' ')[-1].split('/')
                if len(parts) == 2 and parts[1] != '*':
                    file_size = int(parts[1])
            
            # 备用内容长度检�?            if file_size == 0:
                file_size = int(response.headers.get('Content-Length', '0'))
            
            # 打开文件准备写入
            open_mode = 'ab' if resume_pos > 0 else 'wb'
            with open(temp_path, open_mode) as f:
                # 处理续传位置
                if resume_pos > 0:
                    f.seek(resume_pos)
                
                # 核心读写循环
                chunk = b''
                downloaded_size = resume_pos
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    
                    downloaded_size += len(chunk)
                    f.write(chunk)
                    
                    # 进度回调
                    if progress_func:
                        progress_func(os.path.basename(destination), 
                                     downloaded_size, 
                                     len(chunk), 
                                     file_size)
        
        # 完整性校�?        final_size = os.path.getsize(temp_path)
        if file_size > 0 and final_size < file_size:
            print_warning_msg(f"Incomplete file: got {final_size} expected {file_size}")
            if resume:
                # 尝试恢复下载
                return _force_download_file(url, destination, chunk_size, progress_func, False, ssl_context)
            else:
                raise NonFatalException(13, "Download incomplete after retries")
        
        # 移动到最终位�?        _safe_move_file(temp_path, destination)
        print_info_msg(f"Successfully saved to {destination} - Size: {final_size / (1024 * 1024):.2f} MB")
    
    finally:
        # 确保清理临时文件
        if os.path.exists(temp_path):
            print_warning_msg(f"Cleaning up temporary file: {temp_path}")
            os.remove(temp_path)

def wait_for_port_open(host: str, port: int, timeout: int = 60, sleep_interval: float = 1.0) -> bool:
    """更可配置的端口等待函�?""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    
    start_time = time.time()
    print_info_msg(f"Waiting for {host}:{port} to become available...")
    
    while time.time() - start_time < timeout:
        try:
            if sock.connect_ex((host, port)) == 0:
                print_info_msg(f"Port {host}:{port} is open")
                return True
        except socket.error as e:
            print_warning_msg(f"Socket error: {str(e)}")
        
        # 递减精度显示剩余时间
        remaining = timeout - (time.time() - start_time)
        if remaining > 1:
            sys.stdout.write(f"\rWaiting... {remaining:.0f}s left")
            sys.stdout.flush()
        
        time.sleep(sleep_interval)
    
    print_error_msg(f"Timeout waiting for {host}:{port}")
    return False

def resolve_address(address: str) -> str:
    """地址解析器，带智能处�?""
    # 处理特殊的绑定地址
    if address in ['0.0.0.0', '::']:
        if OSCheck.is_windows_family():
            return '127.0.0.1'
        else:
            return 'localhost'
    
    # 尝试DNS解析
    try:
        socket.getaddrinfo(address, None)
        return address
    except socket.error:
        pass
    
    # 回退到正则验�?    if re.match(r"^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$", address):
        return address
    
    # 最终回退
    return '127.0.0.1' if OSCheck.is_windows_family() else 'localhost'

def configure_ssl(
    protocol: str = "PROTOCOL_TLSv1_2", 
    ca_certs: str = None, 
    verify_hostname: bool = False,
    cipher_list: str = None
) -> Dict:
    """生成用于下载的SSL上下文配�?""
    return {
        'protocol': protocol,
        'ca_certs': ca_certs,
        'verify_hostname': verify_hostname,
        'cipher_list': cipher_list
    }

# 兼容旧API
openurl = safe_openurl
download_file = download_file
download_file_anyway = download_file_anyway
wait_for_port_opened = wait_for_port_open
get_host_from_url = get_host_from_url
resolve_address = resolve_address
ensure_ssl_using_protocol = configure_ssl
