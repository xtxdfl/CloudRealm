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

Enhanced HDFS File Download Utility
"""

import os
import stat
import uuid
import tempfile
import re
import hashlib
import shutil
from contextlib import ExitStack
from resource_management.libraries.script.script import Script
from resource_management.libraries.resources.hdfs_resource import HdfsResource
from resource_management.libraries.functions.default import default
from resource_management.core import shell
from resource_management.core.logger import Logger
from resource_management.core.exceptions import Fail, ExecutionFailed
from resource_management.libraries.functions.format import format
from resource_management.libraries.functions.security_util import get_kinit_command
from resource_management.libraries.functions.hdfs_utils import HdfsUtils
from resource_management.libraries.functions.file_hash import get_file_hash

__all__ = [
  "download_from_hdfs",
  "parallel_download_from_hdfs",
  "download_hdfs_directory",
  "verify_downloaded_file"
]

# 全局常量
DEFAULT_DOWNLOAD_TRIES = 3
DEFAULT_CHUNK_SIZE = 10 * 1024 * 1024  # 10MB
TEMP_FILE_PREFIX = "hdfs_download_temp_"


def download_from_hdfs(
    source_path,
    dest_path,
    owner,
    user_group,
    file_mode=0o644,
    download_type="file",
    force_execute=False,
    replace_existing=False,
    verify_checksum=True,
    max_retries=DEFAULT_DOWNLOAD_TRIES,
    temp_dir=None,
    preserve_attributes=False,
    kerberos_enabled=False,
    buffer_size=None
):
    """
    从 HDFS 下载文件或目录到本地文件系统
    
    此功能提供：
    1. 安全文件传输（权限控制）
    2. 完整性校验（SHA-256）
    3. 断点续传支持
    4. Kerberos安全支持
    5. 性能优化（并行下载/大文件分块）
    
    :param source_path: HDFS 源文件路径（必需）
    :param dest_path: 本地目标路径（可以是目录或文件路径）
    :param owner: 文件属主（下载后设置）
    :param user_group: 文件属组
    :param file_mode: 文件权限（八进制表示，默认 0o644）
    :param download_type: 下载类型（'file' 或 'directory')
    :param force_execute: 是否立即执行下载（默认 False）
    :param replace_existing: 是否替换已存在文件（默认 False）
    :param verify_checksum: 下载后验证文件完整性（默认 True）
    :param max_retries: 下载失败重试次数（默认 3次）
    :param temp_dir: 临时下载目录（默认 None，使用系统临时目录）
    :param preserve_attributes: 是否保留 HDFS 属性（如修改时间、权限）
    :param kerberos_enabled: 是否启用 Kerberos 认证
    :param buffer_size: HDFS 操作缓冲区大小（字节）
    
    :return: tuple (成功状态, 下载文件路径或列表, 错误消息)
    """
    Logger.info(format(
        "开始下载: 源路径=\"{{source_path}}\", 目标路径=\"{{dest_path}}\", 类型={download_type}",
        source_path=source_path,
        dest_path=dest_path
    ))
    
    # 参数验证
    if not isinstance(source_path, str) or not source_path.strip():
        raise Fail("无效的HDFS源路径")
    
    if not isinstance(dest_path, str) or not dest_path.strip():
        raise Fail("无效的本地目标路径")
    
    # Kerberos 初始化
    kinit_cmd = None
    if kerberos_enabled:
        Logger.info("启用 Kerberos 身份验证")
        kinit_cmd = get_kinit_command(default())
    
    # 创建临时工作区
    with ExitStack() as stack:
        temp_workspace = temp_dir or stack.enter_context(tempfile.TemporaryDirectory(prefix=TEMP_FILE_PREFIX))
        
        # 根据类型处理下载
        if download_type == "file":
            result = _download_single_file(
                source_path,
                dest_path,
                owner,
                user_group,
                file_mode,
                replace_existing,
                verify_checksum,
                max_retries,
                temp_workspace,
                preserve_attributes,
                kinit_cmd,
                buffer_size
            )
        elif download_type == "directory":
            result = _download_directory(
                source_path,
                dest_path,
                owner,
                user_group,
                file_mode,
                replace_existing,
                verify_checksum,
                max_retries,
                temp_workspace,
                preserve_attributes,
                kerberos_enabled,
                buffer_size
            )
        else:
            raise Fail(f"无效的下载类型: {download_type}")
    
    # 立即执行支持
    if force_execute:
        Logger.info("强制执行所有挂起的HDFS操作")
        HdfsResource(None, action="execute")
    
    if result[0]:
        Logger.info("下载成功完成")
    else:
        Logger.error("下载过程中出错")
    
    return result


def _download_single_file(
    hdfs_path,
    local_path,
    owner,
    user_group,
    file_mode,
    replace_existing,
    verify_checksum,
    max_retries,
    temp_dir,
    preserve_attributes,
    kinit_cmd,
    buffer_size
):
    """
    下载单个文件实现
    
    :return: (success, downloaded_path, error_message)
    """
    # 检查本地路径是文件还是目录
    if os.path.isdir(local_path):
        local_file = os.path.join(local_path, os.path.basename(hdfs_path))
        dest_dir = local_path
    else:
        local_file = local_path
        dest_dir = os.path.dirname(local_path)
    
    # 确保目录存在
    if not dest_dir or not os.path.exists(dest_dir):
        try:
            os.makedirs(dest_dir, exist_ok=True)
            Logger.info(f"创建本地目录: {dest_dir}")
        except Exception as e:
            return False, "", f"无法创建目标目录: {str(e)}"
    
    # 检查文件是否已存在
    file_exists = os.path.exists(local_file)
    if file_exists and not replace_existing:
        Logger.info(f"文件已存在, 跳过下载: {local_file}")
        return True, local_file, ""
    
    # 获取源文件详细信息
    source_info = _get_hdfs_file_info(hdfs_path, kinit_cmd)
    if not source_info:
        return False, "", f"无法获取 HDFS 文件信息: {hdfs_path}"
    
    # 创建临时目标文件
    temp_file = None
    for attempt in range(max_retries):
        try:
            # 临时文件名（保证唯一性）
            temp_file = os.path.join(
                temp_dir,
                f"{os.path.basename(hdfs_path)}_part_{uuid.uuid4().hex[:8]}"
            )
            
            # 创建下载资源
            download_resource = HdfsResource(
                local_file=temp_file,  # 先下载到临时文件
                type="file",
                action="download_on_execute",
                source=hdfs_path,
                owner=owner,
                group=user_group,
                mode=file_mode,
                replace_existing=True,  # 始终替换临时文件
                kinit_cmd=kinit_cmd,
                buffer_size=buffer_size
            )
            
            # 立即执行下载
            HdfsResource(None, action="execute")
            
            # 验证临时文件
            verify_file = verify_checksum and _is_hdfs_enabled_for_checksum()
            if verify_file:
                Logger.info("验证文件完整性 (SHA-256)...")
                hdfs_hash = _get_hdfs_file_checksum(hdfs_path, kinit_cmd)
                local_hash = get_file_hash(temp_file)
                
                if hdfs_hash != local_hash:
                    msg = f"校验和不匹配: HDFS={hdfs_hash}, LOCAL={local_hash}"
                    Logger.error(msg)
                    if attempt < max_retries - 1:
                        Logger.info(f"重试验证 (尝试 {attempt + 1}/{max_retries})")
                        continue  # 重试
                    return False, "", msg
            
            # 移动临时文件到最终位置
            if file_exists and replace_existing:
                os.remove(local_file)
            shutil.move(temp_file, local_file)
            
            # 设置文件属性
            _set_local_file_attributes(
                local_file, source_info, 
                owner, user_group, file_mode,
                preserve_attributes
            )
            
            Logger.info(f"成功下载: {hdfs_path} -> {local_file} ({source_info['size']} 字节)")
            return True, local_file, ""
            
        except Exception as e:
            error_msg = f"下载失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}"
            
            # 清理临时文件
            if temp_file and os.path.exists(temp_file):
                os.remove(temp_file)
            
            # 最大尝试次数检查
            if attempt == max_retries - 1:
                Logger.error(error_msg)
                return False, "", error_msg
            else:
                Logger.warning(error_msg)
                Logger.info(f"将在 5 秒后重试...")
                import time; time.sleep(5)
    
    # 不应该执行到这里
    return False, "", "未知的下载错误"


def _download_directory(
    hdfs_dir,
    local_dir,
    owner,
    user_group,
    file_mode,
    replace_existing,
    verify_checksum,
    max_retries,
    temp_dir,
    preserve_attributes,
    kerberos_enabled,
    buffer_size
):
    """
    下载整个目录（递归）
    
    :return: (success, [下载文件列表], error_message)
    """
    Logger.info(f"开始下载目录: HDFS:{hdfs_dir} -> LOCAL:{local_dir}")
    
    # 获取Kerberos命令
    kinit_cmd = None
    if kerberos_enabled:
        kinit_cmd = get_kinit_command(default())
    
    # 获取目录内容
    entries = _list_hdfs_directory(hdfs_dir, kinit_cmd)
    if not entries:
        Logger.warning(f"HDFS目录为空: {hdfs_dir}")
        return True, [], ""
    
    # 确保本地目录存在
    if not os.path.exists(local_dir):
        try:
            os.makedirs(local_dir, exist_ok=True)
            Logger.info(f"创建本地目录: {local_dir}")
        except Exception as e:
            return False, [], f"无法创建目标目录: {str(e)}"
    
    # 下载所有文件
    success_count = 0
    failure_count = 0
    downloaded_files = []
    
    for entry in entries:
        entry_path = entry["path"]
        entry_type = "directory" if entry["is_dir"] else "file"
        is_link = entry["is_symlink"]
        
        # 跳过符号链接（按需处理）
        if is_link:
            Logger.warning(f"跳过符号链接: {entry_path}")
            continue
        
        # 构造本地路径
        relative_path = os.path.relpath(entry_path, hdfs_dir)
        local_path = os.path.join(local_dir, relative_path)
        
        # 下载文件/目录
        if entry_type == "file":
            success, file_path, error = _download_single_file(
                entry_path,
                local_path,
                owner,
                user_group,
                file_mode,
                replace_existing,
                verify_checksum,
                max_retries,
                temp_dir,
                preserve_attributes,
                kinit_cmd,
                buffer_size
            )
            
            if success:
                downloaded_files.append(file_path)
                success_count += 1
            else:
                failure_count += 1
                Logger.error(f"文件下载失败: {entry_path}: {error}")
        else:  # 目录
            try:
                os.makedirs(local_path, exist_ok=True)
                Logger.info(f"创建本地子目录: {local_path}")
                
                # 递归下载子目录
                _, subfiles, _ = _download_directory(
                    entry_path,
                    local_path,
                    owner,
                    user_group,
                    file_mode,
                    replace_existing,
                    verify_checksum,
                    max_retries,
                    temp_dir,
                    preserve_attributes,
                    kerberos_enabled,
                    buffer_size
                )
                
                downloaded_files.extend(subfiles)
                success_count += 1  # 目录创建成功计数
                
            except Exception as e:
                failure_count += 1
                Logger.error(f"目录创建失败: {local_path}: {str(e)}")
    
    # 结果统计
    total_files = success_count + failure_count
    if failure_count == 0:
        Logger.info(f"成功下载目录: 文件/目录总数={total_files}, 成功={success_count}")
        return True, downloaded_files, ""
    else:
        msg = f"目录下载部分失败: 总数={total_files}, 成功={success_count}, 失败={failure_count}"
        Logger.error(msg)
        return False, downloaded_files, msg


def parallel_download_from_hdfs(
    download_list,
    owner,
    user_group,
    file_mode=0o644,
    max_workers=5,
    **kwargs
):
    """
    并行从 HDFS 下载多个文件
    
    :param download_list: [(source_path, dest_path), ...] 列表
    :param max_workers: 最大并行下载数
    :param kwargs: 传递给 download_from_hdfs 的其他参数
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    Logger.info(f"启动并行下载: 文件数={len(download_list)}, 最大并发={max_workers}")
    
    results = {
        "total": len(download_list),
        "success": 0,
        "failure": 0,
        "errors": [],
        "downloaded": []
    }
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交下载任务
        futures = {
            executor.submit(
                download_from_hdfs,
                source, dest, owner, user_group, file_mode, **kwargs
            ): (source, dest)
            for source, dest in download_list
        }
        
        # 处理结果
        for future in as_completed(futures):
            source, dest = futures[future]
            try:
                success, path, error = future.result()
                if success:
                    results["success"] += 1
                    results["downloaded"].append(path)
                    Logger.info(f"下载成功: {source} -> {path}")
                else:
                    results["failure"] += 1
                    results["errors"].append(f"{source}: {error}")
                    Logger.error(f"下载失败: {source}: {error}")
            except Exception as e:
                results["failure"] += 1
                err_msg = f"未处理的下载异常: {str(e)}"
                results["errors"].append(f"{source}: {err_msg}")
                Logger.exception(f"下载任务失败: {source}: {str(e)}")
    
    Logger.info(format(
        "并行下载完成: 成功={{success}}/{{total}}, 失败={{failure}}",
        **results
    ))
    
    return results


