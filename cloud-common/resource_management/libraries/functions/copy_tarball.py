#!/usr/bin/env python3
"""
Licensed to the Apache Software Foundation (ASF) under one or more
contributor license agreements.  See the NOTICE file distributed with
this work for additional information regarding copyright ownership.
The ASF licenses this file to you under the Apache License, Version 2.0
(the "License"); you may not use this file except in compliance with
the License.  You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Enhanced Tarball Management for Hadoop Ecosystem Components
"""

import os
import re
import shutil
import tempfile
import logging
import json
import uuid
from collections import defaultdict
from functools import partial
from typing import Dict, Tuple, List, Callable, Optional, Pattern, Any
from pathlib import Path

from resource_management.libraries.script.script import Script
from resource_management.core import shell, sudo
from resource_management.core.logger import Logger
from resource_management.core.exceptions import Fail
from resource_management.core.resources.system import File, Directory, Execute
from resource_management.libraries.functions import (
    stack_tools,
    stack_features,
    stack_select,
    component_version,
    tar_archive,
    lzo_utils
)
from resource_management.libraries.functions.default import default
from resource_management.libraries.functions.version import format_stack_version

# Setup enhanced logger
TARBALL_LOGGER = logging.getLogger("tarball_manager")
TARBALL_LOGGER.setLevel(logging.INFO)

# Constants
STACK_NAME_PAT = re.compile("{{ stack_name }}")
STACK_ROOT_PAT = re.compile("{{ stack_root }}")
STACK_VER_PAT = re.compile("{{ stack_version }}")
LIB_DIR = "usr/lib"

# File modes for various operations
SAFE_DIR_PERMS = 0o755
TEMP_TARBALL_PERMS = 0o1777
OWNER_WRITE_PERMS = 0o644
READ_ONLY_PERMS = 0o444

# Configuration keys
SYS_PREP_CONFIG = "/cloudLevelParams/host_sys_prepped"
SKIP_TARBALL_COPY_CONFIG = "/configurations/cluster-env/sysprep_skip_copy_tarballs_hdfs"
STACK_VERSION_CONFIG = "/commandParams/version"
STACK_NAME_CONFIG = ""

def get_service_tarball_map(stack_name: str) -> Dict[str, Dict]:
    """动态生�?tarball 配置，支持版本和架构参数"""
    lib_dir = Path(LIB_DIR)
    
    return {
        'yarn': {
            'source': lib_dir / f"{stack_name}/hadoop-yarn/lib/service-dep.tar.gz",
            'dest': f"/{stack_name}/apps/$V/yarn/service-dep.tar.gz",
            'service': 'YARN'
        },
        'tez': {
            'source': lib_dir / f"{stack_name}/tez/lib/tez.tar.gz",
            'dest': f"/{stack_name}/apps/$V/tez/tez.tar.gz",
            'service': 'TEZ',
            'prepare': 'prepare_tez_tarball'
        },
        'tez_hive2': {
            'source': lib_dir / f"{stack_name}/tez_hive2/lib/tez.tar.gz",
            'dest': f"/{stack_name}/apps/$V/tez_hive2/tez.tar.gz",
            'service': 'HIVE'
        },
        'hive': {
            'source': lib_dir / f"{stack_name}/hive/hive.tar.gz",
            'dest': f"/{stack_name}/apps/$V/hive/hive.tar.gz",
            'service': 'HIVE'
        },
        'hadoop_streaming': {
            'source': lib_dir / f"{stack_name}/hadoop-mapreduce/hadoop-streaming.jar",
            'dest': f"/{stack_name}/apps/$V/mapreduce/hadoop-streaming.jar",
            'service': 'MAPREDUCE2'
        },
        'mapreduce': {
            'source': lib_dir / f"{stack_name}/hadoop/mapreduce.tar.gz",
            'dest': f"/{stack_name}/apps/$V/mapreduce/mapreduce.tar.gz",
            'service': 'MAPREDUCE2',
            'prepare': 'prepare_mapreduce_tarball'
        },
        'spark': {
            'source': "/tmp/spark/$N-spark-assembly.jar",
            'dest': f"/{stack_name}/apps/$V/spark/$N-spark-assembly.jar",
            'service': 'SPARK'
        },
        'spark2': {
            'source': "/tmp/spark2/$N-spark2-yarn-archive.tar.gz",
            'dest': f"/{stack_name}/apps/$V/spark2/$N-spark2-yarn-archive.tar.gz",
            'service': 'SPARK2'
        }
    }

