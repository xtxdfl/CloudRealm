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

Enhanced Architecture Detection Utility
"""

import platform
import os
import sys
import logging
import json
import re
from typing import Dict, Optional, List, Tuple
from resource_management.libraries.functions.default import default

# 配置高级日志记录
logger = logging.getLogger('architecture_detector')
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# 仅在没有父处理器时添加处理程序
if not logger.hasHandlers():
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

# 定义支持的架构映射
ARCHITECTURE_MAPPING = {
    # ARM 架构系列
    'arm64': ['aarch64', 'arm64', 'armv8', 'armv8l'],
    'arm32': ['armv7l', 'armv6l'],
    
    # PowerPC 架构系列
    'ppc64le': ['ppc64le', 'powerpc64le'],
    'ppc64': ['ppc64', 'powerpc64'],
    'ppc': ['powerpc', 'ppc'],
    
    # x86 架构系列
    'amd64': ['x86_64', 'amd64'],
    'x86': ['i386', 'i686', 'x86'],
    
    # RISC-V 架构
    'riscv64': ['riscv64'],
    
    # System Z 架构
    's390x': ['s390x'],
    
    # MIPS 架构系列
    'mips64': ['mips64'],
    'mips': ['mips'],
    
    # 其他架构
    'sparc64': ['sparc64'],
    'ia64': ['ia64']
}

# 云环境检测模式
CLOUD_METADATA_ENDPOINTS = {
    'aws': 'http://169.254.169.254/latest/meta-data/',
    'gcp': 'http://metadata.google.internal/computeMetadata/v1/',
    'azure': 'http://169.254.169.254/metadata/instance?api-version=2021-05-01',
    'oracle': 'http://169.254.169.254/opc/v1/instance/'
}

# 容器环境检测文件
CONTAINER_FILES = [
    '/.dockerenv',  # Docker 容器
    '/run/.containerenv',  # Podman 容器
    '/proc/self/cgroup'  # Cgroup 检查
]

def get_architecture() -> str:
    """
    智能检测系统架构，包含多种检测方法和回退策略
    
    功能特点：
    1. 优先使用配置中定义的架构
    2. 支持检测虚拟机、容器和云环境
    3. 提供全面的架构支持（ARM、PowerPC、RISC-V等）
    4. 包含详细的检测日志
    5. 支持跨平台兼容（Linux, AIX, macOS, Windows等）
    
    返回架构标识：
    - amd64: x86-64 架构
    - arm64: ARM 64位架构
    - ppc64le: PowerPC LE 架构
    - 其他标准架构标识
    """
    try:
        # 步骤1：检查配置覆盖
        if (custom_arch := default("/configurations/hadoop-env/architecture", None)):
            logger.info(f"Using configured architecture: {custom_arch}")
            return custom_arch
        
        # 步骤2：检查容器或虚拟化环境
        if (container_arch := detect_container_architecture()):
            logger.info(f"Detected container architecture: {container_arch}")
            return normalize_architecture(container_arch)
        
        # 步骤3：云环境元数据检测
        if (cloud_arch := detect_cloud_instance_architecture()):
            logger.info(f"Detected cloud instance architecture: {cloud_arch}")
            return cloud_arch
        
        # 步骤4：核心平台检测
        return detect_core_architecture()
    
    except Exception as e:
        logger.error(f"Architecture detection failed: {str(e)}")
        # 恢复策略：基于常见架构的概率返回
        if is_windows():
            return 'amd64'  # 服务器环境绝大多数x86
        return normalized_fallback_architecture()

def detect_container_architecture() -> Optional[str]:
    """检测容器环境中的架构信息"""
    # 检查容器标识文件
    if any(os.path.exists(path) for path in CONTAINER_FILES):
        logger.debug("Container environment detected")
        
        # 方法1：检查容器环境变量
        if (arch := os.getenv('HOSTTYPE') or os.getenv('ARCH')):
            return arch
        
        # 方法2：检查标准uname结果
        try:
            result = os.uname()
            if hasattr(result, 'machine'):
                return result.machine
        except Exception:
            pass
        
        # 方法3：读取cgroup信息
        try:
            with open('/proc/self/cgroup', 'r') as f:
                for line in f:
                    if 'docker' in line or 'kubepods' in line:
                        return detect_core_architecture()
        except Exception:
            pass
    return None

def detect_cloud_instance_metadata(provider: str) -> Optional[Dict]:
    """从云提供商元数据服务获取信息"""
    endpoint = CLOUD_METADATA_ENDPOINTS.get(provider)
    if not endpoint:
        return None
    
    try:
        import urllib.request
        from urllib.error import URLError
        
        headers = {}
        # GCP 需要特殊头部
        if provider == 'gcp':
            headers['Metadata-Flavor'] = 'Google'
        
        req = urllib.request.Request(endpoint, headers=headers)
        with urllib.request.urlopen(req, timeout=2) as response:
            if response.status == 200:
                return json.loads(response.read().decode('utf-8'))
    except URLError as e:
        logger.debug(f"Metadata endpoint not available for provider {provider}: {e.reason}")
    except Exception:
        pass
    return None

def detect_cloud_instance_architecture() -> Optional[str]:
    """检测云服务虚拟机架构"""
    for provider in CLOUD_METADATA_ENDPOINTS:
        if metadata := detect_cloud_instance_metadata(provider):
            try:
                # AWS: architecture in meta-data/instance-type
                if provider == 'aws' and 'instance-type' in metadata:
                    if 'a1.' in metadata['instance-type'] or 'graviton' in metadata['instance-type']:
                        return 'arm64'
                
                # GCP: custom machine types name like "t2a-standard"
                elif provider == 'gcp':
                    if 'machineType' in metadata and 'a2-' in metadata['machineType']:
                        return 'amd64'  # GCP AMD系列
                    if 'machineType' in metadata and 't2a-' in metadata['machineType']:
                        return 'arm64'  # GCP Ampere ARM
                
                # Azure: specialized ARM instances
                elif provider == 'azure':
                    sku = metadata.get('compute', {}).get('sku', '')
                    if 'arm64' in sku.lower() or 'ampere' in sku.lower():
                        return 'arm64'
                
                # Oracle Cloud: ARM instances
                elif provider == 'oracle':
                    shape = metadata.get('shape', '')
                    if '.A1.' in shape:
                        return 'arm64'
                        
            except Exception as e:
                logger.debug(f"Could not parse {provider} metadata: {str(e)}")
    return None

def detect_core_architecture() -> str:
    """
    核心架构检测方法与回退策略
    
    检测方法优先级：
    1. platform.machine() - 最准确
    2. platform.processor() - 备选
    3. 系统文件检测
    4. 平台特定检测（AIX、z/OS等）
    """
    machine = platform.machine().lower()
    processor = platform.processor().lower()
    
    # 多方法交叉验证策略
    methods = [
        lambda: match_architecture(machine),
        lambda: match_architecture(processor),
        lambda: detect_via_uname(),
        lambda: detect_via_sys_files(),
        lambda: detect_via_platform_module()
    ]
    
    for method in methods:
        if (result := method()):
            return result
    
    # 最终回退方案
    logger.warning("Architecture detection failed, using fallback")
    return normalized_fallback_architecture()

def match_architecture(identifier: str) -> Optional[str]:
    """将平台标识符映射到标准架构"""
    for arch, patterns in ARCHITECTURE_MAPPING.items():
        for pattern in patterns:
            if re.match(pattern, identifier, re.IGNORECASE):
                return arch
    return None

def detect_via_uname() -> Optional[str]:
    """通过uname命令检测"""
    try:
        import subprocess
        result = subprocess.run(
            ['uname', '-m'], 
            capture_output=True, 
            text=True,
            check=True
        )
        if arch := match_architecture(result.stdout.strip().lower()):
            return arch
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    return None

def detect_via_sys_files() -> Optional[str]:
    """通过系统文件检测架构"""
    try:
        # 动态检测方法
        is_big_endian = sys.byteorder == 'big'
        
        # Linux kernel检测
        if os.path.exists('/proc/config.gz'):
            import gzip
            with gzip.open('/proc/config.gz', 'rt') as f:
                config = f.read()
                if 'CONFIG_64BIT=y' in config:
                    if 'CONFIG_ARM64=y' in config:
                        return 'arm64'
                    return 'amd64' if not is_big_endian else 'ppc64'
                
        # CPU信息
        if os.path.exists('/proc/cpuinfo'):
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if 'model name' in line:
                        if 'AMD' in line or 'Intel' in line:
                            return 'amd64'
                        if 'POWER' in line or 'PPC' in line:
                            return 'ppc64le' if not is_big_endian else 'ppc64'
                        if 'ARM' in line or 'Cortex' in line:
                            return 'arm64'
    except Exception:
        pass
    
    return None

def detect_via_platform_module() -> str:
    """platform模块的标准检测方法"""
    # Windows特殊处理
    if platform.system() == 'Windows':
        if platform.architecture()[0] == '64bit':
            return 'amd64'
        return 'x86'
    
    # AIX处理
    if platform.system() == 'AIX':
        # AIX只在大端环境下运行
        if os.uname().machine == '00F71DD44C00':  # 特定AIX机器标识
            return 'ppc64'
        return 'rs64'  # 较旧的IBM RS64
    
    # macOS处理
    if platform.system() == 'Darwin':
        if platform.processor() == 'arm':
            return 'arm64'
        return 'amd64'
    
    # 标准UNIX回退
    return normalized_fallback_architecture()

def normalize_architecture(arch: str) -> str:
    """标准化架构标识符"""
    arch = arch.lower().strip()
    
    # 常用别名转换
    alias_map = {
        'x64': 'amd64',
        'x86_64': 'amd64',
        'ia32': 'x86',
        'aarch64': 'arm64',
        'armv8': 'arm64',
        'powerpc': 'ppc',
        'powerpc64le': 'ppc64le',
        's390x': 's390x',
        'riscv': 'riscv64'
    }
    
    return alias_map.get(arch, arch.split('-')[0])

def normalized_fallback_architecture() -> str:
    """带日志记录的稳健回退策略"""
    # 现代Linux系统绝大多数为amd64或arm64
    if platform.system() == 'Linux':
        if 'aarch64' in os.uname().machine or 'arm' in os.uname().machine:
            logger.info("Using Linux ARM64 as fallback")
            return 'arm64'
        logger.info("Using Linux AMD64 as fallback")
        return 'amd64'
    
    # macOS系统默认arm64 (Apple Silicon)
    if platform.system() == 'Darwin':
        return 'arm64'
    
    # Windows系统默认amd64
    if platform.system() == 'Windows':
        return 'amd64'
    
    # IBM 系统默认为PowerPC
    if platform.system() == 'AIX':
        return 'ppc64'
    
    logger.warning("Unable to detect architecture, defaulting to amd64")
    return 'amd64'

def is_windows() -> bool:
    """检测Windows系统"""
    return platform.system() == 'Windows'

def get_arm_cpu_features() -> List[str]:
    """检测ARM处理器的特定功能"""
    if 'arm' not in get_architecture():
        return []
    
    features = []
    try:
        if os.path.exists('/proc/cpuinfo'):
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if 'Features' in line:
                        features = [f.strip() for f in line.split(':')[1].split()]
                        break
    except Exception:
        pass
    
    return features

def is_architecture_supported(arch: str) -> bool:
    """检查架构是否在支持列表中"""
    supported = ['amd64', 'arm64', 'ppc64le', 'x86', 's390x']
    return arch in supported

def log_architecture_details() -> None:
    """记录详细的架构信息用于调试"""
    details = {
        'architecture': platform.architecture(),
        'machine': platform.machine(),
        'processor': platform.processor(),
        'system': platform.system(),
        'uname': platform.uname(),
        'platform': platform.platform(),
        'byte_order': sys.byteorder,
        'container': any(os.path.exists(path) for path in CONTAINER_FILES)
    }
    
    logger.info("Architecture details:\n" + json.dumps(details, indent=2))

if __name__ == "__main__":
    # 直接运行时输出检测结果
    print(f"Detected architecture: {get_architecture()}")
    print(f"ARM CPU features: {get_arm_cpu_features()}")
    log_architecture_details()
