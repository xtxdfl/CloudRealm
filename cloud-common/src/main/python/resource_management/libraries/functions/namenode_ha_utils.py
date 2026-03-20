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

Enhanced HDFS Namenode State Management Utilities
"""

import logging
import socket
import time
from typing import Dict, List, Optional, Tuple, Generator
from resource_management.core.base import Fail
from resource_management.core import shell
from resource_management.core.logger import Logger
from resource_management.libraries.functions.decorator import retry
from resource_management.libraries.functions.hdfs_utils import is_https_enabled_in_hdfs

# 日志配置
logger = Logger
"""使用资源管理框架的标准日志记录器"""

# HDFS 配置常量
HDFS_NN_STATE_ACTIVE = "active"
HDFS_NN_STATE_STANDBY = "standby"
INADDR_ANY = "0.0.0.0"
JMX_URI_TEMPLATE = "{protocol}://{host_port}/jmx?qry={{query}}"
JMX_BEAN_FS = "Hadoop:service=NameNode,name=FSNamesystem"
JMX_BEAN_NN_INFO = "Hadoop:service=NameNode,name=NameNodeInfo"
DEFAULT_NAME_SERVICE = "_default_"
HTTP_POLICY_CONFIG = "dfs.http.policy"
HTTPS_ENABLE_CONFIG = "dfs.https.enable"
NAMENODE_RPC_CONFIG = "dfs.namenode.rpc-address"
NAMESERVICES_CONFIG = "dfs.nameservices"

class NamenodeStateException(Fail):
    """Namenode 状态管理异常基类"""
    pass

class NamenodeConfigurationError(NamenodeStateException):
    """配置错误异常"""
    pass

class ActiveNamenodeNotFound(NamenodeStateException):
    """活动 Namenode 未找到异常"""
    pass

def parse_host_port_address(address: str) -> Tuple[str, int]:
    """
    解析主机端口地址
    
    :param address: 主机:端口 格式的地址
    :return: (主机名, 端口号)
    """
    if ':' not in address:
        raise ValueError(f"无效的地址格式: {address}")
    
    host, port_str = address.rsplit(':', 1)
    try:
        port = int(port_str)
    except ValueError:
        raise ValueError(f"端口号无效: {port_str}")
    
    if not host:
        host = INADDR_ANY
        
    return host, port

def resolve_bind_address(address: str, rpc_host: str) -> str:
    """
    解析绑定地址（替换 0.0.0.0）
    
    :param address: 原始地址 (host:port)
    :param rpc_host: 用于替换的 RPC 主机
    :return: 解析后的地址
    """
    if INADDR_ANY not in address:
        return address
    
    try:
        host, port = parse_host_port_address(address)
        if host == INADDR_ANY and rpc_host:
            # 避免重复替换
            if f"{rpc_host}:{port}" != address:
                return f"{rpc_host}:{port}"
    except ValueError as ve:
        logger.warning(f"地址解析失败: {address} - {str(ve)}")
    
    return address

def is_ha_enabled(hdfs_site: dict) -> bool:
    """
    检查是否启用了 HA 配置
    
    :param hdfs_site: HDFS 配置字典
    :return: 是否启用 HA
    """
    name_services = hdfs_site.get(NAMESERVICES_CONFIG)
    if not name_services:
        return False
        
    for ns in name_services.split(","):
        namenodes_key = f"dfs.ha.namenodes.{ns}"
        if namenodes_key in hdfs_site:
            return True
            
    return False

def get_cluster_security_attributes(hdfs_site: dict) -> Dict[str, bool]:
    """
    获取集群安全相关属性
    
    :param hdfs_site: HDFS 配置字典
    :return: 包含安全属性的字典
    """
    return {
        "is_https": is_https_enabled_in_hdfs(
            hdfs_site.get(HTTP_POLICY_CONFIG),
            hdfs_site.get(HTTPS_ENABLE_CONFIG, "false")
        ),
        "is_ha": is_ha_enabled(hdfs_site)
    }

def get_nameservices(hdfs_site: dict) -> List[str]:
    """
    获取所有 Name Services
    
    :param hdfs_site: HDFS 配置字典
    :return: Name Service 列表
    """
    name_services_param = hdfs_site.get(
        "dfs.internal.nameservices", 
        hdfs_site.get(NAMESERVICES_CONFIG, "")
    )
    
    if not name_services_param:
        if is_ha_enabled(hdfs_site):
            # 隐式 HA 配置但缺少显式命名
            return ["_default_ha"]
        return []
    
    name_services = name_services_param.split(",")
    return [ns.strip() for ns in name_services if ns.strip()]

def generate_namenode_jmx_uris(
    hdfs_site: dict, 
    name_service: str
) -> Generator[Tuple[str, str, str], None, None]:
    """
    为指定 Name Service 的所有 Namenodes 生成 JMX URIs
    
    :param hdfs_site: HDFS 配置字典
    :param name_service: 目标 Name Service
    :return: 生成 (namenode_id, address, jmx_uri)
    """
    security = get_cluster_security_attributes(hdfs_site)
    nn_ids_key = f"dfs.ha.namenodes.{name_service}"
    
    if nn_ids_key not in hdfs_site:
        return
    
    nn_ids = [id.strip() for id in hdfs_site[nn_ids_key].split(",") if id.strip()]
    if not nn_ids:
        logger.warning(f"Name Service '{name_service}' 未配置 namenodes")
        return
    
    # 确定协议 (HTTP/HTTPS)
    protocol = "https" if security["is_https"] else "http"
    
    for nn_id in nn_ids:
        # 获取 RPC 配置用于地址解析
        rpc_key = f"dfs.namenode.rpc-address.{name_service}.{nn_id}"
        rpc_address = hdfs_site.get(rpc_key, "")
        
        # 获取 HTTP/HTTPS 地址
        address_key = (
            f"dfs.namenode.https-address.{name_service}.{nn_id}" 
            if security["is_https"] 
            else f"dfs.namenode.http-address.{name_service}.{nn_id}"
        )
        
        if address_key not in hdfs_site:
            logger.debug(f"跳过 {nn_id}: 未找到 {address_key}")
            continue
            
        address = hdfs_site[address_key]
        
        # 解析 RPC 地址以处理 0.0.0.0
        rpc_host = ""
        if rpc_address:
            try:
                host, _ = parse_host_port_address(rpc_address)
                rpc_host = host
            except ValueError:
                pass
        
        # 替换 0.0.0.0 绑定地址
        resolved_address = resolve_bind_address(address, rpc_host)
        
        # 构建 JMX URI
        jmx_uri = JMX_URI_TEMPLATE.format(
            protocol=protocol,
            host_port=resolved_address
        )
        
        yield nn_id, resolved_address, jmx_uri

@retry(
    times=3, 
    sleep_time=1,
    backoff_factor=2, 
    err_class=NamenodeStateException,
    max_wait_time=15
)
def get_namenode_state(
    jmx_uri: str, 
    bean_query: str,
    security_enabled: bool,
    run_user: str
) -> Optional[str]:
    """
    通过 JMX 获取 Namenode 状态
    
    :param jmx_uri: JMX 服务 URI 模板
    :param bean_query: JMX bean 查询字符串
    :param security_enabled: 是否启用安全模式
    :param run_user: 运行用户
    :return: Namenode 状态或 None
    """
    from resource_management.libraries.functions.jmx import get_value_from_jmx
    
    # 格式化最终的 JMX URI
    query = jmx_uri.format(query=bean_query)
    logger.debug(f"查询 JMX: {query}")
    
    try:
        return get_value_from_jmx(
            query, 
            "tag.HAState", 
            security_enabled, 
            run_user, 
            # 使用集群范围的安全设置
            is_https_enabled_in_hdfs(), 
            # 仅在最终重试时记录警告
            is_last_retry=retry.get_retry_count() == retry.total_retries
        )
    except Exception as e:
        logger.error(f"JMX 状态查询失败: {query} - {str(e)}")
        return None

def get_ha_admin_state(
    name_service: str,
    nn_id: str,
    run_user: str
) -> Optional[str]:
    """
    使用 hdfs haadmin 命令获取 Namenode 状态
    
    :param name_service: Name Service 名称
    :param nn_id: Namenode ID
    :param run_user: 运行用户
    :return: Namenode 状态或 None
    """
    admin_cmd = f"hdfs haadmin -ns {name_service} -getServiceState {nn_id}"
    logger.debug(f"执行 HAAdmin 命令: {admin_cmd}")
    
    try:
        code, output = shell.call(admin_cmd, logoutput=False, user=run_user)
        if code == 0:
            # 标准化状态输出
            output = output.lower()
            if HDFS_NN_STATE_ACTIVE in output:
                return HDFS_NN_STATE_ACTIVE
            elif HDFS_NN_STATE_STANDBY in output:
                return HDFS_NN_STATE_STANDBY
    except Exception as e:
        logger.error(f"HAAdmin 命令执行失败: {str(e)}")
    
    return None

def get_namenode_cluster_id(
    hdfs_site: dict, 
    security_enabled: bool,
    run_user: str
) -> str:
    """
    从 NameNode JMX 获取集群 ID
    
    :param hdfs_site: HDFS 配置字典
    :param security_enabled: 是否启用安全模式
    :param run_user: 运行用户
    :return: 集群 ID
    """
    for name_service in get_nameservices(hdfs_site):
        for nn_id, address, jmx_uri in generate_namenode_jmx_uris(hdfs_site, name_service):
            # 查询 NameNodeInfo Bean 获取集群 ID
            cluster_id = get_namenode_state(
                jmx_uri,
                JMX_BEAN_NN_INFO,
                security_enabled,
                run_user
            )
            
            if cluster_id:
                logger.info(f"从 {name_service}/{nn_id} 获取集群 ID: {cluster_id}")
                return cluster_id
            logger.debug(f"无法从 {name_service}/{nn_id} 获取集群 ID")
    
    raise NamenodeStateException(
        "无法从任何 NameNode 获取集群 ID "
        "(可能 NameNodes 不可访问或 JMX 未启用)"
    )

def get_namenode_states(
    hdfs_site: Dict[str, str],
    security_enabled: bool,
    run_user: str,
    name_service: Optional[str] = None,
    retries: int = 3,
    retry_delay: int = 1
) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]], List[Tuple[str, str]]]:
    """
    获取所有 NameNodes 的状态 (Active, Standby, Unknown)
    
    :param hdfs_site: HDFS 配置字典
    :param security_enabled: 是否启用安全模式
    :param run_user: 运行用户
    :param name_service: 目标 Name Service
    :param retries: 重试次数
    :param retry_delay: 重试间隔时间(秒)
    :return: (active_nns, standby_nns, unknown_nns)
    """
    active_nns = []
    standby_nns = []
    unknown_nns = []
    
    # 确定目标 Name Services
    targets = [name_service] if name_service else get_nameservices(hdfs_site)
    if not targets:
        logger.debug("未配置 Name Services, 使用默认")
        targets.append(DEFAULT_NAME_SERVICE)
    
    logger.info(f"检查 Name Services 的状态: {', '.join(targets)}")
    
    for attempt in range(1, retries + 1):
        for service in targets:
            for nn_id, address, jmx_uri in generate_namenode_jmx_uris(hdfs_site, service):
                # 尝试通过 JMX 获取状态
                state = get_namenode_state(
                    jmx_uri, JMX_BEAN_FS, security_enabled, run_user
                )
                
                # 回退到 HA admin 命令
                if not state and attempt == retries:
                    state = get_ha_admin_state(service, nn_id, run_user)
                
                # 分类状态
                node_info = (nn_id, address)
                if state == HDFS_NN_STATE_ACTIVE:
                    logger.info(f"Active: {nn_id} ({address})")
                    active_nns.append(node_info)
                elif state == HDFS_NN_STATE_STANDBY:
                    logger.debug(f"Standby: {nn_id} ({address})")
                    standby_nns.append(node_info)
                else:
                    logger.warning(f"Unknown: {nn_id} ({address})")
                    unknown_nns.append(node_info)
        
        # 如果找到活动节点或最后一次尝试, 则退出
        if active_nns or attempt == retries:
            break
            
        logger.info(f"未找到活动 NameNode, 将在 {retry_delay}秒后重试...")
        time.sleep(retry_delay)
    
    if not active_nns:
        logger.warning(f"在所有 {len(targets)} Name Services 中都未找到活动 NameNode")
    
    return active_nns, standby_nns, unknown_nns

def get_active_namenode(
    hdfs_site: Dict[str, str],
    security_enabled: bool,
    run_user: str,
    name_service: Optional[str] = None
) -> Tuple[str, str]:
    """
    获取活动的 NameNode
    
    :param hdfs_site: HDFS 配置字典
    :param security_enabled: 是否启用安全模式
    :param run_user: 运行用户
    :param name_service: 目标 Name Service
    :return: (namenode_id, address)
    """
    active_nns, _, _ = get_namenode_states(
        hdfs_site, security_enabled, run_user, name_service
    )
    
    if active_nns:
        # 在联邦模式下可能有多个活动节点，返回第一个
        return active_nns[0]
    
    raise ActiveNamenodeNotFound(
        f"在 Name Service '{name_service or '默认'}' 中未找到活动 NameNode"
    )

def get_namenode_property(
    hdfs_site: Dict[str, str],
    property_name: str,
    security_enabled: bool,
    run_user: str,
    name_service: Optional[str] = None,
    fallback_to_single: bool = True
) -> Optional[str]:
    """
    获取 NameNode 的属性值
    
    :param hdfs_site: HDFS 配置字典
    :param property_name: 属性名（不含命名空间前缀）
    :param security_enabled: 是否启用安全模式
    :param run_user: 运行用户
    :param name_service: 目标 Name Service
    :param fallback_to_single: 非 HA 模式是否回退
    :return: 属性值或 None
    """
    security = get_cluster_security_attributes(hdfs_site)
    
    # 非 HA 配置回退
    if not security["is_ha"] and fallback_to_single:
        return hdfs_site.get(property_name, None)
    
    try:
        active_nn = get_active_namenode(
            hdfs_site, security_enabled, run_user, name_service
        )
        active_id, _ = active_nn
        
        # 构建带命名空间前缀的属性名
        ns = name_service if name_service else next(iter(get_nameservices(hdfs_site)), "")
        prefixed_prop = f"{property_name}.{ns}.{active_id}" if ns else property_name
        
        if prefixed_prop in hdfs_site:
            value = hdfs_site[prefixed_prop]
            logger.debug(f"获取属性: {prefixed_prop} = {value}")
            return value
        else:
            logger.warning(f"未找到属性: {prefixed_prop}")
            
    except ActiveNamenodeNotFound as anfe:
        logger.error(f"无法获取属性 '{property_name}': {str(anfe)}")
    except Exception as e:
        logger.exception(f"获取 NameNode 属性时出错: {str(e)}")
    
    return None

def get_all_namenode_addresses(
    hdfs_site: Dict[str, str],
    with_resolution: bool = True
) -> List[str]:
    """
    获取所有 NameNodes 的地址
    
    :param hdfs_site: HDFS 配置字典
    :param with_resolution: 是否解析 0.0.0.0 地址
    :return: 地址列表
    """
    addresses = []
    security = get_cluster_security_attributes(hdfs_site)
    
    # 遍历所有 Name Services
    for service in get_nameservices(hdfs_site):
        # 遍历所有 NameNodes
        for nn_id, address, _ in generate_namenode_jmx_uris(hdfs_site, service):
            base_host = None
            
            # 尝试解析 RPC 地址
            rpc_key = f"dfs.namenode.rpc-address.{service}.{nn_id}"
            if with_resolution and rpc_key in hdfs_site:
                try:
                    rpc_host, _ = parse_host_port_address(hdfs_site[rpc_key])
                    base_host = rpc_host
                except ValueError:
                    pass
            
            resolved = resolve_bind_address(address, base_host)
            addresses.append(resolved)
    
    # 非 HA 配置处理
    if not security["is_ha"] and not addresses:
        if security["is_https"]:
            addresses.append(hdfs_site.get("dfs.namenode.https-address", ""))
        else:
            addresses.append(hdfs_site.get("dfs.namenode.http-address", ""))
    
    # 去重并过滤无效地址
    return list({
        addr for addr in addresses 
        if addr and addr != INADDR_ANY
    })

def resolve_name_service_by_host(
    hdfs_site: Dict[str, str],
    hostname: str
) -> Optional[str]:
    """
    根据主机名解析 Name Service
    
    :param hdfs_site: HDFS 配置字典
    :param hostname: 主机名
    :return: Name Service 或 None
    """
    if not hostname:
        raise ValueError("解析 Name Service 需要有效主机名")
    
    hostname = hostname.lower()
    logger.info(f"为 {hostname} 解析 Name Service")
    
    # 遍历所有 Name Services
    for service in get_nameservices(hdfs_site):
        # 遍历所有 NameNodes
        for nn_id in hdfs_site.get(
            f"dfs.ha.namenodes.{service}", ""
        ).split(","):
            nn_id = nn_id.strip()
            if not nn_id:
                continue
                
            rpc_key = f"dfs.namenode.rpc-address.{service}.{nn_id}"
            http_key = f"dfs.namenode.http-address.{service}.{nn_id}"
            
            # 检查 RPC 地址
            for key in [rpc_key, http_key]:
                if key in hdfs_site:
                    try:
                        host, _ = parse_host_port_address(hdfs_site[key])
                        if host.lower() == hostname:
                            logger.debug(f"主机 {hostname} 属于 {service}")
                            return service
                    except ValueError:
                        logger.debug(f"跳过无效地址: {hdfs_site[key]}")
    
    logger.warning(f"未找到主机 {hostname} 的 Name Service")
    return None


# =================== 使用示例 ===================
if __name__ == "__main__":
    # 模拟配置
    test_config = {
        "dfs.nameservices": "my-cluster",
        "dfs.ha.namenodes.my-cluster": "nn1,nn2",
        "dfs.namenode.rpc-address.my-cluster.nn1": "hadoop1:8020",
        "dfs.namenode.http-address.my-cluster.nn1": "0.0.0.0:50070",
        "dfs.namenode.rpc-address.my-cluster.nn2": "hadoop2:8020",
        "dfs.namenode.http-address.my-cluster.nn2": "hadoop2:50070",
        "dfs.http.policy": "HTTP_ONLY"
    }
    
    # 测试配置检测
    print("=== 配置检测测试 ===")
    ns = get_nameservices(test_config)
    ha_enabled = is_ha_enabled(test_config)
    security = get_cluster_security_attributes(test_config)
    print(f"Name Services: {ns}")
    print(f"HA Enabled: {ha_enabled}")
    print(f"Security: {security}")
    
    # 测试地址生成
    print("\n=== JMX URI 生成测试 ===")
    for nn_id, addr, uri in generate_namenode_jmx_uris(test_config, "my-cluster"):
        print(f"{nn_id}: {addr} => {uri}")
    
    # 测试状态获取 (模拟)
    print("\n=== 状态获取测试 (模拟) ===")
    # 在实际环境中需要运行 HDFS 集群进行测试
    try:
        actives, standbys, unknowns = get_namenode_states(
            test_config, False, "hdfs", name_service="my-cluster", retries=1
        )
        print(f"Active: {actives}")
        print(f"Standby: {standbys}")
        print(f"Unknown: {unknowns}")
    except Exception as e:
        print(f"状态检查测试失败: {str(e)} (预期在测试环境中)")
    
    # 测试地址解析
    print("\n=== 地址解析测试 ===")
    print(f"Resolved: {resolve_bind_address('0.0.0.0:50070', 'hadoop1')}")
    
    # 测试主机名解析
    print("\n=== 主机名解析测试 ===")
    service = resolve_name_service_by_host(test_config, "hadoop1")
    print(f"Resolved service: {service}")

