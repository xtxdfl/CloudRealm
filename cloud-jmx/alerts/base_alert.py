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

import logging
import re
import time
from collections import namedtuple
from typing import Dict, Any, Optional, List, Tuple, Union

# 配置日志
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 创建命名元组来返回包含URI和SSL标志的元组
AlertUri = namedtuple("AlertUri", "uri is_ssl_enabled")
UriLookupConfig = namedtuple(
    "UriLookupConfig", 
    "acceptable_codes http https https_property https_property_value default_port "
    "kerberos_keytab kerberos_principal "
    "ha_nameservice ha_alias_key ha_http_pattern ha_https_pattern"
)

class AlertState:
    """告警状态常量"""
    OK = "OK"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"
    SKIPPED = "SKIPPED"


class BaseAlert:
    """告警处理基类，提供通用告警处理功能"""
    
    # 匹配配置键的正则表达式，如{{hdfs-site/value}}
    CONFIG_KEY_REGEXP = re.compile(r"{{(\S+?)}}")
    
    # 默认的kinit超时时间（毫秒）
    DEFAULT_KINIT_TIMEOUT = 14400000  # 4小时

    # HA相关参数常量
    HA_NAMESERVICE_PARAM = "{{ha-nameservice}}"
    HA_ALIAS_PARAM = "{{alias}}"

    def __init__(self, alert_meta: Dict, alert_source_meta: Dict, config: Any):
        """
        初始化告警基类
        
        Args:
            alert_meta: 告警元数据
            alert_source_meta: 告警来源元数据
            config: 配置对象
        """
        self.alert_meta = alert_meta
        self.alert_source_meta = alert_source_meta
        self.cluster_name = ""
        self.cluster_id = ""
        self.host_name = ""
        self.public_host_name = ""
        self.config = config
        
        # 辅助对象
        self.collector = None
        self.cluster_configuration_cache = None
        self.configuration_builder = None
    
    # ----------------------------
    # 公共属性访问器
    # ----------------------------
    
    def interval(self) -> int:
        """获取告警检查的执行间隔（分钟）"""
        interval = self.alert_meta.get("interval", 1)
        return max(1, interval)  # 确保间隔最小为1分钟
    
    def get_definition_id(self) -> int:
        """获取告警定义ID"""
        return self.alert_meta["definitionId"]
    
    def is_enabled(self) -> bool:
        """检查告警是否启用"""
        return self.alert_meta["enabled"]
    
    def get_name(self) -> str:
        """获取告警名称"""
        return self.alert_meta["name"]
    
    def get_uuid(self) -> str:
        """获取告警UUID"""
        return self.alert_meta["uuid"]
    
    def get_reporting_text(self, state: str) -> str:
        """获取结果报告文本模板"""
        return "{0}"
    
    # ----------------------------
    # 环境设置方法
    # ----------------------------
    
    def set_helpers(
        self, 
        collector: Any, 
        cluster_configuration_cache: Any, 
        configuration_builder: Any
    ) -> None:
        """
        设置辅助对象
        
        Args:
            collector: 告警收集器
            cluster_configuration_cache: 集群配置缓存
            configuration_builder: 配置构建器
        """
        self.collector = collector
        self.cluster_configuration_cache = cluster_configuration_cache
        self.configuration_builder = configuration_builder
    
    def set_cluster(
        self, 
        cluster_name: str, 
        cluster_id: Union[int, str], 
        host_name: str, 
        public_host_name: Optional[str] = None
    ) -> None:
        """
        设置集群信息
        
        Args:
            cluster_name: 集群名称
            cluster_id: 集群ID
            host_name: 主机名
            public_host_name: 公共主机名（默认为主机名）
        """
        self.cluster_name = cluster_name
        self.cluster_id = str(cluster_id)
        self.host_name = host_name
        self.public_host_name = public_host_name or host_name
    
    # ----------------------------
    # 告警收集主流程
    # ----------------------------
    
    def collect(self) -> None:
        """执行告警收集并处理结果"""
        try:
            # 执行具体的收集操作
            result = self._collect()
            result_state, result_data = result
        except Exception as e:
            logger.exception(f"[告警][{self.get_name()}] 告警收集失败")
            result_state = AlertState.UNKNOWN
            result_data = [f"系统错误: {str(e)}"]
        
        # 获取报告文本模板
        reporting_text = self._resolve_reporting_template(result_state)
        
        # 格式化报告文本
        formatted_text = self._format_result_text(reporting_text, result_data)
        
        # 构建告警数据
        alert_data = self._build_alert_data(result_state, formatted_text)
        
        # 将告警数据提交给收集器
        self._submit_alert_data(alert_data)
    
    def _resolve_reporting_template(self, result_state: str) -> str:
        """解析报告文本模板"""
        # 转换为小写状态以匹配定义
        state_lower = result_state.lower()
        reporting_config = self.alert_source_meta.get("reporting", {})
        state_config = reporting_config.get(state_lower, {})
        
        # 优先使用定义中配置的报告文本
        if "text" in state_config:
            return state_config["text"]
        
        # 使用默认报告文本
        return self.get_reporting_text(result_state)
    
    def _format_result_text(self, template: str, data: list) -> str:
        """格式化结果文本"""
        try:
            # 尝试直接格式化
            return template.format(*data)
        except (ValueError, TypeError):
            # 格式化失败时转为字符串再尝试
            logger.warning(f"[告警][{self.get_name()}] 结果格式化异常，尝试字符串转换")
            str_data = [str(item) for item in data]
            return template.format(*str_data)
    
    def _build_alert_data(self, state: str, text: str) -> Dict:
        """构建告警数据字典"""
        return {
            "name": self.alert_meta.get("name", ""),
            "clusterId": self.cluster_id,
            "timestamp": int(time.time() * 1000),
            "definitionId": self.get_definition_id(),
            "state": state,
            "text": text.replace("\x00", "").strip()  # 清理无效字符和空白
        }
    
    def _submit_alert_data(self, alert_data: Dict) -> None:
        """提交告警数据到收集器"""
        if self.collector:
            self.collector.put(self.cluster_name, alert_data)
        else:
            logger.error(f"[告警][{self.get_name()}] 收集器未设置，无法提交告警数据")
    
    # ----------------------------
    # 配置解析方法
    # ----------------------------
    
    def _get_configuration_value(
        self, 
        configurations: Dict, 
        key: str, 
        default: Any = None
    ) -> Any:
        """
        从配置中解析值
        
        Args:
            configurations: 配置字典
            key: 配置键或包含占位符的字符串
            default: 找不到时的默认值
            
        Returns:
            解析后的配置值
        """
        if not key:
            return default
            
        # 查找所有占位符（如{{hdfs-site/foo}}）
        placeholders = self.CONFIG_KEY_REGEXP.findall(key)
        
        # 如果没有占位符，直接返回键值
        if not placeholders:
            return key
        
        # 逐个替换占位符
        resolved = key
        for placeholder in placeholders:
            # 获取配置值
            config_value = self.get_configuration_value(configurations, placeholder)
            
            # 如果找不到值，整个解析失败
            if config_value is None:
                return None
            
            # 对于字典类型配置，直接返回整个字典
            if isinstance(config_value, dict):
                return config_value
                
            # 替换占位符
            resolved = resolved.replace(f"{{{{{placeholder}}}}}", config_value)
        
        return resolved
    
    def get_configuration_value(
        self, 
        configurations: Dict, 
        key_path: str
    ) -> Any:
        """
        通过路径从配置中获取值
        
        Args:
            configurations: 配置字典
            key_path: 配置路径（如 'hdfs-site/foo'）
            
        Returns:
            配置值或None（如果找不到）
        """
        if not key_path:
            return None
            
        # 规范化路径
        if not key_path.startswith("/"):
            key_path = f"/configurations/{key_path}"
        
        # 分割路径为层级
        keys = [k for k in key_path.split("/") if k]
        
        # 逐级查找配置
        current = configurations
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                logger.debug(f"[告警][{self.get_name()}] 配置未找到: {key_path}")
                return None
            current = current[key]
        
        return current
    
    # ----------------------------
    # URI 相关方法
    # ----------------------------
    
    def _parse_uri_config(self, uri_config: Dict) -> Optional[UriLookupConfig]:
        """解析URI配置字典为结构化对象"""
        if not uri_config:
            return None
            
        return UriLookupConfig(
            acceptable_codes=uri_config.get("acceptable_codes"),
            http=uri_config.get("http"),
            https=uri_config.get("https"),
            https_property=uri_config.get("https_property"),
            https_property_value=uri_config.get("https_property_value"),
            default_port=uri_config.get("default_port"),
            kerberos_keytab=uri_config.get("kerberos_keytab"),
            kerberos_principal=uri_config.get("kerberos_principal"),
            ha_nameservice=uri_config.get("high_availability", {}).get("nameservice"),
            ha_alias_key=uri_config.get("high_availability", {}).get("alias_key"),
            ha_http_pattern=uri_config.get("high_availability", {}).get("http_pattern"),
            ha_https_pattern=uri_config.get("high_availability", {}).get("https_pattern"),
        )
    
    def _get_uri(self, uri_config: Dict) -> Optional[AlertUri]:
        """
        根据URI配置获取实际的URI
        
        Args:
            uri_config: URI配置字典
            
        Returns:
            包含URI和SSL标志的命名元组
        """
        # 解析URI配置
        lookup_cfg = self._parse_uri_config(uri_config)
        if not lookup_cfg:
            return None
            
        # 获取集群配置
        configurations = self.configuration_builder.get_configuration(self.cluster_id)
        
        # 优先尝试高可用性URI
        ha_uri = self._get_ha_uri(lookup_cfg, configurations)
        if ha_uri:
            return ha_uri
            
        # 获取普通URI
        return self._get_standard_uri(lookup_cfg, configurations)
    
    def _get_ha_uri(
        self, 
        lookup_cfg: UriLookupConfig, 
        configurations: Dict
    ) -> Optional[AlertUri]:
        """获取高可用性URI"""
        # 如果没有配置高可用性参数，直接返回
        if not lookup_cfg.ha_nameservice and not lookup_cfg.ha_alias_key:
            return None
            
        logger.debug(f"[告警][{self.get_name()}] 检测到高可用性URI配置，尝试解析")
        
        # 获取高可用性名称服务
        ha_nameservice = self._get_configuration_value(
            configurations, lookup_cfg.ha_nameservice
        )
        
        # 如果需要名称服务但未配置，返回None
        if lookup_cfg.ha_nameservice and not ha_nameservice:
            logger.debug(f"[告警][{self.get_name()}] 未配置高可用名称服务: {lookup_cfg.ha_nameservice}")
            return None
            
        # 获取高可用性别名键
        alias_key = lookup_cfg.ha_alias_key
        if not alias_key:
            return None
            
        # 处理名称服务列表
        ha_nameservices = [ns.strip() for ns in ha_nameservice.split(",")] if ha_nameservice else [None]
        
        # 收集名称服务及其别名
        aliases_map = {}
        for nameservice in ha_nameservices:
            resolved_key = alias_key.replace(self.HA_NAMESERVICE_PARAM, nameservice or "")
            aliases = self._get_configuration_value(configurations, resolved_key)
            if aliases:
                aliases_map[nameservice] = aliases
                
        # 如果没有找到任何别名，返回None
        if not aliases_map:
            logger.warning(f"[告警][{self.get_name()}] 未找到高可用别名: {alias_key}")
            return None
            
        # 确定URI模式（HTTP或HTTPS）
        use_ssl = self._check_ssl_enabled(lookup_cfg, configurations)
        pattern = lookup_cfg.ha_https_pattern if use_ssl else lookup_cfg.ha_http_pattern
        
        if not pattern:
            logger.warning(f"[告警][{self.get_name()}] 未配置高可用URI模式")
            return None
            
        # 尝试匹配主机到别名
        for nameservice, aliases_str in aliases_map.items():
            aliases = [a.strip() for a in aliases_str.split(",")]
            
            for alias in aliases:
                # 构建配置键
                pattern_key = pattern
                if nameservice:
                    pattern_key = pattern_key.replace(self.HA_NAMESERVICE_PARAM, nameservice)
                pattern_key = pattern_key.replace(self.HA_ALIAS_PARAM, alias)
                
                # 获取URI值
                uri_value = self._get_configuration_value(configurations, pattern_key)
                
                # 检查是否匹配当前主机
                if uri_value and self._is_host_match(uri_value):
                    return AlertUri(uri=uri_value, is_ssl_enabled=use_ssl)
        
        logger.warning(f"[告警][{self.get_name()}] 没有找到匹配当前主机的高可用URI")
        return None
    
    def _get_standard_uri(
        self, 
        lookup_cfg: UriLookupConfig, 
        configurations: Dict
    ) -> AlertUri:
        """获取标准URI（非高可用）"""
        # 解析HTTP和HTTPS配置
        http_uri = self._get_configuration_value(configurations, lookup_cfg.http)
        https_uri = self._get_configuration_value(configurations, lookup_cfg.https)
        
        # 如果没有配置URI但有默认端口，返回默认端口
        if not http_uri and not https_uri and lookup_cfg.default_port:
            return AlertUri(uri=str(lookup_cfg.default_port), is_ssl_enabled=False)
            
        # 默认使用HTTP
        uri = http_uri
        is_ssl_enabled = False
        
        # 检查是否应使用HTTPS
        if https_uri:
            # 如果没有HTTP配置则使用HTTPS
            if not http_uri:
                uri = https_uri
                is_ssl_enabled = True
            else:
                # 检查SSL属性
                is_ssl_enabled = self._check_ssl_enabled(lookup_cfg, configurations)
                uri = https_uri if is_ssl_enabled else http_uri
        
        return AlertUri(uri=uri, is_ssl_enabled=is_ssl_enabled)
    
    def _is_host_match(self, uri_value: str) -> bool:
        """检查URI值是否匹配当前主机"""
        host = self._extract_host_from_uri(uri_value)
        if not host:
            return False
            
        return (
            self.host_name.lower() in host.lower() or 
            self.public_host_name.lower() in host.lower()
        )
    
    def _extract_host_from_uri(self, uri: str) -> Optional[str]:
        """从URI中提取主机名"""
        # 简化实现 - 实际中应使用URL解析库
        if "://" in uri:
            uri = uri.split("://")[1]
        if "/" in uri:
            uri = uri.split("/")[0]
        if ":" in uri:
            uri = uri.split(":")[0]
        return uri
        
    def _check_ssl_enabled(
        self, 
        lookup_cfg: UriLookupConfig, 
        configurations: Dict
    ) -> bool:
        """检查是否启用SSL"""
        ssl_property = self._get_configuration_value(
            configurations, lookup_cfg.https_property
        )
        expected_value = self._get_configuration_value(
            configurations, lookup_cfg.https_property_value
        )
        
        # 如果未配置SSL属性，默认不使用SSL
        if not ssl_property or not expected_value:
            return False
            
        return ssl_property == expected_value
    
    # ----------------------------
    # 抽象方法
    # ----------------------------
    
    def _collect(self) -> Tuple[str, List]:
        """
        收集告警数据（子类必须实现）
        
        Returns:
            元组 (告警状态, 数据详情)
        """
        raise NotImplementedError("子类必须实现 _collect 方法")
