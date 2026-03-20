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

Enhanced Process Monitoring Utilities
"""

import os
import time
import logging
from resource_management.core import sudo
from resource_management.core.exceptions import ComponentIsNotRunning
from resource_management.core.logger import Logger

__all__ = ["check_process_status", "wait_process_stopped"]

# 常量配置
POLL_INTERVAL = 1  # 秒 - 进程状态检查间隔
LOG_INTERVAL = 10  # 秒 - 状态日志报告间隔
MAX_WAIT_TIME = 300  # 秒 - 进程停止最大等待时间

def check_process_status(pid_file: str) -> int:
    """
    通过PID文件校验进程运行状态
    
    流程:
    1. 检查PID文件存在性
    2. 读取和解析PID值
    3. 发送信号0验证进程存活
    
    :param pid_file: PID文件路径
    :return: 有效的进程PID
    :raises ComponentIsNotRunning: 进程未运行时触发
    :raises ValueError: PID文件格式错误
    """
    logger = Logger
    
    # 验证PID文件存在
    if not pid_file or not os.path.isfile(pid_file):
        logger.info(f"PID文件缺失或为空: {pid_file}")
        raise ComponentIsNotRunning(f"PID文件缺失: {pid_file}")
    
    try:
        # 读取并解析PID文件
        pid_content = sudo.read_file(pid_file).strip()
        pid = int(pid_content)
    except ValueError as ve:
        logger.error(f"PID文件 {pid_file} 包含无效数字: '{pid_content}' - {str(ve)}")
        raise ComponentIsNotRunning(f"无效PID内容: {pid_content}") from ve
    except Exception as e:
        logger.error(f"读取PID文件 {pid_file} 失败: {str(e)}")
        raise ComponentIsNotRunning("PID文件读取异常") from e
    
    try:
        # 发送信号0验证进程存活
        sudo.kill(pid, 0)
        logger.debug(f"进程运行中: PID={pid} (文件: {pid_file})")
        return pid
    except OSError as ose:
        logger.info(f"进程已停止: PID={pid} (PID文件: {pid_file})")
        raise ComponentIsNotRunning(
            f"进程已终止 (PID {pid} from {pid_file})"
        ) from ose
    except Exception as e:
        logger.error(f"进程状态检查异常 (PID {pid}): {str(e)}")
        raise ComponentIsNotRunning("进程验证异常") from e

def wait_process_stopped(pid_file: str, max_wait: int = MAX_WAIT_TIME) -> bool:
    """
    等待进程完全停止(基于PID文件验证)
    
    流程:
    1. 周期性检查进程状态
    2. 超时后强制结束等待
    3. 提供详细的等待进度
    
    :param pid_file: 要监控的PID文件路径
    :param max_wait: 最大等待时间(秒)
    :return: 进程是否正常停止 (True: 已停止, False: 超时)
    """
    logger = Logger.logger
    start_time = time.time()
    last_log_time = start_time
    elapsed = 0
    
    logger.info(f"开始等待进程停止 (PID文件: {pid_file}) 最长等待: {max_wait}秒")
    
    while elapsed <= max_wait:
        try:
            current_time = time.time()
            elapsed = current_time - start_time
            
            # 定期记录等待状态
            if current_time - last_log_time >= LOG_INTERVAL:
                remaining = max(max_wait - elapsed, 0)
                logger.info(
                    f"等待进程停止中... 已等待: {int(elapsed)}秒 | "
                    f"剩余: {int(remaining)}秒 | PID文件: {pid_file}"
                )
                last_log_time = current_time
            
            # 检查进程状态
            check_process_status(pid_file)
            
            # 进程仍在运行，等待下一轮检查
            time.sleep(POLL_INTERVAL)
        except ComponentIsNotRunning:
            elapsed = time.time() - start_time
            logger.info(f"进程确认停止! 总等待时间: {elapsed:.1f}秒")
            return True
    
    # 超时处理
    logger.warning(
        f"进程停止等待超时! 等待 {max_wait}秒后仍在运行 "
        f"(PID文件: {pid_file})"
    )
    return False


# =========== 使用示例 ===========
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    
    # 测试PID文件
    test_pid_file = "/var/run/test_service.pid"
    
    print("=== 测试进程状态检查 ===")
    try:
        # 假设这个PID文件不存在
        check_process_status(test_pid_file)
    except ComponentIsNotRunning as e:
        print(f"测试1通过: {str(e)}")
    
    try:
        # 创建无效PID文件
        with open(test_pid_file, "w") as f:
            f.write("invalid")
        check_process_status(test_pid_file)
    except ComponentIsNotRunning as e:
        print(f"测试2通过: {str(e)}")
        os.remove(test_pid_file)
    
    print("\n=== 测试进程停止等待 ===")
    # 创建虚假运行中进程文件
    with open(test_pid_file, "w") as f:
        f.write(str(os.getpid()))  # 写入当前Python进程PID
    
    print("启动等待(5秒超时)...")
    result = wait_process_stopped(test_pid_file, max_wait=5)
    print(f"等待结果: {'成功' if result else '超时'}")
    
    # 清理
    os.remove(test_pid_file)

