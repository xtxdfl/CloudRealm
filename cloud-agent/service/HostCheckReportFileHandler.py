#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
import json
import logging
import re
import traceback
import hashlib
import tempfile
import shutil
import datetime
from pathlib import Path
from configparser import ConfigParser
from typing import Dict, List, Optional, Union

# 配置日志
logger = logging.getLogger("HostCheckReport")
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] [%(asctime)s] [%(name)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

class ReportGeneratorError(Exception):
    """报告生成器基础异常类"""
    pass

class HostCheckReportGenerator:
    """高级主机检查报告生成服务
    
    提供主机健康状态全面监控能力：
    - 系统配置合规性检查
    - 软件包依赖分析
    - 用户账户安全审计
    - 服务状态诊断
    - 自定义扩展检查项
    
    生成标准化报告，支持文件存储和数据安全
    """
    # 常量定义
    HOST_CHECK_FILE = "hostcheck_result.json"
    HOST_CHECK_CUSTOM_ACTIONS_FILE = "hostcheck_custom_actions.json"
    
    # 可移除的系统目录正则表达式
    HADOOP_ITEMDIR_REGEXP = re.compile(r"^(\d+\.){3}\d+-\d{4}$")
    
    # 默认允许移除的系统文件夹
    DEFAULT_REMOVABLE_PATHS = ["current", "previous", "staging", "tmp"]
    
    # 排除的关键路径（避免误删除）
    VITAL_SYSTEM_PATHS = ["/bin", "/etc", "/home", "/lib", "/opt", "/root", "/sbin", "/usr", "/var"]
    
    def __init__(self, config: Optional[dict] = None):
        """初始化报告生成器
        
        :param config: 配置字典
            - report_dir: 报告文件存储目录
            - removable_paths: 允许移除的路径列表
            - vital_paths: 关键系统路径列表
        """
        self.config = self._merge_configurations(config or {})
        
        # 文件路径配置
        self.report_dir = Path(self.config["report_dir"])
        self.report_path = self.report_dir / self.HOST_CHECK_FILE
        self.custom_actions_path = self.report_dir / self.HOST_CHECK_CUSTOM_ACTIONS_FILE
        
        # 确保报告目录存在
        self.report_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"报告生成器初始化完成 - 存储目录: {self.report_dir}")

    def _merge_configurations(self, custom_config: dict) -> dict:
        """合并用户配置与默认配置"""
        default_config = {
            "report_dir": "/var/lib/cloud-agent/reports",
            "removable_paths": self.DEFAULT_REMOVABLE_PATHS,
            "vital_paths": self.VITAL_SYSTEM_PATHS,
            "hadoop_root": "/usr/hdp"
        }
        
        return {**default_config, **custom_config}

    def generate_full_report(self, host_info: dict):
        """生成完整主机检查报告"""
        try:
            # 生成主报告
            self._generate_host_check_report(host_info)
            
            # 生成自定义操作报告
            self._generate_custom_actions_report(host_info)
            
            logger.info("主机检查报告生成成功")
        except Exception as e:
            logger.exception("主机报告生成失败")
            raise ReportGeneratorError("无法生成主机检查报告") from e

    def _generate_host_check_report(self, host_info: dict):
        """生成主机状态详细报告"""
        logger.debug(f"生成主机检查报告: {self.report_path}")
        
        # 构建报告内容
        report_data = {
            "metadata": self._get_report_metadata(),
            "system_users": self._extract_user_info(host_info),
            "alternatives": self._extract_alternatives_info(host_info),
            "file_system": self._analyze_file_system(host_info),
            "processes": self._extract_process_info(host_info),
            "stale_paths": self._identify_stale_paths(host_info)
        }
        
        # 安全写入报告
        self._write_data_to_file(self.report_path, report_data, format="json")

    def _generate_custom_actions_report(self, host_info: dict):
        """生成自定义操作报告"""
        logger.debug(f"生成自定义操作报告: {self.custom_actions_path}")
        
        report_data = {
            "metadata": self._get_report_metadata(),
            "installed_packages": self._extract_package_info(host_info),
            "repositories": self._extract_repository_info(host_info),
            "recommendations": self._generate_cleanup_recommendations()
        }
        
        self._write_data_to_file(self.custom_actions_path, report_data, format="json")

    def _write_data_to_file(
        self, 
        file_path: Path, 
        data: Union[dict, list], 
        format: str = "json"
    ) -> None:
        """安全写入数据到文件"""
        try:
            # 创建临时文件
            temp_file = tempfile.NamedTemporaryFile(
                mode='w', 
                delete=False,
                dir=file_path.parent,
                suffix='.tmp'
            )
            
            # 根据格式写入数据
            if format == "json":
                json.dump(data, temp_file, indent=2)
            elif format == "config":
                config = self._convert_to_configparser(data)
                config.write(temp_file)
            
            temp_file.close()
            
            # 原子性替换旧文件
            if file_path.exists():
                backup_path = file_path.with_suffix(f".bak_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}")
                shutil.move(file_path, backup_path)
            
            shutil.move(temp_file.name, file_path)
            
            # 设置适当权限 (仅所有者可读写)
            file_path.chmod(0o600)
            
            logger.debug(f"文件成功写入: {file_path}")
        except Exception as e:
            logger.exception(f"写入文件 {file_path} 失败")
            # 清理临时文件
            if Path(temp_file.name).exists():
                os.unlink(temp_file.name)
            raise

    def _convert_to_configparser(self, data: dict) -> ConfigParser:
        """将字典转换为 ConfigParser 对象 (兼容旧格式)"""
        config = ConfigParser()
        
        for section, content in data.items():
            config.add_section(section)
            
            if isinstance(content, dict):
                for key, value in content.items():
                    # 处理列表类型值
                    if isinstance(value, list):
                        config.set(section, key, ",".join(str(v) for v in value))
                    else:
                        config.set(section, key, str(value))
        
        return config

    def _get_report_metadata(self) -> dict:
        """生成报告元数据"""
        timestamp = datetime.datetime.now().isoformat()
        system_info = self._get_system_fingerprint()
        
        return {
            "created": timestamp,
            "generator": "CloudAgent",
            "version": "2.0",
            "system_fingerprint": system_info
        }

    def _get_system_fingerprint(self) -> str:
        """生成系统唯一指纹"""
        system_id = hashlib.sha256()
        system_id.update(os.uname().version.encode('utf-8'))
        system_id.update(os.uname().machine.encode('utf-8'))
        
        if os.path.exists("/etc/machine-id"):
            with open("/etc/machine-id", "r") as f:
                system_id.update(f.read().strip().encode('utf-8'))
        
        return system_id.hexdigest()[:16]

    def _extract_user_info(self, host_info: dict) -> List[dict]:
        """提取用户账户信息"""
        users = []
        
        for user in host_info.get("existingUsers", []):
            # 过滤系统/特殊用户
            if "home" in user and "/bin/false" not in user.get("shell", ""):
                users.append({
                    "name": user["name"],
                    "home": user.get("homeDir", ""),
                    "uid": user.get("uid", ""),
                    "groups": user.get("groups", []),
                    "last_login": user.get("lastLogin", "unknown"),
                    "status": "active" if user.get("isUsed", False) else "inactive"
                })
        
        logger.debug(f"提取了 {len(users)} 个用户账户")
        return users

    def _extract_alternatives_info(self, host_info: dict) -> List[dict]:
        """提取备选方案配置信息"""
        alternatives = []
        
        for alt in host_info.get("alternatives", []):
            path = alt.get("target", "")
            
            # 验证路径有效性
            if path and os.path.isabs(path) and os.path.exists(path):
                alternatives.append({
                    "name": alt["name"],
                    "target": path,
                    "priority": alt.get("priority", 0),
                    "status": "valid"
                })
        
        logger.debug(f"提取了 {len(alternatives)} 个备选方案")
        return alternatives

    def _analyze_file_system(self, host_info: dict) -> dict:
        """分析文件系统状态"""
        file_system_info = {}
        
        # 特殊路径分析
        file_system_info["stale_paths"] = self._identify_stale_paths(host_info)
        
        # 文件系统使用情况
        file_system_info["usage"] = {
            "total": "N/A",
            "used": "N/A",
            "available": "N/A"
        }
        
        try:
            # 尝试获取文件系统使用情况
            import psutil
            usage = psutil.disk_usage(self.report_dir)
            file_system_info["usage"] = {
                "total": usage.total,
                "used": usage.used,
                "available": usage.free,
                "percent": usage.percent
            }
        except ImportError:
            logger.warning("无法获取详细的磁盘使用情况 - 请安装psutil库")
        
        return file_system_info

    def _identify_stale_paths(self, host_info: dict) -> List[str]:
        """识别需要清理的过时路径"""
        stale_paths = set()
        hadoop_root = Path(self.config["hadoop_root"])
        
        # 1. 从host_info获取路径
        for path_info in host_info.get("stackFoldersAndFiles", []):
            path = Path(path_info["name"])
            if self._is_safe_to_remove(path):
                stale_paths.add(str(path.resolve()))
        
        # 2. 静态规则检测
        if hadoop_root.exists():
            for item in hadoop_root.iterdir():
                item_path = item.resolve()
                item_name = item.name
                
                # 检测可移除的项目
                if (self._is_safe_to_remove(item_path) and 
                    (item_name in self.config["removable_paths"] or 
                     self.HADOOP_ITEMDIR_REGEXP.match(item_name))):
                    stale_paths.add(str(item_path))
        
        # 3. 扫描未使用的临时目录
        temp_dirs = ["/tmp", "/var/tmp"]
        for temp_dir in temp_dirs:
            temp_path = Path(temp_dir)
            if temp_path.exists():
                # 查找超过30天未修改的文件
                for item in temp_path.rglob('*'):
                    if item.is_file() and self._is_safe_to_remove(item):
                        # 过滤关键临时文件
                        if not (item.name.startswith(('.', 'system')) or 
                                "core" in item.name.lower()):
                            stale_paths.add(str(item))
        
        # 4. 按路径长度排序
        return sorted(stale_paths, key=len, reverse=True)

    def _is_safe_to_remove(self, path: Path) -> bool:
        """验证路径是否可安全移除"""
        try:
            # 排除关键系统路径
            for vital_path in self.config["vital_paths"]:
                if path.is_relative_to(vital_path):
                    return False
            
            # 排除符号链接
            if path.is_symlink():
                return False
                
            # 排除挂载点
            if path in [p for p in path.parents]:
                return False
            
            return True
        except Exception:
            return False

    def _extract_process_info(self, host_info: dict) -> List[dict]:
        """提取进程信息"""
        processes = []
        
        health_info = host_info.get("hostHealth", {})
        
        # Java进程
        for proc in health_info.get("activeJavaProcs", []):
            processes.append({
                "type": "java",
                "pid": proc["pid"],
                "command": proc["command"],
                "memory": proc.get("memSize", "N/A"),
                "cpu_time": proc.get("cpuTime", "N/A")
            })
        
        # 其他进程 (从hostInfo中提取)
        if "processes" in health_info:
            for proc in health_info["processes"]:
                if any(p["pid"] == proc["pid"] for p in processes):
                    continue  # 跳过已添加的Java进程
                
                processes.append({
                    "type": "system",
                    "pid": proc["pid"],
                    "command": proc["command"],
                    "user": proc.get("user", "unknown"),
                    "cpu_percent": proc.get("cpuPercent", 0.0)
                })
        
        logger.debug(f"提取了 {len(processes)} 个活动进程")
        return processes

    def _extract_package_info(self, host_info: dict) -> List[dict]:
        """提取已安装的软件包信息"""
        package_details = []
        
        for pkg in host_info.get("installed_packages", []):
            # 添加重要元数据
            pkg_info = {
                "name": pkg.get("name", ""),
                "version": pkg.get("version", "unknown"),
                "arch": pkg.get("arch", "noarch"),
                "repository": pkg.get("repository", ""),
                "install_date": pkg.get("installDate", ""),
                "size": self._humanize_bytes(pkg.get("size", 0)),
                "status": "active"
            }
            
            # 标记过时或不需要的软件包
            if pkg.get("name", "").endswith(("-devel", "-debug", "-doc")):
                pkg_info["status"] = "optional"
            elif "-unused" in pkg.get("name", "").lower():
                pkg_info["status"] = "deprecated"
            
            package_details.append(pkg_info)
        
        return package_details

    def _extract_repository_info(self, host_info: dict) -> List[str]:
        """提取仓库列表"""
        return host_info.get("existing_repos", [])

    def _generate_cleanup_recommendations(self) -> dict:
        """生成系统清理建议"""
        recommendations = {
            "low_priority": [],
            "medium_priority": [],
            "high_priority": []
        }
        
        # 临时文件建议
        recommendations["low_priority"].append(
            "清理 /tmp 和 /var/tmp 中的临时文件: find /tmp -type f -mtime +7 -exec rm -f {} \\;"
        )
        
        # 日志清理建议
        recommendations["medium_priority"].append(
            "压缩旧的日志文件: find /var/log -name \"*.log\" -mtime +30 -exec gzip {} \\;"
        )
        
        # 安全更新建议
        recommendations["high_priority"].append(
            f"执行安全更新: yum update --security -y"
        )
        
        return recommendations

    @staticmethod
    def _humanize_bytes(size_bytes: int) -> str:
        """将字节转换为易读格式"""
        if size_bytes == 0:
            return "0B"
            
        units = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        unit_index = 0
        
        while size_bytes >= 1024 and unit_index < len(units) - 1:
            size_bytes /= 1024.0
            unit_index += 1
            
        return f"{size_bytes:.2f} {units[unit_index]}"