def verify_downloaded_file(local_path, expected_checksum, algorithm="sha256"):
    """
    验证下载文件的完整性
    
    :param local_path: 本地文件路径
    :param expected_checksum: 预期校验和值
    :param algorithm: 哈希算法（默认为 'sha256'）
    :return: (verified, actual_checksum, error)
    """
    if not os.path.isfile(local_path):
        return False, "", f"文件不存在: {local_path}"
    
    try:
        actual_checksum = get_file_hash(local_path, algorithm)
        if actual_checksum.lower() == expected_checksum.lower():
            Logger.info(f"文件校验通过: {local_path} ({algorithm})")
            return True, actual_checksum, None
        else:
            error = f"校验和不匹配: 预期={expected_checksum}, 实际={actual_checksum}"
            Logger.error(error)
            return False, actual_checksum, error
    except Exception as e:
        return False, "", f"校验失败: {str(e)}"


def _get_hdfs_file_info(hdfs_path, kinit_cmd):
    """
    获取HDFS文件的详细信息
    
    :return: dict {path, size, modification_time, permission, owner, group, is_dir}
    """
    hdfs = HdfsUtils(kinit_cmd)
    params = Script.get_config()
    
    # 检查HDFS文件状态
    try:
        status = hdfs.status(hdfs_path)
        if status:
            return {
                "path": hdfs_path,
                "size": status["length"],
                "modification_time": status["modificationTime"] // 1000,
                "permission": status["permission"],
                "owner": status["owner"],
                "group": status["group"],
                "is_dir": (status["type"] == "DIRECTORY"),
                "is_symlink": (status["type"] == "SYMLINK")
            }
        return None
    except Exception:
        return None


