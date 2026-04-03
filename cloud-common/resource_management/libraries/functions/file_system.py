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

Enhanced Mount Point Management System
"""

__all__ = [
    "get_and_cache_mount_points", 
    "get_mount_point_for_dir",
    "validate_disk_space",
    "list_mount_usage",
    "get_largest_mount_point"
]

import os
import stat
import sys
import logging
import functools
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from resource_management.core.logger import Logger
from resource_management.core.providers import mount
from resource_management.core.exceptions import FileSystemError
from resource_management.core.security import secure_path

# 缓存初始化
_mounts_cache = None
_sorted_mount_points = None
_last_refresh_time = 0.0
CACHE_TTL = 300  # 5分钟缓存时间（秒）

# 安全审计日志
audit_logger = logging.getLogger('mount_audit')
audit_logger.addHandler(logging.FileHandler('/var/log/mount_audit.log'))
audit_logger.setLevel(logging.INFO)

def get_and_cache_mount_points(refresh: bool = False, secure: bool = True) -> List[Dict]:
    """
    获取并缓存挂载点信息（带安全检测和性能优化）
    
    :param refresh: 是否强制刷新缓存
    :param secure: 是否执行安全路径检测
    :return: 挂载点字典列表
    """
    global _mounts_cache, _sorted_mount_points, _last_refresh_time
    
    # 检查缓存是否有效
    if (not refresh and 
        _mounts_cache is not None and 
        (time.time() - _last_refresh_time) < CACHE_TTL):
        Logger.debug("Returning cached mount points")
        return _mounts_cache
    
    Logger.info("Refreshing mount point information")
    
    try:
        # 安全获取挂载信息
        raw_mounts = mount.get_mounted()
        processed_mounts = []
        trusted_paths = set()
        
        for m in raw_mounts:
            try:
                if not m["mount_point"]:
                    Logger.warning(f"Skipping invalid mount point: {str(m)}")
                    continue
                    
                # 标准化路径
                mount_point = m["mount_point"].rstrip()
                # 对路径进行安全检测（如果启用）
                if secure:
                    secure_path(mount_point, is_directory=True, check_symlinks=True)
                
                # 检测潜在的路径遍历攻击
                if ".." in mount_point or not mount_point.startswith("/"):
                    Logger.warning(f"Potential risky mount point detected: {mount_point}")
                    continue
                
                # 只接受真实的文件系统挂载点
                if not os.path.ismount(mount_point):
                    Logger.debug(f"Skipping non-mount point: {mount_point}")
                    continue
                
                # 添加磁盘空间信息
                m["device"] = m.get("device", "unknown")
                m["mount_point"] = mount_point
                m["free_space"] = _get_free_space(mount_point)
                m["total_space"] = _get_total_space(mount_point)
                
                # 检查重复挂载点
                if mount_point in trusted_paths:
                    Logger.warning(f"Duplicate mount point: {mount_point}")
                    continue
                
                trusted_paths.add(mount_point)
                processed_mounts.append(m)
                
            except (ValueError, OSError) as e:
                Logger.error(f"Skipping problematic mount: {str(e)}")
        
        # 按路径深度排序
        processed_mounts.sort(
            key=lambda x: len(x["mount_point"].split(os.path.sep)),
            reverse=True
        )
        
        # 准备排序后的挂载点列表用于快速搜索
        _sorted_mount_points = [m["mount_point"] for m in processed_mounts]
        _mounts_cache = processed_mounts
        _last_refresh_time = time.time()
        
        # 安全审计
        _log_mount_audit(processed_mounts)
        
        Logger.info(f"Detected {len(processed_mounts)} valid mount points")
        return processed_mounts
        
    except Exception as e:
        Logger.critical(f"Failed to fetch mount points: {str(e)}")
        # 安全回退机制
        if _mounts_cache is not None:
            Logger.warning("Returning stale cache due to failure")
            return _mounts_cache
        raise FileSystemError(f"Unable to retrieve mount points: {str(e)}")


def get_mount_point_for_dir(dir_path: str, require_existence: bool = True) -> Optional[str]:
    """
    高级挂载点查找算法
    
    :param dir_path: 待检查的目录路径
    :param require_existence: 是否要求目录路径必须存在
    :return: 最匹配的挂载点路径（如果没有匹配则返回None）
    """
    if not dir_path or not dir_path.strip():
        Logger.info("Empty directory path received, returning None")
        return None
    
    # 清理和标准化输入路径
    norm_dir = os.path.normpath(dir_path.strip())
    Logger.debug(f"Finding mount point for directory: {norm_dir}")
    
    # 验证路径安全性
    try:
        secure_path(norm_dir, is_directory=True, check_symlinks=True)
    except FileSystemError as e:
        Logger.error(f"Security violation for path '{norm_dir}': {str(e)}")
        return None
    
    # 如果路径不存在且不强制要求存在，则使用其父路径
    if not os.path.exists(norm_dir):
        if require_existence:
            Logger.warning(f"Directory does not exist: {norm_dir}")
            return None
        else:
            # 回退到父路径搜索
            parent_dir = os.path.dirname(norm_dir)
            if parent_dir == norm_dir:  # 已经是根目录
                return "/"
            return get_mount_point_for_dir(parent_dir, require_existence)
    
    # 获取实际文件系统的挂载点
    try:
        stat_info = os.stat(norm_dir)
        actual_dev = stat_info.st_dev
        for m in get_and_cache_mount_points():
            if os.stat(m["mount_point"]).st_dev == actual_dev:
                Logger.info(f"Found direct mount match: {m['mount_point']} for {norm_dir}")
                return m["mount_point"]
    except OSError as e:
        Logger.warning(f"Cannot compare device IDs for {norm_dir}: {str(e)}")
    
    # 回退到路径匹配方法
    return _find_best_mount_match(norm_dir)


def _find_best_mount_match(path: str) -> Optional[str]:
    """高效查找最佳挂载点匹配"""
    # 使用预排序列表进行优化搜索
    mounts = _sorted_mount_points or [m["mount_point"] for m in get_and_cache_mount_points()]
    norm_path = os.path.join(path, "")
    
    # 按长度递减顺序检查（最深层优先）
    for mount in mounts:
        if norm_path.startswith(os.path.join(mount, "")):
            Logger.debug(f"Found best mount match: {mount} for {path}")
            return mount
    
    # 没有找到匹配，返回根目录
    if path.startswith('/'):
        Logger.info(f"No specific mount found for {path}, defaulting to root")
        return "/"
    
    return None


def validate_disk_space(path: str, min_space: int, min_inodes: int = 0) -> Tuple[bool, Dict]:
    """
    验证挂载点磁盘空间
    
    :param path: 存储路径
    :param min_space: 需要的最小磁盘空间（字节）
    :param min_inodes: 需要的最小inode数
    :return: (是否满足要求, 详细磁盘信息)
    """
    mount_point = get_mount_point_for_dir(path)
    if not mount_point:
        return False, {"error": "Invalid path or mount point"}
    
    try:
        stats = os.statvfs(mount_point)
        free_space = stats.f_bfree * stats.f_frsize
        free_inodes = stats.f_ffree
        
        result = {
            "path": path,
            "mount_point": mount_point,
            "free_space": free_space,
            "free_inodes": free_inodes,
            "sufficient_space": free_space >= min_space,
            "sufficient_inodes": not min_inodes or free_inodes >= min_inodes
        }
        
        audit_logger.info(f"Disk check for {path}: {json.dumps(result)}")
        return (result["sufficient_space"] and result["sufficient_inodes"], result)
        
    except OSError as e:
        Logger.error(f"Failed to check disk space: {str(e)}")
        return False, {"error": str(e)}


def get_largest_mount_point(min_size: int = 0, mount_type: str = '') -> Optional[Dict]:
    """
    获取最大可用空间的挂载点
    
    :param min_size: 最小空间要求（字节）
    :param mount_type: 筛选特定文件系统类型（如 'xfs', 'ext4'）
    :return: 挂载点信息字典
    """
    candidates = []
    for m in get_and_cache_mount_points():
        # 筛选文件系统类型
        if mount_type and m.get("type", "").lower() != mount_type.lower():
            continue
            
        if min_size and m.get("total_space", 0) < min_size:
            continue
            
        # 根据可用空间和总空间排序
        score = m.get("free_space", 0) * 0.7 + m.get("total_space", 0) * 0.3
        candidates.append((score, m))
    
    if not candidates:
        Logger.warning("No suitable mount points found")
        return None
        
    # 选择最高得分的候选挂载点
    return max(candidates, key=lambda x: x[0])[1]


def list_mount_usage(sort_by: str = 'free_space') -> List[Dict]:
    """
    获取磁盘使用情况报表
    
    :param sort_by: 排序字段（free_space | total_space | mount_point）
    :return: 带空间信息的挂载点列表
    """
    mounts = get_and_cache_mount_points()
    
    # 计算使用率
    for m in mounts:
        total = m.get("total_space", 1)  # 避免除以零
        free = m.get("free_space", 0)
        m["used_space"] = total - free
        m["usage_percent"] = int((m["used_space"] / total) * 100) if total > 0 else 0
    
    # 排序选项
    sort_fields = {
        'free_space': lambda x: x["free_space"],
        'usage': lambda x: x["usage_percent"],
        'size': lambda x: x["total_space"],
        'path': lambda x: x["mount_point"]
    }
    
    key_func = sort_fields.get(sort_by, sort_fields['free_space'])
    return sorted(mounts, key=key_func, reverse=sort_by == 'free_space')


def _get_free_space(path: str) -> int:
    """获取可用空间（字节）"""
    try:
        statvfs = os.statvfs(path)
        return statvfs.f_bfree * statvfs.f_frsize
    except OSError:
        return -1  # 未知


def _get_total_space(path: str) -> int:
    """获取总空间（字节）"""
    try:
        statvfs = os.statvfs(path)
        return statvfs.f_blocks * statvfs.f_frsize
    except OSError:
        return -1  # 未知


def _log_mount_audit(mounts: List[Dict]):
    """记录挂载点安全审计日志"""
    alert_rules = {
        'over_75': {'limit': 75, 'matches': []},
        'over_90': {'limit': 90, 'matches': []},
        'high_risk': {'limit': 95, 'matches': []}
    }
    
    for m in mounts:
        usage = m.get("usage_percent", 0)
        if usage > 95: key = 'high_risk'
        elif usage > 90: key = 'over_90'
        elif usage > 75: key = 'over_75'
        else: continue
        
        alert_rules[key]['matches'].append({
            'mount': m["mount_point"],
            'usage': usage,
            'free': m.get("free_space", 0)
        })
    
    # 生成告警报告
    if any(len(v['matches']) > 0 for v in alert_rules.values()):
        audit_logger.warning("Disk space alert triggered", extra={
            'disk_alerts': {k: v['matches'] for k, v in alert_rules.items()}
        })


def mount_point_cache_invalidator():
    """定期自动缓存更新器（使用线程或定时任务调用）"""
    while True:
        get_and_cache_mount_points(refresh=True)
        time.sleep(CACHE_TTL * 0.8)  # 稍早于TTL过期


# 安全防护装饰器
def validate_path(func):
    """路径验证装饰器防止不安全输入"""
    @functools.wraps(func)
    def wrapper(path, *args, **kwargs):
        try:
            secure_path(path)
            return func(path, *args, **kwargs)
        except FileSystemError as e:
            Logger.error(f"Path security violation: {str(e)}")
            return None
    return wrapper
