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
import json
import uuid
import importlib.util
import ast
import os
from typing import Dict, Any, Tuple, List, Optional, Union, NamedTuple
from dataclasses import dataclass
from tempfile import gettempdir

from alerts.base_alert import BaseAlert, AlertState
from alerts.metric_utils import (
    MetricCollector,
    JMXCollector,
    MetricCalculationError
)
from alerts.security import SecurityContext
from cloud_commons.urllib_handlers import RefreshHeaderProcessor
from resource_management.libraries.functions.url_utils import (
    get_port_from_url, 
    build_full_url,
    validate_url
)
from cloud_commons.constants import AGENT_TMP_DIR
from cloud_commons.ast_validator import ASTValidator, SecurityRule

# 配置日志
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 常量定义
DEFAULT_CONNECTION_TIMEOUT = 5.0  # 默认连接超时时间（秒）
DEFAULT_KINIT_TIMEOUT = 14400  # 默认 Kerberos 票据超时时间（4小时）
JMX_BASE_PATH = "/jmx?qry="  # JMX 基础路径
METRIC_ARGUMENT_PATTERN = re.compile(r"\{(\d+)\}")  # 指标参数引用模式

class MetricAlertConfig(NamedTuple):
    """指标告警配置数据类"""
    uri_config: Dict
    jmx_config: Dict
    warning_threshold: Optional[float] = None
    critical_threshold: Optional[float] = None
    ok_threshold: Optional[float] = None
    connection_timeout: float = DEFAULT_CONNECTION_TIMEOUT

