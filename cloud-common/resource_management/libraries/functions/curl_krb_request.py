censed to the Apache Software Foundation (ASF) under one
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

Enhanced Kerberos-Authenticated Curl Utility
"""

import contextlib
import datetime
import hashlib
import logging
import os
import getpass
import shutil
import tempfile
import time
from typing import Dict, List, Optional, Tuple, Union

from resource_management.core import global_lock, shell
from resource_management.core.exceptions import Fail
from resource_management.libraries.functions.get_user_call_output import get_user_call_output
from resource_management.libraries.functions.security_commons import KerberosSecurityContext

# 日志配置
logger = logging.getLogger("kerberos_curl")
logger.setLevel(logging.INFO)

# 安全哈希算法
HASH_ALGORITHM = hashlib.sha384
CONNECTION_TIMEOUT_DEFAULT = 10
MAX_TIMEOUT_DEFAULT = CONNECTION_TIMEOUT_DEFAULT + 5
DEFAULT_KINIT_EXPIRATION_MS = 14400000  # 4 hours
DEFAULT_KRB_CACHE_DIR = "/var/kerberos_curl_cache"
DEFAULT_COOKIE_DIR = "/var/curl_cookies"

# 全局凭证缓存时间跟踪
CREDENTIAL_CACHE_TIMES: Dict[str, float] = {}

class KerberosCurlError(Fail):
    """Kerberos curl 相关错误的基�?""
    pass

class CredentialCacheError(KerberosCurlError):
    """凭证缓存错误"""
    pass

class CurlExecutionError(KerberosCurlError):
    """curl 执行错误"""
    pass

def create_secure_temp_directory(
    path: str, 
    mode: int = 0o1777
) -> None:
    """
    创建具有安全权限的临时目�?    
    :param path: 目录路径
    :param mode: 目录权限模式
    """
    if not path:
        raise ValueError("无效目录路径")
    
    try:
        # 创建目录（如果不存在�?        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
            os.chmod(path, mode)
            logger.debug(f"创建安全目录: {path}")
            
        # 验证目录权限
        current_mode = os.stat(path).st_mode & 0o777
        if current_mode != mode:
            os.chmod(path, mode)
            logger.info(f"修正目录权限: {path} ({oct(current_mode)} -> {oct(mode)})")
            
    except (OSError, PermissionError) as e:
        raise CredentialCacheError(
            f"无法创建安全目录 '{path}': {str(e)}"
        ) from e

def generate_credential_cache_path(
    base_dir: str,
    principal: str,
    keytab: str,
    prefix: str,
    user: str
) -> Tuple[str, str]:
    """
    生成唯一的凭证缓存路�?    
    :param base_dir: 基础目录路径
    :param principal: Kerberos 主体
    :param keytab: keytab 文件路径
    :param prefix: 缓存文件前缀
    :param user: 运行用户
    :return: (缓存文件路径, 缓存文件标识�?
    """
    # 创建基础目录
    create_secure_temp_directory(base_dir)
    
    # 生成唯一标识�?    unique_id = HASH_ALGORITHM(
        f"{principal}|{keytab}|{user}".encode("utf-8")
    ).hexdigest()
    
    # 构建缓存文件路径
    cache_path = os.path.join(base_dir, f"{prefix}_{user}_cc_{unique_id}")
    
    return cache_path, unique_id