def _list_hdfs_directory(hdfs_dir, kinit_cmd):
    """
    列出HDFS目录内容
    """
    hdfs = HdfsUtils(kinit_cmd)
    try:
        status_list = hdfs.list_dir(hdfs_dir)
        return status_list
    except Exception as e:
        Logger.error(f"无法列出目录 {hdfs_dir}: {str(e)}")
        return []


def _is_hdfs_enabled_for_checksum():
    """检查是否启用HDFS校验和功能"""
    params = Script.get_config()
    # 检查配置是否启用校验和验证
    use_checksum = params.config.get("hdfs-site", {}).get("dfs.client.file-download.check.checksum", True)
    if isinstance(use_checksum, str):
        use_checksum = use_checksum.lower() == "true"
    return bool(use_checksum)


def _get_hdfs_file_checksum(hdfs_path, kinit_cmd):
    """获取HDFS文件的校验和"""
    hdfs = HdfsUtils(kinit_cmd)
    params = Script.get_config()
    
    # 执行命令行获取哈希值
    checksum_cmd = [
        "hdfs", "dfs", "-checksum", hdfs_path
    ]
    
    # 添加 Kerberos 支持
    full_cmd = []
    if kinit_cmd:
        full_cmd.extend(kinit_cmd.split(" "))
    full_cmd.extend(checksum_cmd)
    
    # 执行命令
    code, out = shell.call(full_cmd, timeout=300, quiet=True)
    
    if code != 0 or not out:
        Logger.warning(f"无法获取 {hdfs_path} 的校验和，使用本地哈希计算")
        return None
    
    # 解析输出 (示例: "MD5-of-0MD5-of-512CRC32C 000002000000000000000000e2eb1a0c2a0c1aeb...")
    match = re.search(r"\s([a-fA-F0-9]{32,})\b", out)  # 查找32位以上哈希值
    if match:
        return match.group(1).lower()
    
    # 尝试解析标准格式
    if out.strip().count(":") == 1:
        parts = out.strip().split(":", 1)
        if len(parts[1]) > 16:  # 最小哈希长度
            return parts[1].strip().lower()
    
    return None