class MetricAlert(BaseAlert):
    """JMX指标监控告警类"""
    
    def __init__(self, alert_meta: Dict, alert_source_meta: Dict, config: Any):
        """
        初始化指标监控告警
        
        Args:
            alert_meta: 告警元数据
            alert_source_meta: 告警来源元数据
            config: 配置对象
        """
        super().__init__(alert_meta, alert_source_meta, config)
        
        # 解析配置
        self.config = self._parse_config(alert_source_meta)
        self.security_context = SecurityContext(config)
        
        # 创建JMX指标收集器
        self.metric_collector = JMXCollector(self.config.jmx_config, self.get_name())
    
    def _parse_config(self, alert_source_meta: Dict) -> MetricAlertConfig:
        """解析指标告警配置"""
        # 提取URI配置
        uri_config = alert_source_meta.get("uri", {})
        
        # 设置连接超时
        connection_timeout = float(
            uri_config.get("connection_timeout", DEFAULT_CONNECTION_TIMEOUT)
        )
        
        # 提取阈值配置
        thresholds = self._extract_thresholds(alert_source_meta)
        
        return MetricAlertConfig(
            uri_config=uri_config,
            jmx_config=alert_source_meta.get("jmx", {}),
            warning_threshold=thresholds.get("warning"),
            critical_threshold=thresholds.get("critical"),
            ok_threshold=thresholds.get("ok"),
            connection_timeout=connection_timeout
        )
    
    def _extract_thresholds(self, alert_source_meta: Dict) -> Dict[str, float]:
        """从告警源元数据提取阈值配置"""
        thresholds = {}
        reporting = alert_source_meta.get("reporting", {})
        
        for state in ["warning", "critical", "ok"]:
            if state in reporting and "value" in reporting[state]:
                try:
                    thresholds[state] = float(reporting[state]["value"])
                except ValueError:
                    logger.warning(
                        f"[警报][{self.get_name()}] 无效的{state}阈值: {reporting[state]['value']}"
                    )
        
        return thresholds
    
    def _collect(self) -> Tuple[AlertState, List]:
        """
        收集指标数据并确定告警状态
        
        Returns:
            元组 (告警状态, 数据详情)
        """
        try:
            # 构建JMX URL
            jmx_url = self._build_jmx_url()
            logger.debug(f"[警报][{self.get_name()}] JMX URL: {jmx_url}")
            
            # 获取JMX JSON数据
            jmx_data = self._retrieve_jmx_data(jmx_url)
            
            # 收集指标值
            metric_values = self.metric_collector.collect(jmx_data)
            if not metric_values:
                logger.error(f"[警报][{self.get_name()}] 未收集到指标值")
                return AlertState.UNKNOWN, ["未收集到指标值"]
            
            # 计算结果值
            calc_value = self.metric_collector.calculate(metric_values)
            if calc_value is None:
                # 如果没有计算表达式，使用第一个指标值
                calc_value = metric_values[0]
            
            # 确定告警状态
            result_state = self._determine_state(calc_value)
            
            # 构建结果详情
            metric_details = self._build_result_details(metric_values, calc_value)
            
            # 结果日志记录
            self._log_collection_result(result_state, metric_details, jmx_url)
            
            return result_state, metric_details
            
        except MetricCalculationError as e:
            logger.error(f"[警报][{self.get_name()}] 指标计算失败: {str(e)}")
            return AlertState.UNKNOWN, [f"指标计算失败: {str(e)}"]
        except Exception as e:
            logger.exception(f"[警报][{self.get_name()}] 指标收集过程中发生错误")
            return AlertState.CRITICAL, [f"系统错误: {str(e)}"]
    
    def _build_jmx_url(self) -> str:
        """构建完整的JMX URL"""
        # 从配置获取监控URI
        configurations = self.configuration_builder.get_configuration(self.cluster_id)
        alert_uri = self._get_uri_from_structure(self.config.uri_config)
        
        # 构建完整URL
        return build_full_url(
            uri=alert_uri.uri,
            is_ssl=alert_uri.is_ssl_enabled,
            host=self.host_name,
            base_path=JMX_BASE_PATH,
            query=self.metric_collector.jmx_query
        )
    
    def _retrieve_jmx_data(self, jmx_url: str) -> Dict:
        """检索JMX数据"""
        # 检查是否需要Kerberos认证
        if self.security_context.is_kerberos_enabled():
            return self._retrieve_jmx_with_kerberos(jmx_url)
        
        return self._retrieve_jmx_over_http(jmx_url)
    
    def _retrieve_jmx_with_kerberos(self, jmx_url: str) -> Dict:
        """使用Kerberos认证获取JMX数据"""
        try:
            # 获取Kerberos凭证
            credentials = self.security_context.get_credentials()
            if not credentials:
                raise Exception("Kerberos凭证不可用")
            
            # 执行Kerberos认证的请求
            response, error_msg, _ = SecurityContext.krb_curl_request(
                jmx_url,
                credentials['keytab'],
                credentials['principal'],
                context="metric_alert",
                label=self.get_name(),
                connection_timeout=self.config.connection_timeout,
                kinit_timeout=credentials['kinit_timeout']
            )
            
            if error_msg:
                raise Exception(f"Kerberos请求失败: {error_msg}")
            
            return self._parse_jmx_response(response)
            
        except Exception as e:
            logger.error(f"[警报][{self.get_name()}] 通过Kerberos获取JMX数据失败: {str(e)}")
            raise
    
    def _retrieve_jmx_over_http(self, jmx_url: str) -> Dict:
        """通过HTTP获取JMX数据"""
        try:
            # 创建支持自动重定向的HTTP处理器
            url_opener = urllib.request.build_opener(RefreshHeaderProcessor())
            response = url_opener.open(jmx_url, timeout=self.config.connection_timeout)
            
            # 读取并解析响应
            content = response.read()
            return self._parse_jmx_response(content)
            
        except urllib.error.HTTPError as e:
            logger.error(f"[警报][{self.get_name()}] JMX HTTP错误 ({e.code}): {e.reason}")
            if e.code in [401, 403]:
                return self._handle_authentication_failure(jmx_url)
            return {}
        except Exception as e:
            logger.error(f"[警报][{self.get_name()}] 获取JMX数据失败: {str(e)}")
            return {}
    
    def _handle_authentication_failure(self, jmx_url: str) -> Dict:
        """处理身份验证失败情况"""
        logger.warning(f"[警报][{self.get_name()}] JMX访问需要身份验证，尝试Kerberos")
        
        # 尝试切换SecurityContext
        self.security_context.force_kerberos = True
        
        try:
            return self._retrieve_jmx_with_kerberos(jmx_url)
        except Exception:
            logger.error(f"[警报][{self.get_name()}] Kerberos JMX请求失败")
            return {}
    
    def _parse_jmx_response(self, content: Union[str, bytes]) -> Dict:
        """解析JMX响应为JSON对象"""
        try:
            # 确保内容为字符串
            if isinstance(content, bytes):
                content = content.decode('utf-8')
            
            jmx_data = json.loads(content)
            
            # 验证JMX响应格式
            if not isinstance(jmx_data, dict) or "beans" not in jmx_data:
                logger.error("[警报][%s] 无效的JMX响应格式: %s", self.get_name(), content[:100])
                return {}
            
            return jmx_data
        except json.JSONDecodeError:
            logger.error(f"[警报][{self.get_name()}] JMX响应JSON解析失败")
            return {}
        except Exception:
            logger.exception(f"[警报][{self.get_name()}] 处理JMX响应时出错")
            return {}
    
    def _determine_state(self, value: float) -> AlertState:
        """根据指标值和配置的阈值确定告警状态"""
        # 获取配置的阈值
        warn_val = self.config.warning_threshold
        crit_val = self.config.critical_threshold
        ok_val = self.config.ok_threshold
        
        # 如果没有配置任何阈值，返回OK
        if warn_val is None and crit_val is None:
            return AlertState.OK
        
        # 只配置了一个阈值的情况处理
        if warn_val is None and crit_val is not None:
            warn_val = crit_val * 0.8 if crit_val > 0 else crit_val * 1.2
        
        if crit_val is None and warn_val is not None:
            crit_val = warn_val * 1.25 if warn_val > 0 else warn_val * 0.8
        
        # 确定阈值方向 (critical_direction_up: True表示越大越严重)
        critical_direction_up = (crit_val >= warn_val)
        
        if critical_direction_up:
            # 临界方向向上 - 数值越大越危险
            if crit_val is not None and value >= crit_val:
                return AlertState.CRITICAL
            elif warn_val is not None and value >= warn_val:
                return AlertState.WARNING
            
            # 检查OK阈值
            if ok_val is not None:
                return AlertState.OK if value >= ok_val else AlertState.UNKNOWN
            return AlertState.OK
        else:
            # 临界方向向下 - 数值越小越危险
            if crit_val is not None and value <= crit_val:
                return AlertState.CRITICAL
            elif warn_val is not None and value <= warn_val:
                return AlertState.WARNING
            
            # 检查OK阈值
            if ok_val is not None:
                return AlertState.OK if value <= ok_val else AlertState.UNKNOWN
            return AlertState.OK
    
    def _build_result_details(self, values: List, calc_value: float) -> List:
        """构建结果详情列表"""
        # 包含所有原始值、计算值和字符串表示
        result = [value for value in values]
        result.append(calc_value)
        result.append(f"计算值: {calc_value:.4f}")
        return result
    
    def _log_collection_result(self, state: AlertState, details: List, url: str) -> None:
        """记录指标收集结果"""
        if state == AlertState.CRITICAL:
            logger.error(
                f"[警报][{self.get_name()}] CRITICAL: 指标值 {details[-2]:.4f} 超过阈值 | URL: {url} | 详情: {details}"
            )
        elif state == AlertState.WARNING:
            logger.warning(
                f"[警报][{self.get_name()}] WARNING: 指标值 {details[-2]:.4f} 接近阈值 | URL: {url} | 详情: {details}"
            )
        else:
            logger.info(
                f"[警报][{self.get_name()}] OK: 指标值 {details[-2]:.4f} | URL: {url}"
            )
    
    def _get_reporting_text(self, state: AlertState) -> str:
        """获取结果汇报文本模板"""
        return "{0}"


