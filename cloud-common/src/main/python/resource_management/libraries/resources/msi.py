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

Windows MSI 安装包管理系统

提供全面的Windows软件包安装、管理和修复功能，支持：
- 本地/远程MSI安装包部署
- 自定义安装参数配置
- 静默安装与卸载
- 安装日志记录
- 安装状态验证
- 数字签名验证
- 依赖管理
- 安装结果代码解析
"""

import os
import sys
import re
import shutil
import tempfile
import logging
import subprocess
import hashlib
import json
from urllib.request import urlopen
from resource_management.core.base import (
    Resource, 
    ForcedListArgument, 
    ResourceArgument,
    BooleanArgument
)

# MSI 标准退出代码含义
MSI_EXIT_CODES = {
    0: "安装成功",
    1602: "用户取消",
    1603: "安装过程中出现致命错误",
    1618: "另一个安装已在运行",
    1619: "无法打开安装包",
    1620: "无法验证安装包完整性",
    1621: "安装包版本不受支持",
    1625: "需要管理员权限"
}

# 支持的安装源类型
SOURCE_TYPES = ["local", "http", "https", "ftp", "s3"]

class Msi(Resource):
    """
    Windows MSI 软件包管理资源
    
    特点:
    • 多源支持: 支持本地、HTTP、S3等多种来源
    • 安全验证: 数字签名验证和哈希校验
    • 静默部署: 后台静默安装/卸载
    • 复杂配置: 支持自定义安装参数和属性
    • 状态检测: 已安装软件状态验证
    • 依赖管理: 软件包依赖处理
    
    使用场景:
      Windows软件批量部署
      企业级软件分发
      自动化桌面环境配置
      系统映像定制
    
    示例:
        Msi(
            name="VisualStudioBuildTools",
            msi_name="vs_buildtools_2022.msi",
            product_id="{ABC12345-6789-DEFG-1234-567890ABCDEF}",
            http_source="https://downloads.example.com/vs_buildtools_2022.msi",
            install_args=["ADDLOCAL=ALL", "INSTALLDIR=C:\\Program Files\\BuildTools"],
            uninstall_args=["REMOVE=ALL", "/quiet"],
            install_checks=[
                "file:C:\\Program Files\\BuildTools\\msbuild.exe",
                "reg:HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\VisualStudio\\Version=17.0"
            ],
            download_dir="C:\\installers",
            checksum="sha256:abcdef1234567890",
            certificate_publisher="Microsoft Corporation",
            action="install"
        )
    """
    
    # 核心安装参数
    action = ForcedListArgument(
        default="install",
        choices=["install", "uninstall", "repair", "verify"],
        description="操作类型: 安装/卸载/修复/验证"
    )
    msi_name = ResourceArgument(
        required=True,
        default=lambda obj: obj.name,
        description="MSI文件名(包含扩展名)"
    )
    product_id = ResourceArgument(
        required=True,
        description="MSI产品ID(GUID格式)"
    )
    product_version = ResourceArgument(
        default=None,
        description="软件包版本号(x.y.z格式)"
    )
    
    # 安装源配置
    http_source = ResourceArgument(
        default=None,
        description="HTTP/HTTPS下载源URL"
    )
    ftp_source = ResourceArgument(
        default=None,
        description="FTP下载源URL"
    )
    s3_source = ResourceArgument(
        default=None,
        description="S3下载源URI"
    )
    source_type = ResourceArgument(
        default="local",
        choices=SOURCE_TYPES,
        description="安装源类型"
    )
    source_path = ResourceArgument(
        default=None,
        description="本地源路径"
    )
    download_dir = ResourceArgument(
        default=None,
        description="下载文件保存目录"
    )
    keep_downloads = BooleanArgument(
        default=False,
        description="安装后保留下载文件"
    )
    
    # 安装参数
    install_args = ForcedListArgument(
        default=["/qn", "/norestart"],
        description="安装命令行参数"
    )
    uninstall_args = ForcedListArgument(
        default=["/qn"],
        description="卸载命令行参数"
    )
    repair_args = ForcedListArgument(
        default=["/qn", "/repair"],
        description="修复命令行参数"
    )
    transform_file = ResourceArgument(
        default=None,
        description="MST转换文件路径"
    )
    suppress_reboot = BooleanArgument(
        default=True,
        description="禁止自动重启"
    )
    disable_ui_all = BooleanArgument(
        default=True,
        description="完全禁用UI(完全静默)"
    )
    
    # 安全验证
    checksum = ResourceArgument(
        default=None,
        description="文件校验值格式 hash_type:value (如: sha256:abcd...)"
    )
    signature_required = BooleanArgument(
        default=True,
        description="需要数字签名"
    )
    certificate_publisher = ResourceArgument(
        default=None,
        description="签名者名称(必须匹配)"
    )
    
    # 状态验证
    install_checks = ForcedListArgument(
        default=[],
        description="安装成功验证条件"
    )
    
    # 高级配置
    dependency_ids = ForcedListArgument(
        default=[],
        description="依赖产品的ID(GUIDs)"
    )
    force_reinstall = BooleanArgument(
        default=False,
        description="强制重新安装"
    )
    require_network = BooleanArgument(
        default=False,
        description="需要网络连接"
    )
    log_file = ResourceArgument(
        default=None,
        description="安装日志文件路径"
    )
    log_verbose = BooleanArgument(
        default=True,
        description="启用详细安装日志"
    )
    
    # 支持的操作
    actions = Resource.actions + ["install", "uninstall", "repair", "verify"]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.logger = logging.getLogger(f"Msi.{self.name}")
        
        # 检测操作系统
        if sys.platform != "win32":
            raise OSError("MSI资源仅在Windows系统可用")
            
        # 为MSI文件设置完整路径
        self._resolve_msi_path()
        
        # 添加默认日志路径
        if not self.log_file:
            self.log_file = f"C:\\Windows\\Temp\\{self.msi_name}.log"
            
        # 添加默认下载目录
        if not self.download_dir:
            self.download_dir = os.environ.get('TEMP', 'C:\\Windows\\Temp')
    
    def install(self):
        """安装MSI软件包"""
        if self._is_installed():
            if self.force_reinstall:
                self.logger.info(f"{self.msi_name} 已安装，强制重装...")
                return self._run_reinstall()
            else:
                self.logger.info(f"{self.msi_name} 已安装，跳过安装")
                return True
                
        # 文件存在检查
        if not os.path.exists(self.local_msi_path):
            self._download_msi()
            
        # 验证文件
        if not self._validate_file():
            self.logger.error("MSI文件验证失败")
            return False
            
        # 构建安装命令
        cmd = self._build_install_command()
        
        # 执行安装
        if not self._run_msiexec(cmd, "安装"):
            return False
            
        # 验证安装
        return self._verify_installation()
    
    def uninstall(self):
        """卸载MSI软件包"""
        if not self._is_installed():
            self.logger.info(f"{self.msi_name} 未安装，无需卸载")
            return True
            
        # 构建卸载命令
        cmd = self._build_uninstall_command()
        
        # 执行卸载
        if not self._run_msiexec(cmd, "卸载"):
            return False
            
        # 验证卸载
        return self._verify_uninstallation()
    
    def repair(self):
        """修复安装"""
        if not self._is_installed():
            self.logger.warning("无法修复未安装的软件包")
            return False
            
        # 构建修复命令
        cmd = self._build_repair_command()
        
        # 执行修复
        return self._run_msiexec(cmd, "修复")
    
    def verify(self):
        """验证安装状态"""
        installed = self._is_installed()
        self.logger.info(f"验证结果: {self.msi_name} {'已安装' if installed else '未安装'}")
        return installed
    
    def _resolve_msi_path(self):
        """解析MSI本地路径"""
        # 优先使用source_path
        if self.source_path:
            self.local_msi_path = os.path.join(self.source_path, self.msi_name)
            return
            
        # 其次使用各种下载源
        if self.http_source or self.ftp_source or self.s3_source:
            self.local_msi_path = os.path.join(self.download_dir, self.msi_name)
            return
            
        # 最后尝试当前目录
        self.local_msi_path = self.msi_name
    
    def _download_msi(self):
        """下载MSI安装包"""
        # 确定下载源
        download_url = None
        if self.http_source:
            download_url = self.http_source
        elif self.ftp_source:
            download_url = self.ftp_source
        elif self.s3_source:
            # 实际实现中会使用boto3
            self.logger.warning("S3下载功能暂未实现")
            return False
            
        if not download_url:
            self.logger.error("未提供有效的下载源")
            return False
            
        self.logger.info(f"开始下载: {download_url}")
        
        # 创建目标目录
        os.makedirs(self.download_dir, exist_ok=True)
        
        try:
            with urlopen(download_url) as response:
                with open(self.local_msi_path, 'wb') as f:
                    shutil.copyfileobj(response, f)
                    
            self.logger.info(f"下载完成: {self.local_msi_path}")
            return True
        except Exception as e:
            self.logger.error(f"下载失败: {str(e)}")
            return False
    
    def _validate_file(self):
        """验证MSI文件完整性和签名"""
        # 文件存在检查
        if not os.path.exists(self.local_msi_path):
            self.logger.error(f"MSI文件不存在: {self.local_msi_path}")
            return False
            
        # 文件大小检查
        if os.path.getsize(self.local_msi_path) < 1024:
            self.logger.error("MSI文件过小，可能无效")
            return False
            
        # 校验和验证
        if self.checksum and not self._verify_checksum():
            return False
            
        # 数字签名验证
        if self.signature_required and not self._verify_signature():
            return False
            
        return True
    
    def _verify_checksum(self):
        """验证文件校验和"""
        hash_type, expected_hash = self.checksum.split(':', 1)
        hash_type = hash_type.lower()
        
        # 计算实际哈希值
        hasher = hashlib.new(hash_type)
        with open(self.local_msi_path, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        actual_hash = hasher.hexdigest()
        
        # 比较哈希值
        if actual_hash != expected_hash:
            self.logger.error(f"校验和不匹配\n期望: {expected_hash}\n实际: {actual_hash}")
            return False
            
        self.logger.info(f"{hash_type} 校验和验证通过")
        return True
    
    def _verify_signature(self):
        """验证数字签名"""
        command = [
            'powershell',
            'Get-AuthenticodeSignature',
            '-FilePath', self.local_msi_path,
            '|', 'Format-List', '-Property', 'Status, SignerCertificate'
        ]
        
        try:
            result = subprocess.run(
                ' '.join(command), 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                shell=True
            )
            
            # 检查签名状态
            if "Status : Valid" not in result.stdout:
                self.logger.error(f"签名验证失败: {result.stdout}")
                return False
                
            # 检查特定发布者
            if self.certificate_publisher:
                if f"IssuerName : CN={self.certificate_publisher}" not in result.stdout:
                    self.logger.error("发布者证书不匹配")
                    return False
                    
            self.logger.info("数字签名验证通过")
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"签名验证命令失败: {e.stderr}")
            return False
    
    def _build_install_command(self):
        """构建安装命令行"""
        base_cmd = [
            "msiexec.exe", 
            "/i", self.local_msi_path,
            "/l*v", self.log_file
        ]
        
        # 添加静默参数
        if self.disable_ui_all:
            base_cmd.append("/qn")
        else:
            base_cmd.append("/passive")
            
        # 添加禁止重启参数
        if self.suppress_reboot:
            base_cmd.append("/norestart")
            
        # 添加转换文件
        if self.transform_file:
            base_cmd.extend(["TRANSFORMS=", self.transform_file])
            
        # 添加自定义参数
        for arg in self.install_args:
            base_cmd.append(arg)
            
        return base_cmd
    
    def _build_uninstall_command(self):
        """构建卸载命令行"""
        base_cmd = [
            "msiexec.exe",
            "/x", self.product_id,
            "/l*v", self.log_file
        ]
        
        if self.disable_ui_all:
            base_cmd.append("/qn")
            
        # 添加禁止重启参数
        if self.suppress_reboot:
            base_cmd.append("/norestart")
            
        # 添加自定义参数
        for arg in self.uninstall_args:
            base_cmd.append(arg)
            
        return base_cmd
    
    def _build_repair_command(self):
        """构建修复命令行"""
        base_cmd = [
            "msiexec.exe",
            "/fa", self.product_id,
            "/l*v", self.log_file
        ]
        
        if self.disable_ui_all:
            base_cmd.append("/qn")
            
        # 添加禁止重启参数
        if self.suppress_reboot:
            base_cmd.append("/norestart")
            
        # 添加自定义参数
        for arg in self.repair_args:
            base_cmd.append(arg)
            
        return base_cmd
    
    def _run_msiexec(self, command, action_name):
        """执行MSI操作"""
        self.logger.info(f"开始{action_name} {self.msi_name}")
        self.logger.debug(f"命令: {' '.join(command)}")
        
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            
            exit_code = result.returncode
            self.logger.debug(f"退出代码: {exit_code}")
            
            # 检查退出代码
            if exit_code == 0:
                self.logger.info(f"{action_name}成功")
                return True
            else:
                error_msg = MSI_EXIT_CODES.get(exit_code, f"未知错误 {exit_code}")
                self.logger.error(f"{action_name}失败: {error_msg}")
                self._analyze_logs()
                return False
                
        except subprocess.CalledProcessError as e:
            self.logger.error(f"{action_name}异常: {e.stderr}")
            self._analyze_logs()
            return False
        except Exception as e:
            self.logger.error(f"{action_name}运行时错误: {str(e)}")
            return False
    
    def _analyze_logs(self):
        """分析安装日志"""
        if not os.path.exists(self.log_file):
            self.logger.warning("安装日志不存在")
            return
            
        self.logger.info("分析安装日志中...")
        
        try:
            with open(self.log_file, 'r', encoding='utf-16') as f:
                log_content = f.read()
            
            # 查找错误行
            error_lines = [line for line in log_content.splitlines() if "error" in line.lower()]
            
            # 关键错误码
            error_codes = re.findall(r'Error (\d+):', log_content)
            if error_codes:
                self.logger.error(f"检测到错误代码: {', '.join(set(error_codes))}")
                
            # 展示最后10行错误
            for line in error_lines[-10:]:
                self.logger.debug(f"日志错误: {line}")
                
        except UnicodeDecodeError:
            self.logger.warning("日志文件解码失败")
    
    def _is_installed(self):
        """检查软件是否已安装"""
        # 通过产品ID检查注册表
        reg_path = f"HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{self.product_id}"
        
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, 
                f"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\{self.product_id}"
            )
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            return False
        except PermissionError:
            self.logger.error("需要管理员权限")
            return False
    
    def _verify_installation(self):
        """验证安装结果"""
        # 基本产品ID验证
        if not self._is_installed():
            self.logger.error("基本验证失败: 未在注册表中找到产品ID")
            return False
            
        # 额外验证条件
        all_checks_passed = True
        for check in self.install_checks:
            if not self._verify_check_condition(check):
                self.logger.error(f"验证失败: {check}")
                all_checks_passed = False
                
        if all_checks_passed:
            self.logger.info("所有安装验证通过")
            return True
        return False
    
    def _verify_uninstallation(self):
        """验证卸载结果"""
        if self._is_installed():
            self.logger.error("卸载验证失败: 产品ID仍在注册表中")
            return False
        
        # 检查可能的残余文件等
        return True
    
    def _verify_check_condition(self, condition):
        """验证单一的安装检查条件"""
        # 文件存在检查
        if condition.startswith("file:"):
            file_path = condition[5:]
            if not os.path.exists(file_path):
                self.logger.debug(f"文件不存在: {file_path}")
                return False
            return True
            
        # 注册表项存在检查
        if condition.startswith("reg:"):
            try:
                import winreg
                reg_path = condition[4:]
                key_spec = reg_path.split()
                key_path = key_spec[0]
                value_name = key_spec[1] if len(key_spec) > 1 else None
                value_expected = key_spec[2] if len(key_spec) > 2 else None
                
                hive, path = key_path.split('\\', 1)
                access = winreg.KEY_READ
                
                # 解析注册表根键
                if hive == "HKEY_LOCAL_MACHINE":
                    root_key = winreg.HKEY_LOCAL_MACHINE
                elif hive == "HKEY_CURRENT_USER":
                    root_key = winreg.HKEY_CURRENT_USER
                else:
                    self.logger.warning(f"不支持的注册表根键: {hive}")
                    return False
                    
                # 打开注册表项
                key = winreg.OpenKey(root_key, path, 0, access)
                
                # 检查值是否存在
                if value_name:
                    try:
                        value, value_type = winreg.QueryValueEx(key, value_name)
                        # 检查期望值
                        if value_expected:
                            if str(value) != value_expected:
                                self.logger.debug(f"注册表值不匹配: {value} != {value_expected}")
                                return False
                        return True
                    except FileNotFoundError:
                        self.logger.debug(f"注册表值不存在: {value_name}")
                        return False
                else:
                    return True
                    
            except Exception as e:
                self.logger.debug(f"注册表访问错误: {str(e)}")
                return False
                
        # 服务运行检查
        if condition.startswith("service:"):
            service_name = condition[8:]
            if not self._is_service_running(service_name):
                return False
            return True
            
        # PowerShell脚本检查
        if condition.startswith("ps:"):
            script = condition[3:]
            return self._run_powershell_check(script)
            
        self.logger.warning(f"未知的验证条件类型: {condition}")
        return False
    
    def _is_service_running(self, service_name):
        """检查服务是否运行"""
        command = f'sc query "{service_name}" | find "RUNNING"'
        try:
            result = subprocess.run(
                command, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                shell=True
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def _run_powershell_check(self, script):
        """执行PowerShell验证脚本"""
        cmd = [
            'powershell', 
            '-ExecutionPolicy', 'Bypass', 
            '-Command', script
        ]
        
        try:
            result = subprocess.run(cmd, check=True)
            return result.returncode == 0
        except subprocess.CalledProcessError as e:
            self.logger.debug(f"PowerShell验证失败: {e.stderr}")
            return False
    
    def _run_reinstall(self):
        """执行重新安装操作"""
        self.uninstall()
        return self.install()