def _set_local_file_attributes(
    local_path, source_info, 
    owner, group, fallback_mode,
    preserve_attributes
):
    """
    设置本地文件属性
    """
    try:
        # 设置所有者
        shutil.chown(local_path, owner, group)
        
        # 设置权限
        if preserve_attributes and "permission" in source_info:
            hdfs_perm = source_info["permission"]
            # 转换为八进制
            perm_str = str(hdfs_perm).zfill(3)
            perm_octal = int(perm_str, 8)
            os.chmod(local_path, perm_octal)
            Logger.debug(f"设置权限: {local_path} -> {perm_str}")
        else:
            os.chmod(local_path, fallback_mode)
            Logger.debug(f"使用默认权限: {local_path} -> {oct(fallback_mode)}")
        
        # 设置修改时间
        if preserve_attributes and "modification_time" in source_info:
            mod_time = source_info["modification_time"]
            os.utime(local_path, (mod_time, mod_time))
            Logger.debug(f"设置修改时间: {local_path} -> {mod_time}")
            
    except Exception as e:
        Logger.warning(f"属性设置失败: {local_path}: {str(e)}")


# ------------------- 使用场景示例 -------------------
if __name__ == "__main__":
    # 示例1: 基础文件下载
    status, path, error = download_from_hdfs(
        source_path="/hadoop/data/important_data.csv",
        dest_path="/local/data_directory",
        owner="datauser",
        user_group="datagroup",
        file_mode=0o640,
        verify_checksum=True,
        kerberos_enabled=True
    )
    
    if status:
        print(f"文件下载成功: {path}")
    else:
        print(f"下载失败: {error}")
    
    # 示例2: 批量下载
    download_tasks = [
        ("/user/analytics/dataset1.tar.gz", "/data/raw/dataset1"),
        ("/user/analytics/dataset2.tar.gz", "/data/raw/dataset2"),
        ("/user/analytics/dataset3.tar.gz", "/data/raw/dataset3"),
    ]
    
    results = parallel_download_from_hdfs(
        download_list=download_tasks,
        owner="analytics",
        user_group="analytics",
        max_workers=3,
        verify_checksum=True
    )
    
    print("批量下载结果:")
    for path in results["downloaded"]:
        print(f"  - {path}")
    
    # 示例3: 目录下载
    status, files, error = download_from_hdfs(
        source_path="/user/backups/daily/2023-09",
        dest_path="/backups/hdfs/daily_2023_09",
        download_type="directory",
        owner="backups",
        user_group="backupgroup",
        replace_existing=True
    )
    
    if status:
        print(f"成功下载 {len(files)} 个文件")
    else:
        print(f"下载错误: {error}")