class JMXCollector(MetricCollector):
    """JMX指标收集器"""
    
    def __init__(self, jmx_info: Dict, alert_name: str):
        """
        初始化JMX收集器
        
        Args:
            jmx_info: JMX配置信息
            alert_name: 关联的告警名称
        """
        super().__init__(alert_name)
        self.property_map = {}
        self.calc_module = None
        
        # 初始化属性映射
        self._init_property_map(jmx_info.get("property_list", []))
        
        # 初始化计算公式（如果提供）
        if "value" in jmx_info:
            self._init_calculation_formula(jmx_info["value"])
    
    def _init_property_map(self, property_list: List) -> None:
        """初始化JMX属性映射"""
        for p in property_list:
            if '/' not in p:
                logger.error(f"[警报][{self.alert_name}] 无效的属性格式: {p}")
                continue
                
            bean, attr = p.split('/', 1)
            if bean not in self.property_map:
                self.property_map[bean] = set()
            self.property_map[bean].add(attr)
        
        # 创建JMX查询字符串
        self.jmx_query = ",".join([
            f"JmxName={bean}" for bean in self.property_map.keys()
        ])
        logger.debug(f"[警报][{self.alert_name}] JMX查询: {self.jmx_query}")
    
    def _init_calculation_formula(self, formula: str) -> None:
        """初始化指标计算公式"""
        try:
            # 安全验证公式
            validator = ASTValidator([SecurityRule()])
            validator.validate_expression(formula)
            
            # 创建动态模块
            module_name = f"metric_calc_{uuid.uuid4().hex}"
            module_spec = importlib.util.spec_from_loader(module_name, loader=None)
            self.calc_module = importlib.util.module_from_spec(module_spec)
            
            # 生成可执行代码
            real_code = METRIC_ARGUMENT_PATTERN.sub(r"args[\g<1>]", formula)
            code_str = f"def calculate(args):\n    return {real_code}"
            
            # 动态编译代码
            exec(code_str, self.calc_module.__dict__)
            logger.debug(f"[警报][{self.alert_name}] 公式编译成功: {formula} -> {real_code}")
            
        except Exception as e:
            logger.error(f"[警报][{self.alert_name}] 公式编译失败: {formula} | 错误: {str(e)}")
            raise MetricCalculationError(f"公式编译失败: {str(e)}")
    
    def collect(self, jmx_data: Dict) -> List:
        """从JMX数据收集所有指定的属性值"""
        metric_values = []
        
        # 检查JMX数据是否有效
        if not jmx_data or not jmx_data.get("beans"):
            return metric_values
        
        # 遍历所有JMX bean，查找所需属性
        for bean in jmx_data["beans"]:
            # 检查这个bean是否在需要的列表中
            bean_name = bean.get("name", "")
            if bean_name not in self.property_map:
                continue
            
            # 收集此bean的所有所需属性
            for attr in self.property_map[bean_name]:
                if attr not in bean:
                    logger.warning(
                        f"[警报][{self.alert_name}] 属性未找到: {attr} in {bean_name}"
                    )
                    metric_values.append(0.0)  # 使用默认值
                    continue
                
                metric_values.append(bean[attr])
        
        return metric_values
    
    def calculate(self, args: List) -> float:
        """使用配置公式计算指标值"""
        if not self.calc_module or not hasattr(self.calc_module, "calculate"):
            # 没有计算公式，返回None
            return None
            
        try:
            return self.calc_module.calculate(tuple(args))
        except Exception as e:
            logger.error(f"[警报][{self.alert_name}] 公式计算失败: {str(e)}")
            raise MetricCalculationError(f"公式计算失败: {str(e)}")


class MetricCalculationError(Exception):
    """指标计算错误异常类"""
    pass

