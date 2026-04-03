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

HDFS Tarball Management System
"""

import os
import re
import uuid
import tempfile
from typing import List, Tuple, Optional
from resource_management.libraries.functions.default import default
from resource_management.libraries.functions.format import format
from resource_management.libraries.resources.copy_from_local import CopyFromLocal
from resource_management.libraries.resources.execute_hadoop import ExecuteHadoop
from resource_management.libraries.functions import stack_tools
from resource_management.core.resources.system import Execute
from resource_management.core.exceptions import Fail
from resource_management.core.logger import Logger
from resource_management.core import shell

__all__ = ["copy_tarballs_to_hdfs"]

# Suffix for properties in cluster-env.xml
TAR_SOURCE_SUFFIX = "_tar_source"
TAR_DESTINATION_FOLDER_SUFFIX = "_tar_destination_folder"

# Stack version regex pattern with support for build numbers or package versions
STACK_VERSION_PATTERN = r"(\d{1,4}(?:\.\d+){1,4}(?:-\d+)?)"
# Tarball prefixes supported by the system
SUPPORTED_TARBALL_PREFIXES = {"tez", "hive", "mr", "pig"}


def _get_tar_properties(tarball_prefix: str) -> Tuple[Optional[str], Optional[str]]:
    """
    获取tarball的来源路径和目标文件夹配置
    
    :param tarball_prefix: tarball前缀 (tez, hive, mr, pig)
    :return: (source_path, destination_folder) 元组
    """
    if tarball_prefix.lower() not in SUPPORTED_TARBALL_PREFIXES:
        Logger.warning(f"不支持的tarball前缀: {tarball_prefix}")
        return None, None
    
    prefix_key = tarball_prefix.lower()
    tar_source_prop = f"configurations/cluster-env/{prefix_key}{TAR_SOURCE_SUFFIX}"
    tar_dest_prop = f"configurations/cluster-env/{prefix_key}{TAR_DESTINATION_FOLDER_SUFFIX}"
    
    component_tar_source_file = default(tar_source_prop, None)
    component_tar_destination_folder = default(tar_dest_prop, None)
    
    if not component_tar_source_file or not component_tar_destination_folder:
        Logger.warning(f"未在cluster-env.xml中找到{tarball_prefix}的tar文件源路径和目标文件夹属性")
        return None, None
    
    if not os.path.isabs(component_tar_source_file):
        Logger.warning(f"tar文件路径 {component_tar_source_file} 不是绝对路径")
        return None, None
    
    # 确保目标路径以斜杠结尾
    if not component_tar_destination_folder.endswith("/"):
        component_tar_destination_folder += "/"
    
    return component_tar_source_file, component_tar_destination_folder


def _get_stack_version(stack_selector_path: str, component_name: str) -> Optional[str]:
    """
    使用stack selector工具获取组件的堆栈版本
    
    :param stack_selector_path: stack selector可执行文件路径
    :param component_name: 组件名称
    :return: 堆栈版本字符串 (例如: "2.4.0.0-1234")
    """
    try:
        cmd = f"{stack_selector_path} status {component_name}"
        return_code, output = shell.call(cmd, logoutput=False, timeout=30)
        
        if return_code != 0:
            Logger.error(f"执行命令失败: {cmd} (状态码={return_code})")
            return None
            
        # 从输出中提取版本号
        match = re.search(STACK_VERSION_PATTERN, output)
        return match.group(1) if match else None
    except Exception as e:
        Logger.error(f"获取堆栈版本时出错: {str(e)}")
        return None


def _hdfs_file_exists(file_path: str, hdfs_params: dict) -> bool:
    """
    检查HDFS文件是否存在
    
    :param file_path: HDFS文件路径
    :param hdfs_params: Hadoop相关参数
    :return: 文件是否存在
    """
    ls_command = format("fs -ls {file_path}")
    
    try:
        ExecuteHadoop(
            ls_command,
            user=hdfs_params["user"],
            bin_dir=hdfs_params["bin_dir"],
            conf_dir=hdfs_params["conf_dir"],
            logoutput=True
        )
        return True
    except Fail:
        return False


def _copy_tarball_to_hdfs(
    source_path: str, 
    dest_path: str, 
    file_owner: str, 
    group_owner: str, 
    hdfs_params: dict,
    kinit_cmd: Optional[str] = None
) -> int:
    """
    将单个tarball文件复制到HDFS
    
    :param source_path: 本地tarball路径
    :param dest_path: HDFS目标路径
    :param file_owner: 文件所有者
    :param group_owner: 文件组
    :param hdfs_params: Hadoop相关参数
    :param kinit_cmd: kinit命令(安全环境需要)
    :return: 0表示成功，1表示失败
    """
    import params
    
    try:
        # 创建目标目录
        dest_dir = os.path.dirname(dest_path)
        params.HdfsDirectory(
            dest_dir,
            action="create",
            owner=file_owner,
            hdfs_user=hdfs_params["user"],
            mode=0o555,
        )
        
        # 生成唯一的目标文件名避免冲突
        unique_name = f"{os.path.basename(dest_path)}.{str(uuid.uuid4())[:8]}"
        temp_dest = os.path.join(dest_dir, unique_name)
        
        # 复制文件到临时位置
        CopyFromLocal(
            source_path,
            mode=0o444,
            owner=file_owner,
            group=group_owner,
            user=hdfs_params["user"],
            dest_dir=dest_dir,
            dest_file=unique_name,
            kinnit_if_needed=kinit_cmd,
            hdfs_user=hdfs_params["user"],
            hadoop_bin_dir=hdfs_params["bin_dir"],
            hadoop_conf_dir=hdfs_params["conf_dir"],
        )
        
        # 移动到最终位置
        rename_cmd = format("fs -mv {temp_dest} {dest_path}")
        ExecuteHadoop(
            rename_cmd,
            user=hdfs_params["user"],
            bin_dir=hdfs_params["bin_dir"],
            conf_dir=hdfs_params["conf_dir"],
        )
        
        Logger.info(f"成功复制文件: {source_path} -> {dest_path}")
        return 0
    except Exception as e:
        Logger.error(f"复制文件失败: {source_path} -> {dest_path}, 错误: {str(e)}")
        return 1


def copy_tarballs_to_hdfs(
    tarball_prefix: str,
    stack_component: str,
    component_user: str,
    file_owner: str,
    group_owner: str,
    ignore_sysprep: bool = False
) -> int:
    """
    将本地tarball文件复制到HDFS
    
    :param tarball_prefix: tarball前缀(tez, hive, mr, pig)
    :param stack_component: 相关堆栈组件名称
    :param component_user: Hadoop命令执行用户
    :param file_owner: HDFS文件所有者
    :param group_owner: HDFS文件所属组
    :param ignore_sysprep: 忽略sysprep指令
    :return: 0-成功, 1-失败
    """
    import params
    
    # 检查sysprep状态
    if not ignore_sysprep and getattr(params, "host_sys_prepped", False):
        Logger.info(f"Sysprepped主机 - 跳过{stack_component}的{tarball_prefix} tarball复制")
        return 0
    
    # 验证堆栈版本
    if not hasattr(params, "stack_version_formatted") or not params.stack_version_formatted:
        Logger.error("缺少stack_version_formatted参数")
        return 1
    
    # 获取tarball配置属性
    tar_source, tar_dest = _get_tar_properties(tarball_prefix)
    if not tar_source or not tar_dest:
        Logger.error(f"无法获取{tarball_prefix}的tarball配置")
        return 1
    
    # 验证tarball文件是否存在
    if not os.path.exists(tar_source):
        Logger.error(f"源tarball文件不存在: {tar_source}")
        return 1
    
    # 获取组件版本
    _, stack_selector_path, _ = stack_tools.get_stack_tool(stack_tools.STACK_SELECTOR_NAME)
    stack_version = _get_stack_version(stack_selector_path, stack_component)
    
    if not stack_version:
        Logger.error(f"无法获取{stack_component}的堆栈版本")
        return 1
    
    # 构建HDFS目标路径
    file_name = os.path.basename(tar_source)
    destination_path = os.path.join(tar_dest, file_name)
    destination_path = destination_path.replace("{{ stack_version_formatted }}", stack_version)
    
    # Hadoop配置参数
    hdfs_params = {
        "user": params.hdfs_user,
        "bin_dir": params.hadoop_bin_dir,
        "conf_dir": params.hadoop_conf_dir
    }
    
    # Kerberos权限配置
    kinit_cmd = ""
    if getattr(params, "security_enabled", False):
        kinit_cmd = format("{kinit_path_local} -kt {hdfs_user_keytab} {hdfs_principal_name};")
    
    # 执行kinit(如需要)
    if kinit_cmd:
        Execute(kinit_cmd, user=component_user, path="/bin")
    
    # 仅在HDFS文件不存在时复制
    if _hdfs_file_exists(destination_path, hdfs_params):
        Logger.info(f"HDFS文件已存在: {destination_path} - 跳过复制")
        return 0
    
    # 执行复制操作
    return _copy_tarball_to_hdfs(
        source_path=tar_source,
        dest_path=destination_path,
        file_owner=file_owner,
        group_owner=group_owner,
        hdfs_params=hdfs_params,
        kinit_cmd=kinit_cmd
    )

