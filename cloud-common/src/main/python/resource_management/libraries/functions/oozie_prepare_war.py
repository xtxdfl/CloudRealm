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

Enhanced Oozie WAR Preparation Module
"""

import os
import hashlib
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Tuple, Optional

from resource_management.core import shell
from resource_management.core.exceptions import Fail
from resource_management.core.resources.system import File
from resource_management.libraries.functions import format
from resource_management.libraries.functions import secured_execution

# 配置日志
logger = logging.getLogger("oozie_war_prep")
logger.setLevel(logging.INFO)

class WarPreparationState:
    """表示 WAR 文件准备状态的不可变对象"""
    __slots__ = ('command_hash', 'libext_hash', 'should_run')
    
    def __init__(self, command_hash: str, libext_hash: str, should_run: bool):
        self.command_hash = command_hash
        self.libext_hash = libext_hash
        self.should_run = should_run

class OozieWarError(Fail):
    """Oozie WAR 准备错误的基类"""
    pass

class WarPreparationNeeded(OozieWarError):
    """需要 WAR 文件准备操作的异常"""
    pass

def generate_command_hash(command: str) -> str:
    """
    生成命令的安全哈希
    
    :param command: 完整命令字符串
    :return: SHA256 哈希字符串
    """
    return hashlib.sha256(command.encode('utf-8')).hexdigest()

def generate_libext_fingerprint(libext_dir: str) -> str:
    """
    生成 libext 目录的指纹（基于文件名和大小）
    
    :param libext_dir: libext 目录路径
    :return: 目录内容的指纹哈希
    """
    md5 = hashlib.md5()
    try:
        # 递归处理目录内容
        for root, _, files in os.walk(libext_dir):
            # 按字母顺序处理文件以确保一致性
            for filename in sorted(files):
                filepath = Path(root) / filename
                if filepath.is_file():
                    # 文件名和大小组合
                    md5.update(f"{filepath.name}{filepath.stat().st_size}".encode('utf-8'))
    except OSError as e:
        logger.error(f"无法扫描 libext 目录: {str(e)}")
        return "error"
    
    return md5.hexdigest()

def load_war_state(
    params: Dict[str, str],
    marker_files: Dict[str, Path]
) -> Optional[WarPreparationState]:
    """
    加载当前的 WAR 准备状态
    
    :param params: Oozie 配置参数
    :param marker_files: 标记文件路径
    :return: WAR 准备状态对象
    """
    command = format(
        "cd {oozie_tmp_dir} && {oozie_setup_sh_current} prepare-war {oozie_secure}"
    ).strip()
    command_hash = generate_command_hash(command)
    
    # 捕获 libext 目录指纹
    try:
        libext_fingerprint = generate_libext_fingerprint(format(params.oozie_libext_dir))
    except Exception as e:
        logger.error(f"生成 libext 目录指纹失败: {str(e)}")
        return WarPreparationState(command_hash, "error", False)
    
    should_run = False
    
    # 检查命令标记文件
    if not os.path.exists(marker_files['command']):
        logger.info("命令标记文件不存在 - 需要执行 WAR 准备")
        should_run = True
    else:
        try:
            with open(marker_files['command'], 'r') as f:
                cmd_marker = f.read().strip()
            if cmd_marker != command_hash:
                logger.info(
                    "命令标记文件内容不匹配:\n"
                    f"期望: {command_hash}\n"
                    f"实际: {cmd_marker}"
                )
                should_run = True
        except IOError as e:
            logger.error(f"读取命令标记文件失败: {str(e)}")
            should_run = True
    
    # 检查 libext 标记文件
    if not should_run:
        if not os.path.exists(marker_files['libext']):
            logger.info("libext 标记文件不存在 - 需要执行 WAR 准备")
            should_run = True
        else:
            try:
                with open(marker_files['libext'], 'r') as f:
                    libext_marker = f.read().strip()
                if libext_marker != libext_fingerprint:
                    logger.info(
                        "libext 目录内容已更改:\n"
                        f"期望指纹: {libext_fingerprint}\n"
                        f"实际指纹: {libext_marker}"
                    )
                    should_run = True
            except IOError as e:
                logger.error(f"读取 libext 标记文件失败: {str(e)}")
                should_run = True
    
    return WarPreparationState(command_hash, libext_fingerprint, should_run)

def save_war_state(
    state: WarPreparationState, 
    marker_files: Dict[str, Path]
) -> None:
    """
    保存 WAR 准备状态
    
    :param state: WAR 准备状态对象
    :param marker_files: 标记文件路径
    """
    try:
        # 创建父目录（如果不存在）
        os.makedirs(marker_files['command'].parent, exist_ok=True)
        
        # 写入命令标记文件
        with open(marker_files['command'], 'w') as f:
            f.write(state.command_hash)
        
        # 写入 libext 标记文件
        with open(marker_files['libext'], 'w') as f:
            f.write(state.libext_fingerprint)
        
        # 设置安全权限
        for file_path in marker_files.values():
            os.chmod(file_path, 0o644)
    
    except IOError as e:
        logger.error(f"保存 WAR 准备状态失败: {str(e)}")
        raise WarPreparationNeeded(
            "无法保存 WAR 准备状态标记"
        ) from e

def execute_prepare_war(
    params: Dict[str, str], 
    marker_files: Dict[str, Path]
) -> None:
    """
    执行实际的 WAR 准备命令
    
    :param params: Oozie 配置参数
    :param marker_files: 标记文件路径
    """
    # 准备完整的命令
    command = format(
        "cd {oozie_tmp_dir} && {oozie_setup_sh} prepare-war {oozie_secure}"
    ).strip()
    
    logger.info(f"执行 WAR 准备命令: {command}")
    
    # 安全执行命令（带超时和错误处理）
    result = secured_execution.run_user_command(
        command, 
        user=params.oozie_user,
        timeout=600,  # WAR 准备可能需要较长时间
        return_stdout=True  # 我们需要输出进行分析
    )
    
    # 验证命令输出
    if (result.exit_code != 0 or 
        "New Oozie WAR file with added".lower() not in result.stdout.lower()):
        logger.error(
            "WAR 准备失败:\n"
            f"退出码: {result.exit_code}\n"
            f"输出: {result.stdout}\n"
            f"错误: {result.stderr}"
        )
        
        # 清理无效状态标记文件
        for path in marker_files.values():
            try:
                if os.path.exists(path):
                    os.remove(path)
                    logger.info(f"清理无效标记文件: {path}")
            except OSError:
                pass
            
        raise OozieWarError("WAR 准备失败 - 参考日志获取详细信息")

def verify_temp_directory(params: Dict[str, str]) -> None:
    """
    验证 Oozie 临时目录是否已正确设置
    
    :param params: Oozie 配置参数
    """
    temp_dir = format("{oozie_tmp_dir}")
    if not os.path.exists(temp_dir):
        try:
            Path(temp_dir).mkdir(parents=True, exist_ok=True)
            logger.info(f"创建 Oozie 临时目录: {temp_dir}")
        except OSError as e:
            raise OozieWarError(
                f"无法创建临时目录 {temp_dir}: {str(e)}"
            ) from e
    
    # 确保适当的目录所有权
    try:
        os.chown(temp_dir, params.oozie_uid, params.oozie_gid)
    except OSError as e:
        logger.warning(f"无法更改临时目录所有权: {str(e)}")

def run_war_preparation_batch(params: Dict[str, str]) -> None:
    """
    执行 WAR 准备的主函数（入口点）
    
    :param params: Oozie 配置参数
    """
    try:
        logger.info("开始 Oozie WAR 准备任务")
        
        # 定义标记文件
        marker_files = {
            'command': Path(format("{oozie_home}/.prepare_war_cmd")),
            'libext': Path(format("{oozie_home}/.war_libext_content"))
        }
        
        # 验证临时目录
        verify_temp_directory(params)
        
        # 评估当前状态
        state = load_war_state(params, marker_files)
        if not state:
            logger.warning("状态评估失败 - 继续执行 WAR 准备")
            state = WarPreparationState("", "", True)
        
        if state.should_run:
            # 执行 WAR 准备
            execute_prepare_war(params, marker_files)
            
            # 重新捕获 libext 指纹（执行后可能发生变化）
            final_libext_fingerprint = generate_libext_fingerprint(
                format(params.oozie_libext_dir)
            )
            final_state = WarPreparationState(
                state.command_hash,
                final_libext_fingerprint,
                False
            )
            
            # 保存最终状态
            save_war_state(final_state, marker_files)
            logger.info("成功完成 WAR 准备")
        else:
            logger.info(
                f"跳过 WAR 准备 - 标记文件 {marker_files['command']} 与当前状态匹配"
            )
    
    except WarPreparationNeeded as wpe:
        logger.info(f"需要 WAR 准备: {str(wpe)}")
        run_war_preparation_batch(params)  # 重试
    
    except Exception as e:
        logger.error(f"Oozie WAR 准备失败: {str(e)}")
        raise OozieWarError(
            f"Oozie WAR 准备失败: {str(e)}"
        ) from e

# ==================== 使用示例 ====================
if __name__ == "__main__":
    import json
    
    # 模拟参数配置
    sample_params = {
        "oozie_home": "/usr/hdp/current/oozie-server",
        "oozie_tmp_dir": "/var/tmp/oozie",
        "oozie_libext_dir": "/usr/hdp/current/oozie-server/libext",
        "oozie_setup_sh": "/usr/hdp/current/oozie-server/bin/oozie-setup.sh",
        "oozie_setup_sh_current": "/usr/hdp/current/oozie-server/bin/oozie-setup.sh",
        "oozie_secure": "--secure",
        "oozie_user": "oozie",
        "oozie_uid": 1001,
        "oozie_gid": 1001
    }
    
    print("=== 执行 Oozie WAR 准备任务 ===")
    try:
        run_war_preparation_batch(sample_params)
        print("✅ WAR 准备成功完成")
    except OozieWarError as owe:
        print(f"❌ WAR 准备失败: {str(owe)}")