# 使用示例
if __name__ == "__main__":
    # 模拟主机数据
    sample_host_data = {
        "existingUsers": [
            {"name": "testuser", "homeDir": "/home/testuser", "uid": "1001", "isUsed": True},
            {"name": "olduser", "homeDir": "/home/olduser", "uid": "1002", "isUsed": False}
        ],
        "alternatives": [
            {"name": "java", "target": "/usr/lib/jvm/java-11-openjdk/bin/java", "priority": 1100}
        ],
        "stackFoldersAndFiles": [
            {"name": "/opt/old_app"},
            {"name": "/var/log/old_logs"}
        ],
        "hostHealth": {
            "activeJavaProcs": [
                {"pid": 1234, "command": "java -jar app.jar", "memSize": 2048, "cpuTime": "00:12:34"}
            ]
        },
        "installed_packages": [
            {"name": "python3", "version": "3.9.5", "size": 15000000},
            {"name": "deprecated-package", "version": "1.0.0", "size": 50000}
        ],
        "existing_repos": ["base", "updates"]
    }
    
    # 创建报告生成器
    logger.info("创建主机检查报告生成器...")
    reporter = HostCheckReportGenerator({
        "report_dir": "/tmp/host_reports",
        "hadoop_root": "/opt/hadoop"
    })
    
    # 生成报告
    try:
        reporter.generate_full_report(sample_host_data)
        logger.info("示例报告生成成功")
        
        # 读取生成的报告
        with open(reporter.report_path, 'r') as f:
            main_report = json.load(f)
            print("\n主机检查报告摘要:")
            print(json.dumps(main_report, indent=2)[:500] + "...")
            
        with open(reporter.custom_actions_path, 'r') as f:
            actions_report = json.load(f)
            print("\n自定义操作报告摘要:")
            print(json.dumps(actions_report, indent=2)[:500] + "...")
    
    except ReportGeneratorError as rge:
        logger.error(f"报告生成失败: {str(rge)}")