SERVICE_TO_CONFIG_MAP = {
    'yarn': 'yarn-env',
    'tez': 'tez-env',
    'hive': 'hive-env',
    'mapreduce': 'hadoop-env',
    'hadoop_streaming': 'mapred-env',
    'tez_hive2': 'hive-env',
    'spark': 'spark-env',
    'spark2': 'spark2-env',
    'spark2hive': 'spark2-env'
}

def get_sysprep_skip_copy_tarballs_hdfs() -> bool:
    """检查集群是否已系统准备并跳�?tarball 复制"""
    host_sys_prepped = default(SYS_PREP_CONFIG, False)
    
    # 如果集群已系统准备，则根据配置决定是否跳�?    if host_sys_prepped:
        return default(SKIP_TARBALL_COPY_CONFIG, False)
    return False

def get_tarball_paths(
    name: str, 
    use_upgrading_version: bool = True,
    custom_source: str = None,
    custom_dest: str = None
) -> Tuple[bool, str, str, Optional[Callable]]:
    """
    为指�?tarball 获取源路径和目标路径
    
    Args:
        name: Tarball 名称 (tez, yarn, spark �?
        use_upgrading_version: 是否在升级时使用目标版本
        custom_source: 自定义源路径覆盖
        custom_dest: 自定义目标路径覆�?        
    Returns:
        元组 (success, source_file, dest_file, prepare_function)
    """
    stack_name = Script.get_stack_name()
    if not stack_name:
        TARBALL_LOGGER.error("无法获取堆栈名称")
        return False, None, None, None
    
    # 获取服务 tarball 配置
    tarball_conf = get_service_tarball_map(stack_name).get(name.lower())
    if not tarball_conf:
        TARBALL_LOGGER.error(f"不支持的 tarball 名称: {name}")
        return False, None, None, None
    
    # 获取当前服务版本
    stack_version = _get_current_service_version(
        service_name=tarball_conf['service'],
        use_upgrading_version=use_upgrading_version
    )
    if not stack_version:
        TARBALL_LOGGER.error(f"无法�?{name} 获取堆栈版本")
        return False, None, None, None
    
    # 获取堆栈根路�?    stack_root = Script.get_stack_root()
    if not stack_root:
        TARBALL_LOGGER.error(f"无法获取堆栈根路�?)
        return False, None, None, None
    
    # 处理路径模板中的变量
    resolved_source = _resolve_path_template(
        tarball_conf['source'] if custom_source is None else custom_source,
        stack_name, stack_root, stack_version
    )
    resolved_dest = _resolve_path_template(
        tarball_conf['dest'] if custom_dest is None else custom_dest,
        stack_name, stack_root, stack_version
    )
    
    # 获取预处理函�?    prep_func_name = tarball_conf.get('prepare')
    prep_func = globals().get(prep_func_name) if prep_func_name else None
    
    return True, resolved_source, resolved_dest, prep_func

def _resolve_path_template(path: str, stack_name: str, stack_root: str, version: str) -> str:
    """解析路径模板中的变量"""
    path = path.replace('$N', stack_name.lower())
    path = path.replace('$R', stack_root.lower())
    path = path.replace('$V', version)
    return path

def _get_current_service_version(service_name: str, use_upgrading_version: bool) -> str:
    """获取服务的当前或升级版本"""
    from resource_management.libraries.functions import upgrade_summary
    
    # 获取基础版本
    version = stack_features.get_stack_feature_version(Script.get_config())
    
    # 如果是升级且需要目标版�?    if use_upgrading_version and Script.in_stack_upgrade() and service_name:
        target_ver = upgrade_summary.get_target_version(
            service_name=service_name, 
            default_version=version
        )
        if target_ver:
            version = target_ver
    
    # 格式化版本号
    formatted_ver = format_stack_version(version)
    
    if not formatted_ver:
        current_ver = stack_select.get_role_component_current_stack_version()
        if service_name and Script.in_stack_upgrade():
            current_ver = upgrade_summary.get_source_version(
                service_name=service_name, 
                default_version=current_ver
            )
        formatted_ver = current_ver or version
    
    TARBALL_LOGGER.info(f"{service_name} 版本确定�? {formatted_ver}")
    return formatted_ver

def prepare_tez_tarball() -> str:
    """准备带有原生库的 Tez tarball"""
    TARBALL_LOGGER.info("准备 Tez tarball...")
    
    # 获取必要的文件路�?    _, mr_source, _, _ = get_tarball_paths('mapreduce')
    _, tez_source, _, _ = get_tarball_paths('tez')
    
    if not mr_source or not os.path.exists(mr_source):
        raise Fail(f"缺少 MapReduce tarball: {mr_source}")
    if not tez_source or not os.path.exists(tez_source):
        raise Fail(f"缺少 Tez tarball: {tez_source}")
    
    # 创建临时目录
    with tempfile.TemporaryDirectory() as temp_dir,\
         tempfile.TemporaryDirectory(prefix='mr-') as mr_extract_dir,\
         tempfile.TemporaryDirectory(prefix='tez-') as tez_extract_dir:
        
        # 设置目录权限
        _set_temp_perms(mr_extract_dir)
        _set_temp_perms(tez_extract_dir)
        
        # 解压 tarball
        TARBALL_LOGGER.info(f"解压 {mr_source} �?{mr_extract_dir}")
        tar_archive.untar_archive(mr_source, mr_extract_dir)
        
        TARBALL_LOGGER.info(f"解压 {tez_source} �?{tez_extract_dir}")
        tar_archive.untar_archive(tez_source, tez_extract_dir)
        
        # 复制原生�?        native_dir_src = os.path.join(mr_extract_dir, "hadoop", "lib", "native")
        native_dir_dest = os.path.join(tez_extract_dir, "lib")
        
        if not os.path.exists(native_dir_src):
            raise Fail(f"缺少原生库目�? {native_dir_src}")
        os.makedirs(native_dir_dest, exist_ok=True)
        
        TARBALL_LOGGER.info(f"复制原生库到 {native_dir_dest}")
        shutil.copytree(native_dir_src, os.path.join(native_dir_dest, "native"))
        
        # 处理 LZO �?(如果需�?
        if lzo_utils.should_install_lzo():
            _add_lzo_libraries(tez_extract_dir)
            
        # 设置目录权限
        Directory(native_dir_dest, mode=0o755, recursive=True)
        
        # 创建新的 tarball
        new_tarball_path = os.path.join(temp_dir, f"tez-native-{uuid.uuid4().hex[:8]}.tar.gz")
        TARBALL_LOGGER.info(f"创建新版 Tez tarball: {new_tarball_path}")
        tar_archive.archive_dir_via_temp_file(new_tarball_path, tez_extract_dir)
        os.chmod(new_tarball_path, READ_ONLY_PERMS)
        
        return new_tarball_path

def prepare_mapreduce_tarball() -> str:
    """准备带有原生库的 MapReduce tarball"""
    _, mr_source, _, _ = get_tarball_paths('mapreduce')
    
    TARBALL_LOGGER.info("准备 MapReduce tarball...")
    if not os.path.exists(mr_source):
        raise Fail(f"MapReduce tarball 不存�? {mr_source}")
    
    # 如不需�?LZO 直接返回原始文件
    if not lzo_utils.should_install_lzo():
        TARBALL_LOGGER.info("未启�?LZO，跳过处�?)
        return mr_source
    
    # 创建临时目录
    with tempfile.TemporaryDirectory() as temp_dir,\
         tempfile.TemporaryDirectory(prefix='mr-process-') as mr_extract_dir:
        
        _set_temp_perms(mr_extract_dir)
        
        # 解压原始 tarball
        TARBALL_LOGGER.info(f"解压 {mr_source} �?{mr_extract_dir}")
        tar_archive.untar_archive(mr_source, mr_extract_dir)
        
        # 添加 LZO �?        _add_lzo_libraries(mr_extract_dir)
        
        # 创建新的 tarball
        new_tarball_path = os.path.join(temp_dir, f"mr-native-{uuid.uuid4().hex[:8]}.tar.gz")
        TARBALL_LOGGER.info(f"创建新版 MapReduce tarball: {new_tarball_path}")
        tar_archive.archive_dir_via_temp_file(new_tarball_path, mr_extract_dir)
        os.chmod(new_tarball_path, READ_ONLY_PERMS)
        
        return new_tarball_path

def _add_lzo_libraries(target_dir: str):
    """添加 LZO 库到指定目录"""
    stack_root = Script.get_stack_root()
    version = _get_current_service_version("MAPREDUCE2", True)
    lzo_dir_path = os.path.join(
        stack_root, version, "hadoop", "lib", "native"
    )
    
    # 回退路径
    if not os.path.exists(lzo_dir_path):
        lzo_dir_path = os.path.join(stack_root, "current", "hadoop-client", "lib", "native")
        TARBALL_LOGGER.info(f"使用 LZO 回退路径: {lzo_dir_path}")
    
    if not os.path.exists(lzo_dir_path):
        raise Fail(f"LZO 库目录不存在: {lzo_dir_path}")
    
    dest_dir = os.path.join(target_dir, "hadoop", "lib", "native")
    os.makedirs(os.path.dirname(dest_dir), exist_ok=True)
    
    TARBALL_LOGGER.info(f"复制 LZO 库从 {lzo_dir_path} �?{dest_dir}")
    shutil.copytree(lzo_dir_path, dest_dir, dirs_exist_ok=True)
    Directory(dest_dir, mode=0o755)

def _set_temp_perms(path: str):
    """设置临时目录权限"""
    sudo.chmod(path, SAFE_DIR_PERMS)

def copy_to_hdfs(
    name: str,
    user_group: str,
    owner: str,
    file_mode: int = READ_ONLY_PERMS,
    custom_source: str = None,
    custom_dest: str = None,
    force_execute: bool = False,
    use_upgrading_version: bool = True,
    replace_existing: bool = False,
    skip: bool = False,
    skip_component_check: bool = False
) -> bool:
    """
    将本�?tarball 文件复制�?HDFS
    
    Args:
        name: tarball 名称
        user_group: HDFS 文件所属组
        owner: HDFS 文件所有�?        file_mode: 文件权限模式
        custom_source: 自定义源文件路径
        custom_dest: 自定义目标文件路�?        force_execute: 是否立即执行HDFS操作
        use_upgrading_version: 在升级时使用目标版本
        replace_existing: 是否替换现有文件
        skip: 是否跳过复制
        skip_component_check: 是否跳过组件检�?        
    Returns:
        操作是否成功
    """
    TARBALL_LOGGER.info(f"开始处�?tarball: {name}")
    
    # 跳过系统准备的集�?    skip_tarball = skip or get_sysprep_skip_copy_tarballs_hdfs()
    if skip_tarball:
        TARBALL_LOGGER.warning(f"跳过 {name} 复制 (系统准备模式)")
        return True
    
    # 获取路径信息
    success, source_file, dest_file, prep_func = get_tarball_paths(
        name, use_upgrading_version, custom_source, custom_dest
    )
    
    if not success or not source_file or not dest_file:
        TARBALL_LOGGER.error(f"获取 {name} 路径失败")
        return False
    
    # 检查组件状�?(可�?
    if not skip_component_check and not _is_component_active(name):
        TARBALL_LOGGER.info(f"组件 {name} 未激活，跳过复制")
        return True
    
    # 检查源文件是否存在
    if not os.path.exists(source_file):
        TARBALL_LOGGER.error(f"源文件不存在: {source_file}")
        return False
    
    TARBALL_LOGGER.info(f"源文�? {source_file} -> HDFS 目标: {dest_file}")
    
    # 预处理文�?(例如添加本地�?
    if prep_func:
        try:
            TARBALL_LOGGER.info(f"运行预处理函�? {prep_func.__name__}")
            source_file = prep_func()
        except Exception as e:
            TARBALL_LOGGER.error(f"预处理失�? {str(e)}")
            return False
    
    # 使用配置类声明HDFS资源
    import params
    dest_dir = os.path.dirname(dest_file)
    
    params.HdfsResource(
        dest_dir,
        type="directory",
        action="create_on_execute",
        owner=owner,
        mode=0o555
    )
    
    params.HdfsResource(
        dest_file,
        type="file",
        action="create_on_execute",
        source=source_file,
        group=user_group,
        owner=owner,
        mode=file_mode,
        replace_existing_files=replace_existing
    )
    
    TARBALL_LOGGER.info(f"声明 HDFS 资源完成")
    
    # 立即执行或稍后执�?    if force_execute:
        TARBALL_LOGGER.info("立即执行 HDFS 操作...")
        params.HdfsResource(None, action="execute")
        TARBALL_LOGGER.info("HDFS 操作完成")
    
    return True

def _is_component_active(name: str) -> bool:
    """检查组件是否处于活动状�?""
    config_name = SERVICE_TO_CONFIG_MAP.get(name.lower())
    if not config_name:
        TARBALL_LOGGER.warning(f"{name} 缺少配置映射")
        return True  # 默认允许操作
    
    config = default(f"/configurations/{config_name}", None)
    if config is None:
        TARBALL_LOGGER.info(f"{config_name} 配置不存�?)
        return False
    
    return True

# 示例使用
if __name__ == "__main__":
    # 模拟环境设置
    os.environ["SHFURDP_STACK_NAME"] = "HDP"
    os.environ["SHFURDP_STACK_ROOT"] = "/usr/hdp"
    
    # 测试 Tez tarball 准备
    tez_path = prepare_tez_tarball()
    print(f"Tez tarball 准备完成: {tez_path}")
    
    # 测试复制�?HDFS
    copy_to_hdfs(
        name="tez",
        user_group="hadoop",
        owner="tez",
        force_execute=False
    )
