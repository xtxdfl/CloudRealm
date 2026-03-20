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
"""

import http.client
import logging
import re
import time
import urllib.parse
import json
import uuid
import importlib.util
from typing import Dict, Any, List, Tuple, Optional, Union

from alerts.metric_alert import MetricAlert
from cloud_commons.ast_validator import ASTValidator, SecurityRule

logger = logging.getLogger(__name__)

# AMS 指标接口路径
AMS_METRICS_GET_URL = "/ws/v1/timeline/metrics?%s"

# 正则匹配动态代码中的参数引�?PARAM_REF_REGEXP = re.compile(r"\{(\d+)\}")

# 指标计算相关统计函数
AGGREGATE_FUNCTIONS = {
    "mean": "统计平均�?,
    "count": "统计数据点数",
    "sample_standard_deviation": "计算样本标准�?,
    "sample_standard_deviation_percentage": "计算样本标准差的百分�?,
}

class AmsMetricProcessor:
    """AMS 指标处理器：负责动态计算指标�?""
    
    VALUE_CALC_TEMPLATE = """
from __future__ import division
import math

def calculate(args: list) -> list:
    results = []
    for k, values in args.items():
        try:
            data_point = {calculation_expression}
            results.append(data_point)
        except Exception as e:
            # 跳过计算异常的数据点
            continue
    return results
"""

    COMPUTE_CALC_TEMPLATE = """
from __future__ import division
from alerts.ams_statistics import *

def compute(data: list) -> float:
    return {aggregate_expression}
"""

    def __init__(self, metric_config: Dict):
        """
        初始�?AMS 指标处理�?        
        Args:
            metric_config: AMS 指标配置字典
        """
        self.metrics = metric_config.get("metric_list", [])
        self.interval = metric_config.get("interval", 5)  # 默认 5 分钟
        self.app_id = metric_config.get("app_id", "APP_DEFAULT")
        self.minimum_value = metric_config.get("minimum_value")
        
        # 初始化动态计算模�?        self.value_calculation_module = None
        self.compute_aggregation_module = None
        
        # 解析和验证指标值计算表达式
        value_expression = metric_config.get("value")
        if value_expression:
            self.value_calculation_module = self._create_dynamic_module(
                value_expression, 
                self.VALUE_CALC_TEMPLATE,
                "value_calculation",
                {"calculation_expression": self._transform_expression(value_expression)}
            )
        
        # 解析和验证聚合计算表达式
        compute_expression = metric_config.get("compute")
        if compute_expression:
            self.compute_aggregation_module = self._create_dynamic_module(
                compute_expression,
                self.COMPUTE_CALC_TEMPLATE,
                "compute_aggregation",
                {"aggregate_expression": self._transform_expression(compute_expression)}
            )
    
    def _transform_expression(self, expression: str) -> str:
        """转换指标表达式中的参数引用格�?""
        # �?{0}, {1} 等替换为 value[0], value[1]
        return PARAM_REF_REGEXP.sub(r'values[\g<1>]', expression)
    
    def _create_dynamic_module(
        self, 
        expression: str,
        template: str, 
        module_type: str,
        context: Dict
    ) -> Any:
        """
        动态创建计算模�?        
        Args:
            expression: 用户定义的指标表达式
            template: 代码模板
            module_type: 模块类型标识（用于日志）
            context: 模板格式化上下文
            
        Returns:
            动态生成的模块对象
        """
        try:
            # 安全验证表达�?            validator = ASTValidator([SecurityRule()])
            if not validator.validate_expression(expression):
                raise ValueError(f"表达式存在安全问�? {expression}")
            
            # 生成模块名称
            module_name = f"ams_{module_type}_{uuid.uuid4().hex}"
            module_spec = importlib.util.spec_from_loader(module_name, loader=None)
            dynamic_module = importlib.util.module_from_spec(module_spec)
            
            # 生成可执行代�?            code_str = template.format(**context)
            
            # 动态编译代�?            exec(code_str, dynamic_module.__dict__)
            logger.debug(f"[AMS] 成功编译 {module_type} 表达�? {expression}")
            
            return dynamic_module
        except Exception as e:
            logger.error(f"[AMS] {module_type} 表达式编译失�? {expression} | 错误: {str(e)}")
            raise
    
    def calculate_values(self, metric_data: Dict) -> List:
        """
        计算处理后的指标值列�?        
        Args:
            metric_data: 原始指标数据字典
            
        Returns:
            处理后的指标值列�?        """
        if not self.value_calculation_module:
            # 如果没有值计算表达式，则返回原始�?            return [
                values for metrics in metric_data.values()
                for values in metrics.values() 
                if metrics
            ]
        
        try:
            # 调用动态函数计算结�?            result = self.value_calculation_module.calculate(metric_data)
            
            # 过滤掉小于最小值的�?            if self.minimum_value is not None:
                result = [v for v in result if v > self.minimum_value]
                
            return result
        except Exception as e:
            logger.error(f"[AMS] 指标值计算错�? {str(e)}")
            return []
    
    def compute_result(self, values: List) -> Optional[float]:
        """
        执行聚合计算并返回结�?        
        Args:
            values: 指标值列�?            
        Returns:
            计算结果�?        """
        if not self.compute_aggregation_module or not values:
            return None
            
        try:
            return self.compute_aggregation_module.compute(values)
        except Exception as e:
            logger.error(f"[AMS] 聚合计算错误: {str(e)}")
            return None


class AmsAlert(MetricAlert):
    """
    AMS 指标告警�?    基于 cloud Metrics Service 收集指标数据并触发告�?    """

    def __init__(self, alert_meta: Dict, alert_source_meta: Dict, config: Any):
        """
        初始�?AMS 告警
        
        Args:
            alert_meta: 告警元数�?            alert_source_meta: 告警来源元数�?            config: 配置对象
        """
        super().__init__(alert_meta, alert_source_meta, config)
        
        # 初始�?AMS 指标处理�?        ams_config = alert_source_meta.get("ams", {})
        self.metric_processor = AmsMetricProcessor(ams_config)
    
    def _collect(self) -> Tuple[str, List]:
        """
        收集告警数据
        
        Returns:
            元组 (告警状�? 数据详情)
        """
        # 验证必要的配置是否存�?        if not self.metric_processor:
            return self.RESULT_UNKNOWN, ["AMS 指标处理器未配置"]
            
        if not self.uri_property_keys:
            return self.RESULT_UNKNOWN, ["URI 配置缺失"]
        
        # 获取 AMS 服务地址
        try:
            ams_uri = self._get_ams_service_uri()
        except Exception as e:
            return self.RESULT_UNKNOWN, [f"获取 AMS 服务地址失败: {str(e)}"]
            
        # �?AMS 获取指标数据
        raw_metrics, http_status = self._retrieve_ams_metrics(ams_uri)
        if not raw_metrics or http_status != http.client.OK:
            return self._handle_ams_failure(http_status)
        
        # 处理指标数据
        processed_values = self.metric_processor.calculate_values(raw_metrics)
        if not processed_values:
            return self.RESULT_UNKNOWN, ["无有效指标数�?]
            
        # 计算结果�?        compute_result = self.metric_processor.compute_result(processed_values)
        if compute_result is None:
            return self.RESULT_UNKNOWN, ["指标计算结果为空"]
            
        # 记录计算结果
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"[Alert][{self.get_name()}] AMS 计算结果 = {compute_result:.4f}")
        
        # 确定告警状�?        alert_state = self._determine_state(compute_result)
        
        return alert_state, [compute_result, f"计算�? {compute_result:.4f}"]
    
    def _get_ams_service_uri(self) -> Tuple[bool, str, int]:
        """
        获取 AMS 服务地址信息
        
        Returns:
            元组 (是否启用 SSL, 主机地址, 端口�?
        """
        # 获取 URI 配置信息
        alert_uri = self._get_uri_from_structure(self.uri_property_keys)
        if not alert_uri:
            raise ValueError("URI 结构解析失败")
            
        # 提取主机和端�?        host = str(alert_uri.uri)
        if "://" in host:
            host = host.split("://", 1)[1]
        
        # 去除路径部分
        if "/" in host:
            host = host.split("/", 1)[0]
            
        # 分离主机和端�?        if ":" in host:
            host, port_str = host.split(":", 1)
            try:
                port = int(port_str)
            except ValueError:
                port = 6188 if not alert_uri.is_ssl_enabled else 6189
        else:
            port = 6188 if not alert_uri.is_ssl_enabled else 6189
            
        # 处理0.0.0.0特殊地址
        if "0.0.0.0" in host:
            host = self.host_name
            
        return alert_uri.is_ssl_enabled, host, port
    
    def _retrieve_ams_metrics(
        self, 
        ams_uri: Tuple[bool, str, int]
    ) -> Tuple[Dict, int]:
        """
        �?AMS 服务获取指标数据
        
        Args:
            ams_uri: AMS 服务地址元组 (is_ssl_enabled, host, port)
            
        Returns:
            元组 (指标数据字典, HTTP 状态码)
        """
        is_ssl_enabled, host, port = ams_uri
        
        # 准备查询参数
        current_time = int(time.time()) * 1000  # AMS 使用毫秒时间�?        interval_ms = self.metric_processor.interval * 60 * 1000  # 分钟转毫�?        
        query_params = {
            "metricNames": ",".join(self.metric_processor.metrics),
            "appId": self.metric_processor.app_id,
            "hostname": self.host_name,
            "startTime": current_time - interval_ms,
            "endTime": current_time,
            "precision": "seconds",
            "grouped": "true",
        }
        encoded_params = urllib.parse.urlencode(query_params)
        url = AMS_METRICS_GET_URL % encoded_params
        
        # 记录调试信息
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"[AMS] 请求URL: {host}:{port}{url}")
            logger.debug(f"[AMS] 查询参数: {query_params}")
        
        # 发�?HTTP/HTTPS 请求
        try:
            connection = None
            if is_ssl_enabled:
                connection = http.client.HTTPSConnection(host, port, timeout=self.connection_timeout)
            else:
                connection = http.client.HTTPConnection(host, port, timeout=self.connection_timeout)
            
            connection.request("GET", url)
            response = connection.getresponse()
            
            # 检查响应状�?            if response.status != http.client.OK:
                logger.warning(f"[AMS] HTTP错误: {response.status} {response.reason}")
                return {}, response.status
                
            # 读取响应内容
            data = response.read()
            
            # 解析 JSON 响应
            try:
                json_data = json.loads(data)
                if "metrics" not in json_data:
                    logger.warning("[AMS] 响应缺少 'metrics' 字段")
                    return {}, http.client.INTERNAL_SERVER_ERROR
                    
                # 组织指标数据
                metrics_dict = {
                    metric["metricname"]: metric["metrics"]
                    for metric in json_data["metrics"]
                }
                return metrics_dict, response.status
            except json.JSONDecodeError:
                logger.error(f"[AMS] JSON解析失败，响应数�? {data[:200]}...")
                return {}, http.client.INTERNAL_SERVER_ERROR
        except http.client.HTTPException as e:
            logger.error(f"[AMS] HTTP请求异常: {str(e)}")
            return {}, http.client.INTERNAL_SERVER_ERROR
        except Exception as e:
            logger.error(f"[AMS] 处理请求时发生系统错�? {str(e)}")
            return {}, http.client.INTERNAL_SERVER_ERROR
        finally:
            # 确保关闭连接
            if connection:
                try:
                    connection.close()
                except Exception:
                    logger.debug(f"[AMS] 关闭连接时发生错�?)
    
    def _handle_ams_failure(self, http_status: int) -> Tuple[str, List]:
        """
        处理 AMS 请求失败情况
        
        Args:
            http_status: HTTP 状态码
            
        Returns:
            元组 (告警状�? 数据详情)
        """
        status_text = http.client.responses.get(http_status, "未知状�?)
        
        if http_status == http.client.NOT_FOUND:
            return self.RESULT_UNKNOWN, [f"AMS 资源不存�?(404)"]
        elif http_status == http.client.UNAUTHORIZED:
            return self.RESULT_CRITICAL, [f"AMS 访问未授�?(401)"]
        elif http_status == http.client.FORBIDDEN:
            return self.RESULT_CRITICAL, [f"AMS 访问被禁�?(403)"]
        elif http_status == http.client.BAD_GATEWAY or http_status == http.client.SERVICE_UNAVAILABLE:
            return self.RESULT_CRITICAL, [f"AMS 服务不可�?({http_status} {status_text})"]
        elif http_status >= 500:
            return self.RESULT_CRITICAL, [f"AMS 服务器错�?({http_status} {status_text})"]
        else:
            return self.RESULT_UNKNOWN, [f"AMS 请求失败 ({http_status} {status_text})"]
    
    def _determine_state(self, value: float) -> str:
        """
        根据指标值和阈值确定告警状�?        
        Args:
            value: 指标计算结果�?            
        Returns:
            告警状�?(OK, WARNING, CRITICAL, UNKNOWN)
        """
        # 获取配置的阈�?        warning_threshold = self.warning_threshold
        critical_threshold = self.critical_threshold
        
        # 如果没有配置任何阈值，默认返回OK
        if warning_threshold is None and critical_threshold is None:
            return self.RESULT_OK
        
        # 如果没有配置CRITICAL阈值，但配置了WARNING阈值，计算CRITICAL阈�?        if critical_threshold is None and warning_threshold is not None:
            critical_threshold = warning_threshold * 1.25 if warning_threshold > 0 else warning_threshold * 0.8
        
        # 确定阈值方向（critical_direction_up: True表示值越大越严重�?        critical_direction_up = (critical_threshold >= warning_threshold or critical_threshold) 
        
        if critical_direction_up:
            # 临界方向向上 - 值越大越严重
            if critical_threshold and value >= critical_threshold:
                return self.RESULT_CRITICAL
            elif warning_threshold and value >= warning_threshold:
                return self.RESULT_WARNING
        else:
            # 临界方向向下 - 值越小越严重
            if critical_threshold and value <= critical_threshold:
                return self.RESULT_CRITICAL
            elif warning_threshold and value <= warning_threshold:
                return self.RESULT_WARNING
        
        # 所有检查都通过，返回OK
        return self.RESULT_OK