def ensure_klist_cache_validity(
    cache_path: str,
    user: str,
    krb_exec_search_paths: Optional[List[str]] = None
) -> bool:
    """
    检查凭证缓存是否有�?    
    :param cache_path: 缓存文件路径
    :param user: 运行用户
    :param krb_exec_search_paths: klist 可执行文件搜索路�?    :return: 缓存是否有效
    """
    from cloud_agent.security.kerberos_utils import get_klist_path
    
    # 获取 klist 路径
    klist_path = get_klist_path(krb_exec_search_paths or [])
    
    # 检查缓存是否存�?    if not os.path.exists(cache_path):
        logger.debug(f"缓存文件不存�? {cache_path}")
        return False
    
    # 检查缓存是否过�?    klist_cmd = [klist_path, "-s", cache_path]
    logger.debug(f"检查缓存有效�? {' '.join(klist_cmd)}")
    
    try:
        # 执行 klist 检�?        exit_code, _, klist_err = get_user_call_output(
            klist_cmd, 
            user=user,
            silent_on_success=True
        )
        if exit_code == 0:
            # 缓存有效
            cache_age = datetime.timedelta(
                seconds=time.time() - os.path.getmtime(cache_path)
            )
            logger.debug(f"缓存有效 ({cache_path}): 创建�?{cache_age} �?)
            return True
            
        # 缓存可能过期
        logger.warning(
            f"缓存检查失�? {klist_cmd} (Exit: {exit_code}) - {str(klist_err)}"
        )
    except Exception as e:
        logger.error(f"klist 缓存检查错�? {str(e)}")
    
    return False

def perform_kinit(
    cache_path: str,
    keytab: str,
    principal: str,
    user: str,
    krb_exec_search_paths: Optional[List[str]] = None
) -> None:
    """
    执行 kinit 操作获取新的凭证
    
    :param cache_path: 缓存文件路径
    :param keytab: keytab 文件路径
    :param principal: Kerberos 主体
    :param user: 运行用户
    :param krb_exec_search_paths: kinit 可执行文件搜索路�?    """
    from cloud_agent.security.kerberos_utils import get_kinit_path
    
    # 获取 kinit 路径
    kinit_path = get_kinit_path(krb_exec_search_paths or [])
    
    # 构建 kinit 命令
    kinit_cmd = [
        kinit_path,
        "-c", cache_path,
        "-kt", keytab,
        principal
    ]
    
    # 使用重定向避免密码泄露到日志
    kinit_cmd.append(">")
    kinit_cmd.append(os.devnull)
    
    full_cmd = " ".join(kinit_cmd)
    
    # 锁定执行（避免并发操作）
    kerberos_lock = global_lock.get_lock(global_lock.LOCK_TYPE_KERBEROS)
    with kerberos_lock:
        try:
            logger.info(f"执行 kinit: {' '.join(kinit_cmd[:4])}...")
            
            # 执行 kinit
            exit_code, _, kinit_err = get_user_call_output(
                kinit_cmd,
                user=user,
                timeout=30,  # Kinit 超时设置�?30 �?                silent_on_success=True
            )
            
            if exit_code != 0:
                raise CredentialCacheError(
                    f"kinit 失败 (Exit {exit_code}): {kinit_err.strip()}"
                )
            
            # 记录最后更新时�?            CREDENTIAL_CACHE_TIMES[cache_path] = time.time()
            logger.info(f"Kerberos 凭证已更�? {cache_path}")
            
            # 更新缓存文件时间�?            os.utime(cache_path, None)
            
        except Exception as e:
            logger.exception("kinit 执行失败")
            if isinstance(e, CredentialCacheError):
                raise
            raise CredentialCacheError(f"kinit 异常: {str(e)}") from e

def build_curl_command(
    url: str,
    method: str = "GET",
    body: str = "",
    headers: List[str] = None,
    ca_certs: Optional[str] = None,
    return_http_code: bool = False,
    connection_timeout: int = CONNECTION_TIMEOUT_DEFAULT,
    max_timeout: int = MAX_TIMEOUT_DEFAULT,
    cookie_file: Optional[str] = None
) -> List[str]:
    """
    构建 curl 命令参数列表
    
    :param url: 请求 URL
    :param method: HTTP 方法 (GET, POST, PUT, DELETE)
    :param body: 请求�?    :param headers: 额外请求�?    :param ca_certs: CA 证书路径
    :param return_http_code: 是否仅返�?HTTP 状态码
    :param connection_timeout: 连接超时时间
    :param max_timeout: 最大执行时�?    :param cookie_file: Cookie 文件路径
    :return: curl 命令参数列表
    """
    if not url:
        raise ValueError("URL 不能为空")
    
    # 基本参数
    curl_args = ["curl", "--location-trusted", "--negotiate", "-u", ":"]
    
    # 证书处理
    ssl_options = ["-k"] if not ca_certs else ["--cacert", ca_certs]
    curl_args.extend(ssl_options)
    
    # Cookie 处理
    if cookie_file:
        curl_args.extend(["-b", cookie_file, "-c", cookie_file])
    
    # HTTP 方法处理
    if method.upper() != "GET":
        curl_args.extend(["-X", method.upper()])
    
    # 请求头处�?    if headers:
        for header in headers:
            curl_args.extend(["-H", header])
    
    # 请求体处�?    if body:
        curl_args.extend(["-d", body])
    
    # 超时设置
    curl_args.extend([
        "--connect-timeout", str(connection_timeout),
        "--max-time", str(max_timeout)
    ])
    
    # 输出处理
    if return_http_code:
        curl_args.extend([
            "-w", "%{http_code}",
            "-o", os.devnull  # 忽略响应�?        ])
    
    # 添加 URL
    curl_args.append(url)
    
    return curl_args

@contextlib.contextmanager
def managed_cookie_file(cookie_dir: str) -> str:
    """上下文管理器处理临时cookie文件"""
    create_secure_temp_directory(cookie_dir)
    cookie_file = tempfile.NamedTemporaryFile(
        prefix="curl_cookie_",
        dir=cookie_dir,
        delete=False
    ).name
    
    try:
        yield cookie_file
    finally:
        if os.path.exists(cookie_file):
            try:
                os.remove(cookie_file)
                logger.debug(f"删除临时 cookie 文件: {cookie_file}")
            except OSError as e:
                logger.warning(f"无法删除 cookie 文件: {cookie_file} - {str(e)}")

def execute_curl_with_kerberos(
    kerberos_context: KerberosSecurityContext,
    url: str,
    caller_label: str,
    krb_cache_base_dir: str = DEFAULT_KRB_CACHE_DIR,
    return_http_code: bool = False,
    connection_timeout: int = CONNECTION_TIMEOUT_DEFAULT,
    ca_certs: Optional[str] = None,
    kinit_expiration: int = DEFAULT_KINIT_EXPIRATION_MS,
    method: str = "GET",
    headers: Optional[List[str]] = None,
    body: str = "",
    cookie_base_dir: str = DEFAULT_COOKIE_DIR
) -> Tuple[Union[int, str], Optional[str], float]:
    """
    使用 Kerberos 认证执行 curl 请求
    
    :param kerberos_context: Kerberos 安全上下文对�?    :param url: 请求 URL
    :param caller_label: 调用者标识（用于日志�?    :param krb_cache_base_dir: Kerberos 缓存基础目录
    :param return_http_code: 是否仅返�?HTTP 状态码
    :param connection_timeout: 连接超时时间
    :param ca_certs: 证书文件路径
    :param kinit_expiration: Kerberos 凭证到期时间（毫秒）
    :param method: HTTP 方法
    :param headers: 额外请求�?    :param body: 请求�?    :param cookie_base_dir: cookie 基础目录
    :return: (curl 响应, 错误信息, 执行时间)
    """
    if not kerberos_context.is_kerberos_enabled:
        raise ValueError("执行 Kerberos curl 需要启�?Kerberos")
    
    # 生成凭证缓存路径
    cache_path, cache_id = generate_credential_cache_path(
        krb_cache_base_dir,
        kerberos_context.principal,
        kerberos_context.keytab,
        caller_label,
        kerberos_context.user
    )
    
    kerberos_env = {"KRB5CCNAME": cache_path}
    last_kinit_time = CREDENTIAL_CACHE_TIMES.get(cache_path, 0)
    
    # 1. 检查是否需要刷新凭�?    cache_valid = ensure_klist_cache_validity(
        cache_path,
        kerberos_context.user,
        kerberos_context.search_paths
    )
    
    current_kinit_age = (time.time() - last_kinit_time) * 1000
    needs_kinit = not cache_valid or current_kinit_age > kinit_expiration
    
    # 2. 执行 kinit 如果需�?    if needs_kinit:
        try:
            perform_kinit(
                cache_path,
                kerberos_context.keytab,
                kerberos_context.principal,
                kerberos_context.user,
                kerberos_context.search_paths
            )
        except CredentialCacheError as cce:
            logger.error(f"凭证刷新失败 ({caller_label}): {str(cce)}")
            raise CurlExecutionError(
                f"无法获取 {caller_label} 的有效凭�?
            ) from cce
    
    # 3. 执行 curl 请求
    with managed_cookie_file(cookie_base_dir) as cookie_file:
        curl_args = build_curl_command(
            url=url,
            method=method,
            body=body,
            headers=headers,
            ca_certs=ca_certs,
            return_http_code=return_http_code,
            connection_timeout=connection_timeout,
            max_timeout=connection_timeout + 5,
            cookie_file=cookie_file
        )
        
        start_time = time.perf_counter()
        result = ""
        error_msg = None
        
        logger.debug(
            f"执行认证 curl ({caller_label}): {' '.join(curl_args)}"
        )
        
        try:
            # 执行 curl 命令
            exit_code, curl_stdout, curl_stderr = get_user_call_output(
                curl_args,
                user=kerberos_context.user,
                env=kerberos_env,
                quiet=True
            )
            
            elapsed_time = time.perf_counter() - start_time
            logger.info(
                f"Curl 完成 ({caller_label}) - "
                f"耗时: {elapsed_time:.2f}�? 状�? {exit_code}"
            )
            
            if exit_code != 0:
                error_msg = f"Curl 失败 (Exit {exit_code}): {curl_stderr.strip()}"
                logger.warning(error_msg)
                raise CurlExecutionError(error_msg)
            
            # 处理返回结果
            result = curl_stdout.strip()
            if curl_stderr:
                logger.debug(f"Curl 标准错误: {curl_stderr.strip()}")
            
            return result
        except Exception as e:
            if isinstance(e, CurlExecutionError):
                raise
                
            raise CurlExecutionError(
                f"执行认证 curl ({caller_label}) 失败: {str(e)}"
            ) from e
        finally:
            execution_time = time.perf_counter() - start_time
            return result, error_msg, execution_time

# ==================== 使用示例 ====================
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="[%(levelname)s] %(asctime)s - %(name)s - %(message)s"
    )
    
    try:
        # 创建安全上下�?        security_ctx = KerberosSecurityContext(
            principal="hdfs@EXAMPLE.COM",
            keytab="/etc/security/keytabs/hdfs.headless.keytab",
            user="hdfs",
            is_kerberos_enabled=True,
            search_paths=["/usr/bin"]
        )
        
        # API 端点配置
        test_url = "https://namenode.example.com:9870/webhdfs/v1/?op=LISTSTATUS"
        api_name = "WebHDFS API Status Check"
        
        print("\n=== 简�?GET 请求测试 ===")
        response, err, exec_time = execute_curl_with_kerberos(
            security_ctx,
            test_url,
            api_name,
            return_http_code=False
        )
        print(f"响应: {response[:100] + '...' if len(response) > 100 else response}")
        print(f"耗时: {exec_time:.2f}�?)
        
        print("\n=== HTTP 状态码请求测试 ===")
        status, err, exec_time = execute_curl_with_kerberos(
            security_ctx,
            test_url,
            api_name,
            return_http_code=True
        )
        print(f"HTTP 状态码: {status}")
        print(f"耗时: {exec_time:.2f}�?)
        
        print("\n=== 带请求体�?POST 请求测试 ===")
        post_response, err, exec_time = execute_curl_with_kerberos(
            security_ctx,
            "https://service.example.com/api/data",
            "Data Ingestion API",
            method="POST",
            headers=["Content-Type: application/json"],
            body='{"data": "sample payload"}'
        )
        print(f"响应: {post_response}")
        print(f"耗时: {exec_time:.2f}�?)
        
    except Exception as e:
        print(f"\n!!! 异常: {str(e)}")
        if isinstance(e, CurlExecutionError):
            print("详细错误信息请查看日�?)

