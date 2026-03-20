#!/usr/bin/env python3

import os
import re
import fcntl
import shutil
from typing import List, Dict, Optional, Union, TypedDict
from subprocess import Popen, PIPE, STDOUT
from functools import lru_cache
from resource_management.core.base import Fail
from resource_management.core.providers import Provider
from resource_management.core.logger import Logger
from resource_management.core import shell

# 类型定义
class MountInfo(TypedDict):
    """挂载信息数据字典"""
    device: str
    mount_point: str
    fstype: str
    options: List[str]

class FstabEntry(TypedDict):
    """/etc/fstab条目数据字典"""
    device: str
    mount_point: str
    fstype: str
    options: List[str]
    dump: int
    passno: int

# 常量配置
FSTAB_PATH = "/etc/fstab"
FSTAB_BACKUP_PATH = "/etc/fstab.bak"
MOUNT_TIMEOUT = 60  # 挂载操作超时时间（秒）
MAX_FSTAB_SIZE = 10 * 1024 * 1024  # fstab文件最大尺寸（10MB）
DEFAULT_MOUNT_OPTIONS = ["defaults"]

class MountManager:
    """
    挂载操作管理器
    
    封装挂载相关的系统调用和文件操作，
    提供线程安全的fstab修改和挂载状态查询。
    """
    
    @staticmethod
    @lru_cache(maxsize=1)
    def get_current_mounts() -> List[MountInfo]:
        """
        获取当前系统挂载列表
        
        实现逻辑：
        1. 执行mount命令获取实时挂载信息
        2. 解析命令输出（格式：/dev/sda1 on / type ext4 (rw,barrier=0)）
        3. 提取设备、挂载点、文件系统类型和选项
        
        返回: MountInfo对象列表
        
        异常: 当mount命令执行失败时抛出Fail异常
        """
        Logger.debug("开始获取系统当前挂载列表")
        
        try:
            # 执行mount命令
            proc = Popen(
                "mount", 
                stdout=PIPE, 
                stderr=STDOUT, 
                shell=True, 
                universal_newlines=True,
                timeout=10
            )
            output, _ = proc.communicate()
            
            if proc.returncode != 0:
                raise Fail(f"执行mount命令失败，返回码: {proc.returncode}")
            
            # 解析输出
            mounts = []
            for line in output.strip().split("\n"):
                # 跳过空行
                if not line.strip():
                    continue
                
                # 按空格分割，最多分6个字段
                parts = line.split(" ", 5)
                
                # 验证格式：设备 on 挂载点 type 类型 (选项)
                if len(parts) >= 6 and parts[1] == "on" and parts[3] == "type":
                    mount_info: MountInfo = {
                        "device": parts[0],
                        "mount_point": parts[2],
                        "fstype": parts[4],
                        "options": parts[5][1:-1].split(",") if len(parts[5]) >= 2 else []
                    }
                    mounts.append(mount_info)
            
            Logger.debug(f"成功获取 {len(mounts)} 个挂载点信息")
            return mounts
            
        except subprocess.TimeoutExpired:
            raise Fail("执行mount命令超时")
        except Exception as e:
            raise Fail(f"解析mount命令输出失败: {str(e)}")
    
    @staticmethod
    @lru_cache(maxsize=1)
    def get_fstab_entries() -> List[FstabEntry]:
        """
        获取/etc/fstab配置条目
        
        实现逻辑：
        1. 读取并解析/etc/fstab文件
        2. 跳过注释行和空行
        3. 验证每行6个字段的格式
        4. 提取设备、挂载点、文件系统类型、选项、dump和passno
        
        返回: FstabEntry对象列表
        
        异常: 当fstab文件不存在、无法读取或格式错误时抛出Fail异常
        """
        Logger.debug(f"开始读取配置文件: {FSTAB_PATH}")
        
        if not os.path.exists(FSTAB_PATH):
            raise Fail(f"配置文件不存在: {FSTAB_PATH}")
        
        if os.path.getsize(FSTAB_PATH) > MAX_FSTAB_SIZE:
            raise Fail(f"配置文件过大（>{MAX_FSTAB_SIZE}字节）: {FSTAB_PATH}")
        
        try:
            entries = []
            with open(FSTAB_PATH, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    # 移除注释并去除首尾空白
                    clean_line = line.split("#", 1)[0].strip()
                    
                    # 跳过空行
                    if not clean_line:
                        continue
                    
                    # 使用正则表达式分割（处理多个空白字符）
                    parts = re.split(r"\s+", clean_line)
                    
                    # 验证字段数量（必须6个字段）
                    if len(parts) != 6:
                        Logger.warning(
                            f"跳过格式错误的行（行号 {line_num}）: {clean_line}"
                        )
                        continue
                    
                    try:
                        entry: FstabEntry = {
                            "device": parts[0],
                            "mount_point": parts[1],
                            "fstype": parts[2],
                            "options": parts[3].split(",") if parts[3] else [],
                            "dump": int(parts[4]),
                            "passno": int(parts[5])
                        }
                        entries.append(entry)
                    except ValueError as e:
                        Logger.warning(
                            f"跳过数值转换失败的行（行号 {line_num}）: {str(e)}"
                        )
            
            Logger.debug(f"成功解析 {len(entries)} 个fstab配置条目")
            return entries
            
        except IOError as e:
            raise Fail(f"读取配置文件失败 {FSTAB_PATH}: {str(e)}")
        except Exception as e:
            raise Fail(f"解析配置文件失败: {str(e)}")
    
    @staticmethod
    def backup_fstab() -> str:
        """
        备份/etc/fstab文件
        
        实现逻辑：
        1. 创建带时间戳的备份文件
        2. 保留文件权限和属性
        
        返回: 备份文件路径
        
        异常: 当备份失败时抛出Fail异常
        """
        if not os.path.exists(FSTAB_PATH):
            raise Fail(f"无法备份，源文件不存在: {FSTAB_PATH}")
        
        timestamp = int(time.time())
        backup_path = f"{FSTAB_BACKUP_PATH}.{timestamp}"
        
        try:
            shutil.copy2(FSTAB_PATH, backup_path)
            Logger.info(f"成功创建fstab备份: {backup_path}")
            return backup_path
        except Exception as e:
            raise Fail(f"备份fstab失败: {str(e)}")
    
    @staticmethod
    def add_fstab_entry(entry: FstabEntry) -> None:
        """
        添加条目到/etc/fstab
        
        实现逻辑：
        1. 创建备份
        2. 使用文件锁防止并发修改
        3. 验证条目不重复
        4. 追加到文件末尾
        
        参数: entry - FstabEntry对象
        
        异常: 当写入失败或条目已存在时抛出Fail异常
        """
        # 检查条目是否已存在
        existing_entries = MountManager.get_fstab_entries()
        for existing in existing_entries:
            if existing["mount_point"] == entry["mount_point"]:
                raise Fail(
                    f"挂载点已存在于fstab: {entry['mount_point']}"
                )
        
        # 创建备份
        backup_path = MountManager.backup_fstab()
        
        # 准备写入内容
        options_str = ",".join(entry["options"] or DEFAULT_MOUNT_OPTIONS)
        fstab_line = (
            f"{entry['device']}\t{entry['mount_point']}\t"
            f"{entry['fstype']}\t{options_str}\t"
            f"{entry['dump']}\t{entry['passno']}\n"
        )
        
        # 使用文件锁安全写入
        try:
            with open(FSTAB_PATH, "a", encoding="utf-8") as f:
                # 获取独占锁
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                f.write(fstab_line)
                # 强制同步到磁盘
                os.fsync(f.fileno())
            
            Logger.info(
                f"成功添加fstab条目: {entry['mount_point']} -> {entry['device']}"
            )
            
        except Exception as e:
            # 恢复备份
            try:
                shutil.copy2(backup_path, FSTAB_PATH)
                Logger.error(f"恢复fstab备份: {backup_path}")
            except:
                Logger.error("恢复fstab备份失败，请手动检查！")
            
            raise Fail(f"写入fstab失败: {str(e)}")
        
        # 清除缓存
        MountManager.get_fstab_entries.cache_clear()
    
    @staticmethod
    def remove_fstab_entry(mount_point: str) -> bool:
        """
        从/etc/fstab移除指定挂载点条目
        
        实现逻辑：
        1. 创建备份
        2. 使用文件锁防止并发修改
        3. 逐行检查并移除匹配条目
        4. 原子替换文件
        
        参数: mount_point - 要移除的挂载点路径
        
        返回: 是否成功移除（True=找到并移除，False=未找到）
        
        异常: 当写入失败时抛出Fail异常
        """
        # 创建备份
        backup_path = MountManager.backup_fstab()
        
        removed = False
        temp_path = f"{FSTAB_PATH}.tmp"
        
        try:
            # 读取原文件并写入临时文件（跳过目标条目）
            with open(FSTAB_PATH, "r", encoding="utf-8") as src, \
                 open(temp_path, "w", encoding="utf-8") as dst:
                
                # 获取独占锁
                fcntl.flock(dst.fileno(), fcntl.LOCK_EX)
                
                for line in src:
                    # 跳过注释和空行
                    if not line.strip() or line.strip().startswith("#"):
                        dst.write(line)
                        continue
                    
                    # 检查是否为要移除的挂载点
                    parts = re.split(r"\s+", line.split("#", 1)[0].strip())
                    if len(parts) >= 2 and parts[1] == mount_point:
                        removed = True
                        Logger.debug(f"移除fstab条目: {mount_point}")
                        continue
                    
                    dst.write(line)
                
                dst.flush()
                os.fsync(dst.fileno())
            
            # 原子替换
            os.replace(temp_path, FSTAB_PATH)
            
            if removed:
                Logger.info(f"成功移除fstab条目: {mount_point}")
            
            # 清除缓存
            MountManager.get_fstab_entries.cache_clear()
            return removed
            
        except Exception as e:
            # 恢复备份
            try:
                shutil.copy2(backup_path, FSTAB_PATH)
                Logger.error(f"恢复fstab备份: {backup_path}")
            except:
                Logger.error("恢复fstab备份失败，请手动检查！")
            
            # 清理临时文件
            if os.path.exists(temp_path):
                os.remove(temp_path)
            
            raise Fail(f"移除fstab条目失败: {str(e)}")
    
    @staticmethod
    def validate_device(device: str) -> None:
        """
        验证设备是否存在
        
        参数: device - 设备路径（如 /dev/sda1）
        
        异常: 当设备不存在时抛出Fail异常
        """
        if not device:
            raise Fail("设备路径不能为空")
        
        if not os.path.exists(device):
            raise Fail(f"设备不存在: {device}")
        
        if not os.path.isabs(device):
            raise Fail(f"设备路径必须是绝对路径: {device}")


class MountProvider(Provider):
    """
    挂载资源Provider
    
    提供完整的文件系统挂载管理功能：
    • 动态挂载/卸载文件系统
    • 管理/etc/fstab自动挂载配置
    • 验证设备存在性和挂载点有效性
    • 支持多种文件系统类型和挂载选项
    • 提供挂载状态查询
    
    使用示例：
        mount = MountProvider()
        mount.resource.device = "/dev/sdb1"
        mount.resource.mount_point = "/data"
        mount.resource.fstype = "ext4"
        mount.resource.options = ["rw", "noatime"]
        mount.action_mount()
    """
    
    def action_mount(self) -> None:
        """
        挂载文件系统操作
        
        执行流程：
        1. 验证设备存在性
        2. 创建挂载点目录（如果不存在）
        3. 检查是否已挂载（避免重复挂载）
        4. 构建mount命令并执行
        5. 验证挂载结果
        
        异常: 当设备不存在、挂载点创建失败或挂载失败时抛出Fail异常
        """
        resource = self.resource
        Logger.info(f"开始挂载文件系统: {resource.device} -> {resource.mount_point}")
        
        # 验证设备
        MountManager.validate_device(resource.device)
        
        # 创建挂载点目录
        if not os.path.exists(resource.mount_point):
            Logger.info(f"创建挂载点目录: {resource.mount_point}")
            os.makedirs(resource.mount_point, mode=0o755, exist_ok=True)
        
        # 检查是否已挂载
        if self._is_mounted():
            Logger.debug(f"{resource.mount_point} 已挂载，跳过")
            return
        
        # 构建mount命令
        args = ["mount"]
        if resource.fstype:
            args += ["-t", resource.fstype]
        
        # 处理挂载选项
        options = resource.options.copy() if resource.options else []
        if resource.options:
            # 验证选项格式
            for opt in options:
                if not isinstance(opt, str) or "," in opt:
                    raise Fail(f"无效的挂载选项格式: {opt}")
            args += ["-o", ",".join(options)]
        
        args.append(resource.device)
        args.append(resource.mount_point)
        
        Logger.debug(f"执行挂载命令: {' '.join(args)}")
        
        # 执行挂载
        try:
            shell.checked_call(args, timeout=MOUNT_TIMEOUT)
            Logger.info(f"成功挂载: {resource.device} 到 {resource.mount_point}")
        except Exception as e:
            raise Fail(f"挂载失败 {resource.device} -> {resource.mount_point}: {str(e)}")
        
        # 验证挂载结果
        if not self._is_mounted():
            raise Fail("挂载验证失败，挂载点未在系统中显示")
    
    def action_umount(self) -> None:
        """
        卸载文件系统操作
        
        执行流程：
        1. 检查挂载状态
        2. 执行umount命令
        3. 验证卸载结果
        
        注意：不会删除挂载点目录
        
        异常: 当卸载失败时抛出Fail异常
        """
        resource = self.resource
        Logger.info(f"开始卸载挂载点: {resource.mount_point}")
        
        if not self._is_mounted():
            Logger.debug(f"{resource.mount_point} 未挂载，跳过")
            return
        
        try:
            shell.checked_call(["umount", resource.mount_point], timeout=MOUNT_TIMEOUT)
            Logger.info(f"成功卸载: {resource.mount_point}")
        except Exception as e:
            raise Fail(f"卸载失败 {resource.mount_point}: {str(e)}")
        
        # 验证卸载结果
        if self._is_mounted():
            raise Fail("卸载验证失败，挂载点仍然显示为已挂载")
    
    def action_enable(self) -> None:
        """
        启用开机自动挂载（添加到fstab）
        
        执行流程：
        1. 验证必需参数（device, fstype）
        2. 检查是否已启用
        3. 构建fstab条目
        4. 添加到/etc/fstab
        
        异常: 当参数缺失或已存在时抛出Fail异常
        """
        resource = self.resource
        Logger.info(f"启用开机自动挂载: {resource.mount_point}")
        
        # 验证必需参数
        if not resource.device:
            raise Fail("设备路径不能为空（device参数）")
        if not resource.fstype:
            raise Fail("文件系统类型不能为空（fstype参数）")
        
        # 检查是否已启用
        if self._is_enabled():
            Logger.debug(f"{resource.mount_point} 已启用自动挂载")
            return
        
        # 构建fstab条目
        entry: FstabEntry = {
            "device": resource.device,
            "mount_point": resource.mount_point,
            "fstype": resource.fstype,
            "options": resource.options or DEFAULT_MOUNT_OPTIONS,
            "dump": resource.dump,
            "passno": resource.passno
        }
        
        # 添加到fstab
        MountManager.add_fstab_entry(entry)
        Logger.info(f"成功启用自动挂载: {resource.mount_point}")
    
    def action_disable(self) -> None:
        """
        禁用开机自动挂载（从fstab移除）
        
        执行流程：
        1. 检查是否已启用
        2. 从/etc/fstab移除条目
        3. 可选：卸载当前挂载（根据resource.unmount_on_disable）
        
        异常: 当移除失败时抛出Fail异常
        """
        resource = self.resource
        Logger.info(f"禁用开机自动挂载: {resource.mount_point}")
        
        if not self._is_enabled():
            Logger.debug(f"{resource.mount_point} 未启用自动挂载")
            return
        
        # 从fstab移除
        removed = MountManager.remove_fstab_entry(resource.mount_point)
        
        if removed:
            Logger.info(f"成功禁用自动挂载: {resource.mount_point}")
        else:
            Logger.warning(f"fstab中未找到条目: {resource.mount_point}")
        
        # 根据配置决定是否同时卸载
        if getattr(resource, "unmount_on_disable", False):
            Logger.info("同时执行卸载操作")
            self.action_umount()
    
    def _is_mounted(self) -> bool:
        """
        检查挂载点是否已挂载
        
        实现逻辑：
        1. 检查挂载点目录是否存在
        2. 查询当前系统挂载列表
        3. 匹配挂载点路径
        
        返回: True=已挂载, False=未挂载
        
        异常: 当设备不存在时抛出Fail异常
        """
        resource = self.resource
        
        # 检查挂载点目录
        if not os.path.exists(resource.mount_point):
            return False
        
        # 检查设备是否存在
        if resource.device and not os.path.exists(resource.device):
            raise Fail(f"设备不存在: {resource.device}")
        
        # 查询当前挂载
        mounts = MountManager.get_current_mounts()
        for mount in mounts:
            if mount["mount_point"] == resource.mount_point:
                # 验证设备匹配（如果提供了设备信息）
                if resource.device and mount["device"] != resource.device:
                    Logger.warning(
                        f"挂载点 {resource.mount_point} 已挂载到不同设备: "
                        f"期望 {resource.device}，实际 {mount['device']}"
                    )
                return True
        
        return False
    
    def _is_enabled(self) -> bool:
        """
        检查挂载点是否已配置开机自动挂载
        
        实现逻辑：
        查询/etc/fstab中是否存在该挂载点配置
        
        返回: True=已配置, False=未配置
        """
        resource = self.resource
        entries = MountManager.get_fstab_entries()
        
        for entry in entries:
            if entry["mount_point"] == resource.mount_point:
                # 验证配置一致性
                if resource.device and entry["device"] != resource.device:
                    Logger.warning(
                        f"fstab中挂载点 {resource.mount_point} 配置的设备与期望不符: "
                        f"fstab={entry['device']}, 期望={resource.device}"
                    )
                return True
        
        return False


# 辅助函数（保持向后兼容）
def get_mounted() -> List[MountInfo]:
    """
    获取当前挂载列表（兼容函数）
    
    注意：建议使用 MountManager.get_current_mounts()
    """
    return MountManager.get_current_mounts()


def get_fstab() -> List[FstabEntry]:
    """
    获取fstab配置（兼容函数）
    
    注意：建议使用 MountManager.get_fstab_entries()
    """
    return MountManager.get_fstab_entries()
