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
import logging
import shutil
import zipfile
import urllib.request
import time
import threading
import hashlib
import tempfile
import fcntl
import errno
from typing import Dict, Optional, Tuple, BinaryIO
from pathlib import Path

# 配置日志
logger = logging.getLogger("FileCacheService")
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] [%(asctime)s] [%(name)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

class FileCacheException(Exception):
    """自定义缓存异常基类"""
    pass

class DownloadFailedError(FileCacheException):
    """下载失败异常"""
    pass

class InvalidArchiveError(FileCacheException):
    """无效的压缩文件异常"""
    pass

class IntegrityCheckFailedError(FileCacheException):
    """完整性校验失败异常"""
    pass

class FileCache:
    """智能文件缓存服务
    
    提供高效的资源缓存机制，特点：
    - 多层级并发控制
    - 完整性哈希验证
    - 自动缓存更新
    - 原子操作防止损坏
    - 弹性错误处理
    - 磁盘空间管理
    """
    
    # 目录常量
    ALERTS_CACHE_DIR = "alerts"
    RECOVERY_CACHE_DIR = "recovery"
    STACKS_CACHE_DIR = "stacks"
    COMMON_SERVICES_DIR = "common-services"
    CUSTOM_ACTIONS_CACHE_DIR = "custom_actions"
    EXTENSIONS_CACHE_DIR = "extensions"
    HOST_SCRIPTS_CACHE_DIR = "host_scripts"
    
    # 文件名常量
    HASH_FILE = ".hash"
    ARCHIVE_NAME = "archive.zip"
    
    # 配置键名
    CACHE_DIR_KEY = "cache_dir"
    TOLERATE_DOWNLOAD_FAILURES_KEY = "tolerate_download_failures"
    AUTO_CACHE_UPDATE_KEY = "agent.auto.cache.update"
    
    # 网络配置
    DEFAULT_BLOCK_SIZE = 64 * 1024  # 64KB
    MIN_BLOCK_SIZE = 4 * 1024       # 4KB
    MAX_RETRIES = 3
    RETRY_DELAY = 2                # 2秒
    CONNECTION_TIMEOUT = 15         # 15秒
    
    def __init__(self, config: Dict):
        """初始化文件缓存服务
        
        :param config: 包含缓存配置的字典
        """
        self.config = config
        self.cache_root = Path(self.config.get(self.CACHE_DIR_KEY, "/var/lib/cloud/cache"))
        self.tolerate_download_failures = self.config.get(self.TOLERATE_DOWNLOAD_FAILURES_KEY, "true").lower() == "true"
        
        # 并发控制
        self.cache_operations_lock = threading.RLock()
        self.active_downloads: Dict[str, threading.Event] = {}
        
        # 确保缓存目录存在
        self.cache_root.mkdir(parents=True, exist_ok=True)
        logger.info(f"文件缓存服务已初始化，根目录: {self.cache_root}")

    def auto_cache_update_enabled(self) -> bool:
        """检查是否启用自动缓存更新"""
        return self.config.get(self.AUTO_CACHE_UPDATE_KEY, "true").lower() == "true"

    def get_cache_directory(self, category: str, command: Dict) -> Path:
        """获取特定类别的缓存目录路径"""
        # 处理自定义服务路径
        if category == "service" and "service_package_folder" in command.get("commandParams", {}):
            subpath = command["commandParams"]["service_package_folder"]
        elif category == "service":
            subpath = command["serviceLevelParams"]["service_package_folder"]
        elif category == "hooks":
            subpath = command.get("clusterLevelParams", {}).get("hooks_folder", self.COMMON_SERVICES_DIR)
        else:
            subpath = getattr(self, f"{category.upper()}_CACHE_DIR")
        
        # 服务器URL前缀
        server_prefix = command.get("cloudLevelParams", {}).get("jdk_location", "")
        
        # 提供路径
        return self.provide_directory(subpath, server_prefix)

    def provide_directory(self, subdirectory: str, server_url_prefix: str = "") -> Path:
        """确保缓存目录最新并可用"""
        full_path = self.cache_root / subdirectory
        logger.debug(f"为目录 '{subdirectory}' 准备缓存路径: {full_path}")
        
        # 检查是否启用自动更新
        if not self.auto_cache_update_enabled():
            logger.debug("自动缓存更新已禁用 - 使用现有文件")
            return full_path
        
        try:
            # 创建文件锁确保原子操作
            with self.fetch_lock(str(full_path)):
                if not self.is_cache_up_to_date(full_path, server_url_prefix):
                    self.download_and_extract(subdirectory, server_url_prefix, full_path)
            
            return full_path
        except FileCacheException as e:
            if self.tolerate_download_failures:
                logger.warning(f"缓存更新失败但已配置容忍 (错误: {str(e)})")
                return full_path
            logger.error(f"缓存更新失败 (错误: {str(e)})")
            raise

    def is_cache_up_to_date(self, full_path: Path, server_url_prefix: str) -> bool:
        """检查缓存目录是否最新"""
        # 目录不存在 -> 需要更新
        if not full_path.exists():
            logger.info(f"缓存目录不存在: {full_path} - 需要初始化")
            return False
        
        # 获取远程和本地哈希
        try:
            remote_hash = self.fetch_url(
                self.build_download_url(server_url_prefix, full_path.name, self.HASH_FILE)
            )
            remote_hash = remote_hash.decode().strip()
            if not remote_hash:
                logger.warning("远程哈希为空 - 跳过更新检查")
                return True
        except DownloadFailedError as e:
            logger.warning(f"无法获取远程哈希: {str(e)} - 使用现有缓存")
            return True
        
        local_hash = self.read_hash_file(full_path)
        
        if local_hash == remote_hash:
            logger.debug(f"缓存目录 '{full_path.name}' 已是最新版本")
            return True
        
        logger.info(f"缓存需要更新 (本地: {local_hash}, 远程: {remote_hash})")
        return False

    def download_and_extract(self, subdirectory: str, server_url_prefix: str, full_path: Path) -> None:
        """下载并提取缓存内容"""
        logger.info(f"开始更新缓存: {subdirectory}")
        
        # 步骤1: 下载哈希和存档
        remote_hash = self.fetch_url(
            self.build_download_url(server_url_prefix, subdirectory, self.HASH_FILE)
        ).decode().strip()
        
        archive_content = self.fetch_url(
            self.build_download_url(server_url_prefix, subdirectory, self.ARCHIVE_NAME)
        )
        
        # 验证内容
        if not remote_hash or not archive_content:
            raise DownloadFailedError("下载的缓存内容无效")
        
        # 计算下载内容的哈希值
        actual_hash = self.calculate_hash(archive_content)
        if actual_hash != remote_hash:
            raise IntegrityCheckFailedError(f"哈希验证失败 (远程: {remote_hash}, 实际: {actual_hash})")
        
        # 使用临时目录确保原子操作
        with tempfile.TemporaryDirectory(dir=self.cache_root) as tmp_dir:
            temp_path = Path(tmp_dir)
            try:
                # 解压到临时目录
                self.unpack_archive(archive_content, temp_path)
                
                # 清理现有的缓存（如果存在）
                if full_path.exists():
                    try:
                        versioned_path = full_path.with_name(f"{full_path.name}_{time.strftime('%Y%m%d_%H%M%S')}")
                        shutil.move(str(full_path), str(versioned_path))
                        logger.debug(f"备份旧缓存: {versioned_path}")
                    except Exception as e:
                        logger.warning(f"无法备份旧缓存: {str(e)}")
                        shutil.rmtree(full_path, ignore_errors=True)
                
                # 移动到最终位置
                shutil.move(str(temp_path / subdirectory), str(full_path))
                
                # 写入新哈希
                self.write_hash_file(full_path, remote_hash)
                
                logger.info(f"成功更新缓存: {full_path}")
                logger.debug(f"缓存大小: {self.get_directory_size(full_path) / 1048576:.2f} MB")
            except Exception as e:
                logger.error(f"缓存处理失败: {str(e)}")
                self.cleanup_failed_update(full_path)
                raise InvalidArchiveError(f"处理缓存失败: {str(e)}")

    def build_download_url(self, server_url_prefix: str, directory: str, filename: str) -> str:
        """构建下载URL"""
        normalized_dir = directory.lstrip('/').rstrip('/')
        return f"{server_url_prefix.rstrip('/')}/{normalized_dir}/{filename}"

    def fetch_url(self, url: str) -> bytes:
        """获取URL内容（带重试机制）"""
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                logger.debug(f"下载 URL 尝试 #{attempt}/{self.MAX_RETRIES}: {url}")
                
                with urllib.request.urlopen(url, timeout=self.CONNECTION_TIMEOUT) as response:
                    if response.status != 200:
                        raise DownloadFailedError(f"服务器返回状态: {response.status}")
                    
                    block_size = self.calculate_block_size(response.length)
                    content = bytearray()
                    total_received = 0
                    
                    while True:
                        chunk = response.read(block_size)
                        if not chunk:
                            break
                        content.extend(chunk)
                        total_received += len(chunk)
                    
                    logger.debug(f"成功下载资源 ({len(content)/1048576:.2f} MB, {url})")
                    return bytes(content)
            except Exception as e:
                if attempt < self.MAX_RETRIES:
                    logger.warning(f"下载尝试 #{attempt} 失败 (错误: {str(e)}), {self.RETRY_DELAY}秒后重试")
                    time.sleep(self.RETRY_DELAY)
                else:
                    logger.error(f"下载尝试 #{attempt}/{self.MAX_RETRIES} 失败 (错误: {str(e)})")
                    raise DownloadFailedError(f"所有下载尝试失败: {str(e)}")
        
        # 理论上永远不会执行到此处
        raise DownloadFailedError("意外的下载失败")

    def calculate_block_size(self, content_length: Optional[int]) -> int:
        """计算最佳分块大小"""
        if content_length is None or content_length <= 0:
            return self.DEFAULT_BLOCK_SIZE
            
        if content_length > 20 * 1024 * 1024:  # >20MB
            return min(max(content_length // 100, self.MIN_BLOCK_SIZE), self.DEFAULT_BLOCK_SIZE * 4)
        
        return self.DEFAULT_BLOCK_SIZE

    def unpack_archive(self, content: bytes, target_dir: Path) -> None:
        """安全解压ZIP归档"""
        if not self.validate_archive(content):
            raise InvalidArchiveError("无效的ZIP归档格式")
        
        try:
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(content)
                temp_path = temp_file.name
            
            # 使用安全解压
            with zipfile.ZipFile(temp_path, 'r') as zfile:
                # 安全验证1: 检查是否存在ZIP炸弹
                total_size = sum(file.file_size for file in zfile.infolist() if not file.is_dir())
                target_size = shutil.disk_usage(str(target_dir)).free
                
                if total_size > target_size * 0.8:
                    raise InvalidArchiveError(f"ZIP文件过大 ({total_size}字节)，可能超过空间限制")
                
                # 安全验证2: 检查恶意路径
                for name in zfile.namelist():
                    if name.startswith('/') or '..' in name:
                        raise InvalidArchiveError(f"检测到不安全路径: {name}")
                
                # 开始解压
                zfile.extractall(str(target_dir))
        finally:
            # 清理临时文件
            try:
                Path(temp_path).unlink(missing_ok=True)
            except Exception:
                pass

    def validate_archive(self, content: bytes) -> bool:
        """验证ZIP归档格式"""
        try:
            zipfile.ZipFile(io.BytesIO(content))
            return True
        except zipfile.BadZipFile:
            return False

    def read_hash_file(self, path: Path) -> str:
        """读取哈希文件（如果可用）"""
        hash_file = path / self.HASH_FILE
        try:
            if hash_file.exists():
                return hash_file.read_text().strip()
        except Exception as e:
            logger.warning(f"读取哈希文件失败: {str(e)}")
        return ""

    def write_hash_file(self, path: Path, hash_value: str) -> None:
        """写入哈希文件"""
        hash_file = path / self.HASH_FILE
        try:
            with open(hash_file, 'wb') as f:
                f.write(hash_value.encode() + b'\n')
            hash_file.chmod(0o644)
        except Exception as e:
            logger.error(f"写入哈希文件失败: {str(e)}")
            raise

    def calculate_hash(self, content: bytes) -> str:
        """计算内容的SHA256哈希值"""
        return hashlib.sha256(content).hexdigest()

    def cleanup_failed_update(self, path: Path) -> None:
        """清理失败的缓存更新"""
        try:
            if path.exists():
                # 保留最少1个备份
                versions = sorted(
                    [p for p in path.parent.glob(f"{path.name}_*")],
                    key=os.path.getmtime,
                    reverse=True
                )
                
                if len(versions) > 1:
                    for old_version in versions[1:]:
                        try:
                            shutil.rmtree(old_version)
                            logger.debug(f"清理旧版本: {old_version}")
                        except Exception as e:
                            logger.warning(f"清理缓存版本失败: {str(e)}")
        except Exception as e:
            logger.error(f"缓存清理失败: {str(e)}")

    def get_directory_size(self, path: Path) -> int:
        """计算目录大小（字节）"""
        total = 0
        for entry in path.rglob('*'):
            if entry.is_file():
                total += entry.stat().st_size
        return total

    def fetch_lock(self, lock_key: str):
        """提供分布式锁的上下文管理器"""
        return FileLock(lock_key, self.cache_root)

class FileLock:
    """基于文件的分布式锁实现"""
    def __init__(self, name: str, lock_dir: Path):
        self.lock_file = lock_dir / f".{name}.lock"
        self.lock_handle = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()

    def acquire(self, timeout=30.0, poll_interval=0.1):
        """获取锁，带超时机制"""
        start_time = time.time()
        while True:
            try:
                self.lock_handle = open(self.lock_file, 'wb')
                fcntl.flock(self.lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
            except (IOError, OSError) as e:
                if e.errno != errno.EAGAIN:  # MacOS
                    if e.errno != errno.EWOULDBLOCK:  # Linux
                        raise
                
                # 检查超时
                if time.time() - start_time > timeout:
                    raise TimeoutError("获取锁超时")
                
                # 等待重试
                time.sleep(poll_interval)
    
    def release(self):
        """释放锁"""
        if self.lock_handle:
            try:
                fcntl.flock(self.lock_handle, fcntl.LOCK_UN)
                self.lock_handle.close()
            except Exception:
                pass
            finally:
                self.lock_handle = None
        
        # 清理锁文件
        try:
            self.lock_file.unlink(missing_ok=True)
        except Exception:
            pass

# 示例用法
if __name__ == "__main__":
    # 配置模拟
    config = {
        "cache_dir": "/tmp/cloud_cache",
        "tolerate_download_failures": "true",
        "agent.auto.cache.update": "true"
    }
    
    # 测试命令对象
    test_command = {
        "cloudLevelParams": {
            "jdk_location": "https://cloud-server/resources"
        },
        "commandParams": {
            "service_package_folder": "common-services/HDFS/1.0"
        }
    }
    
    # 创建缓存服务
    cache_service = FileCache(config)
    
    try:
        # 获取缓存目录
        service_cache_path = cache_service.get_cache_directory("service", test_command)
        logger.info(f"服务缓存路径: {service_cache_path}")
        
        # 检查内容
        if service_cache_path.exists():
            logger.info(f"缓存目录内容 ({len(list(service_cache_path.glob('*')))} 个文件):")
            for item in service_cache_path.iterdir():
                logger.info(f" - {item.name}")
        else:
            logger.warning("缓存目录不存在")
    except FileCacheException as e:
        logger.error(f"文件缓存操作失败: {str(e)}")

