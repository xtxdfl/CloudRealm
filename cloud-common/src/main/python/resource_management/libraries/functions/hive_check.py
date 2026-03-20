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

Secure Hive Thrift Port Validation Utility
"""

import logging
import time
from enum import Enum
from typing import Dict, Optional, Tuple

from resource_management.core import shell
from resource_management.core.exceptions import Fail
from resource_management.core.resources import Execute
from resource_management.core.signal_utils import TerminateStrategy
from resource_management.core.shell import quote_bash_args
from resource_management.libraries.functions import secure_dump, format
from resource_management.libraries.functions.security import KerberosSecurityContext

# 日志配置
logger = logging.getLogger('hive_thrift_check')
logger.setLevel(logging.INFO)

class AuthType(Enum):
    """Hive 身份认证类型"""
    NOSASL = "NOSASL"
    KERBEROS = "KERBEROS"
    LDAP = "LDAP"
    PAM = "PAM"

class TransportType(Enum):
    """数据传输协议类型"""
    BINARY = "binary"
    HTTP = "http"

class ThriftPortError(Fail):
    """Thrift 端口检查错误的基类"""
    pass

class ConnectionFailure(ThriftPortError):
    """连接失败异常"""
    pass

class AuthenticationFailure(ThriftPortError):
    """身份认证失败异常"""
    pass

class TimeoutError(ThriftPortError):
    """操作超时异常"""
    pass

def build_beeline_url(
    address: str,
    port: int,
    auth_type: AuthType,
    transport: TransportType,
    http_endpoint: str = "cliservice",
    ssl: bool = False,
    ssl_keystore: Optional[str] = None,
    principal: Optional[str] = None
) -> str:
    """
    构建安全�?Beeline JDBC URL
    
    :param address: Hive 服务器地址
    :param port: Thrift 服务端口
    :param auth_type: 身份认证类型
    :param transport: 传输协议类型
    :param http_endpoint: HTTP 端点路径
    :param ssl: 是否启用 SSL
    :param ssl_keystore: SSL 密钥库路�?    :param principal: Kerberos 主体名称
    :return: 完整�?Beeline JDBC URL 字符�?    """
    # 基础 URL 组件
    url_parts = [
        f"jdbc:hive2://{address}:{port}/"
    ]
    
    # 传输协议配置
    url_parts.append(f"transportMode={transport.value}")
    
    if transport == TransportType.HTTP:
        url_parts.append(f"httpPath={http_endpoint}")
    
    # 认证配置
    if auth_type == AuthType.NOSASL:
        url_parts.append("auth=noSasl")
    
    # SSL 配置
    if ssl:
        url_parts.append(f"ssl={str(ssl).lower()}")
        if ssl_keystore:
            url_parts.append(f"sslTrustStore={ssl_keystore}")
    
    # Kerberos 主体配置
    if auth_type == AuthType.KERBEROS and principal:
        url_parts.append(f"principal={principal}")
    
    # 拼接所有部�?    return ";".join(url_parts)

def build_credential_args(
    auth_type: AuthType,
    hive_user: str = "hive",
    ldap_username: Optional[str] = None,
    ldap_password: Optional[str] = None,
    pam_username: Optional[str] = None,
    pam_password: Optional[str] = None
) -> str:
    """
    构建认证凭证参数
    
    :param auth_type: 身份认证类型
    :param hive_user: Hive 默认用户
    :param ldap_username: LDAP 用户�?    :param ldap_password: LDAP 密码
    :param pam_username: PAM 用户�?    :param pam_password: PAM 密码
    :return: 凭证参数字符�?    """
    # 安全引用密码
    safe_password_placeholder = "'_SECURE_PASSWORD_'"
    
    if auth_type == AuthType.LDAP and ldap_username and ldap_password:
        quoted_password = secure_dump.secure_dump_value(ldap_password)
        return f"-n {ldap_username} -p {quoted_password}"
    
    elif auth_type == AuthType.PAM and pam_username and pam_password:
        quoted_password = secure_dump.secure_dump_value(pam_password)
        return f"-n '{pam_username}' -p {quoted_password}"
    
    # 默认使用 Hive 用户
    return f"-n {hive_user}"

def execute_kinit(
    kinit_cmd: str, 
    user: str,
    retries: int = 3,
    retry_delay: int = 5
) -> None:
    """
    安全执行 Kerberos 认证
    
    :param kinit_cmd: kinit 命令
    :param user: 执行用户
    :param retries: 重试次数
    :param retry_delay: 重试间隔(�?
    """
    # 使用 Kerberos 全局�?    kinit_lock = global_lock.get_lock(global_lock.LOCK_TYPE_KERBEROS)
    
    try:
        # 获取锁的超时时间
        kinit_lock.acquire(timeout=30)
        
        # 重试逻辑
        for attempt in range(1, retries + 1):
            try:
                logger.info(f"执行 Kerberos 认证 (尝试 {attempt}/{retries})")
                Execute(
                    kinit_cmd, 
                    user=user,
                    timeout=15,
                    logoutput=True
                )
                return
            except Fail:
                if attempt < retries:
                    logger.warning(f"Kerberos 认证失败, 将在 {retry_delay}秒后重试...")
                    time.sleep(retry_delay)
                else:
                    logger.error("Kerberos 认证最终失�?)
                    raise AuthenticationFailure("Kerberos 认证失败")
    except global_lock.LockTimeout:
        logger.error("获取 Kerberos 锁超�?)
        raise AuthenticationFailure("Kerberos 锁获取失�?)
    finally:
        if kinit_lock.locked():
            kinit_lock.release()

def build_connection_command(
    url: str,
    credential_args: str
) -> str:
    """
    构建连接测试命令
    
    :param url: Beeline URL
    :param credential_args: 凭证参数
    :return: 完整的连接测试命�?    """
    # 安全忽略模式的正则表达式
    ignore_patterns = [
        "Connected to:",
        "Transaction isolation:",
        "inactive HS2 instance; use service discovery"
    ]
    grep_exclusions = "|".join([f"-i -e '{pattern}'" for pattern in ignore_patterns])
    
    return (
        "beeline -u '%s' %s -e ';' 2>&1 | "
        "grep -vz %s > /dev/null; "
        "test ${PIPESTATUS[0]} -eq 0"
    ) % (url, credential_args, grep_exclusions)

def validate_thrift_connection(
    connection_cmd: str,
    user: str,
    timeout: int = 30
) -> bool:
    """
    验证 Thrift 连接
    
    :param connection_cmd: 连接测试命令
    :param user: 执行用户
    :param timeout: 超时时间(�?
    :return: 连接是否成功
    """
    try:
        logger.info(f"验证 Thrift 连接 (超时: {timeout}�?")
        Execute(
            connection_cmd,
            user=user,
            path=[
                "/bin", 
                "/usr/bin", 
                "/usr/lib/hive/bin", 
                "/usr/sbin"
            ],
            timeout=timeout,
            timeout_kill_strategy=TerminateStrategy.KILL_PROCESS_TREE,
            logoutput=True
        )
        return True
    except Fail as e:
        logger.error(f"连接验证失败: {str(e)}")
        return False

def check_thrift_port_sasl(
    config: Dict,
    smoke_test_user: str = "cloud-qa",
    retries: int = 3,
    retry_delay: int = 10,
    command_timeout: int = 30
) -> bool:
    """
    执行 Hive Thrift SASL 端口检�?    
    :param config: Hadoop 配置字典
    :param smoke_test_user: 测试用户
    :param retries: 重试次数
    :param retry_delay: 重试间隔(�?
    :param command_timeout: 命令超时时间(�?
    :return: 端口是否可达
    """
    # 解析配置参数
    params = {
        'address': config.get('hive_server_host', 'localhost'),
        'port': int(config.get('hive_server_port', 10000)),
        'auth_type': AuthType(config.get('hive_authentication', 'KERBEROS')),
        'transport': TransportType(config.get('hive_transport_mode', 'binary')),
        'http_endpoint': config.get('hive_http_endpoint', 'cliservice'),
        'ssl': bool(config.get('hive_ssl_enabled', False)),
        'ssl_keystore': config.get('ssl_keystore_path'),
        'ssl_password': config.get('ssl_keystore_password'),
        'principal': config.get('kerberos_principal'),
        'kinit_cmd': config.get('kinit_command'),
        'ldap_username': config.get('ldap_username'),
        'ldap_password': config.get('ldap_password'),
        'pam_username': config.get('pam_username'),
        'pam_password': config.get('pam_password'),
        'hive_user': config.get('hive_service_user', 'hive')
    }
    
    logger.info(f"验证 {params['address']}:{params['port']} �?Thrift 连接")
    
    # 构建安全上下�?    security_ctx = KerberosSecurityContext(
        principal=params['principal'],
        keytab_path=config.get('kerberos_keytab'),
        service_name='hive'
    )
    
    # 认证准备
    if params['auth_type'] == AuthType.KERBEROS:
        if not security_ctx.is_configured():
            raise AuthenticationFailure("Kerberos 未配置完�?)
        if params['kinit_cmd']:
            execute_kinit(params['kinit_cmd'], smoke_test_user)
    
    # 构建 Beeline URL
    beeline_url = build_beeline_url(
        address=params['address'],
        port=params['port'],
        auth_type=params['auth_type'],
        transport=params['transport'],
        http_endpoint=params['http_endpoint'],
        ssl=params['ssl'],
        ssl_keystore=params['ssl_keystore'],
        principal=params['principal']
    )
    
    # 构建凭证参数
    credential_args = build_credential_args(
        auth_type=params['auth_type'],
        hive_user=params['hive_user'],
        ldap_username=params['ldap_username'],
        ldap_password=params['ldap_password'],
        pam_username=params['pam_username'],
        pam_password=params['pam_password']
    )
    
    # 构建连接命令
    connection_cmd = build_connection_command(
        url=beeline_url,
        credential_args=credential_args
    )
    
    # 重试连接
    for attempt in range(1, retries + 1):
        logger.info(f"尝试连接 #{attempt}")
        try:
            if validate_thrift_connection(
                connection_cmd, 
                smoke_test_user,
                command_timeout
            ):
                logger.info("Thrift 连接成功建立")
                return True
        except Exception as e:
            error_detail = str(e)
            if "Timeout" in error_detail:
                logger.warning(f"连接超时 (尝试 #{attempt})")
            elif "Authentication" in error_detail:
                raise AuthenticationFailure(f"认证失败: {error_detail}")
            else:
                logger.error(f"连接错误: {error_detail}")
        
        if attempt < retries:
            logger.info(f"{retry_delay}秒后重试...")
            time.sleep(retry_delay)
    
    raise ConnectionFailure(
        f"{retries}次尝试后仍然无法连接�?Thriftserver ({params['address']}:{params['port']})"
    )

# ==================== 使用示例 ====================
if __name__ == "__main__":
    import logging.config
    logging.config.fileConfig('/etc/cloud/logging.conf')
    
    # 示例配置
    sample_config = {
        'hive_server_host': 'hive-server.example.com',
        'hive_server_port': '10000',
        'hive_authentication': 'KERBEROS',
        'hive_transport_mode': 'binary',
        'kerberos_principal': 'hive/_HOST@EXAMPLE.COM',
        'kerberos_keytab': '/etc/security/keytabs/hive.service.keytab',
        'ssl_keystore_path': '/etc/hive/conf/keystore.jks',
        'ssl_keystore_password': 'secure_password',
        'kinit_command': 'kinit -kt /path/to/keytab hive/principal'
    }
    
    try:
        success = check_thrift_port_sasl(sample_config)
        if success:
            print("\n�?Thrift 连接验证成功")
            exit(0)
    except ConnectionFailure as cf:
        print(f"\n🔌 连接失败: {str(cf)}")
        exit(101)
    except AuthenticationFailure as af:
        print(f"\n🔐 认证失败: {str(af)}")
        exit(102)
    except TimeoutError as te:
        print(f"\n�?操作超时: {str(te)}")
        exit(103)
    except ThriftPortError:
        print("\n�?Thrift 端口检查出�?)
        exit(1)
    except Exception as e:
        print(f"\n�?未知错误: {str(e)}")
        exit(2)
