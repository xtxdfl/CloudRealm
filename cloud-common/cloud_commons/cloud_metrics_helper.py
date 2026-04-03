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

import json
import logging
import os
import random
import urllib.request
import urllib.parse
import urllib.error
import time
import socket
import ssl
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass

# 配置日志系统
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("cloudMetrics")

# 常量定义
DEFAULT_COLLECTOR_SUFFIX = ".sink.timeline.collector.hosts"
DEFAULT_METRICS2_PROPS_FILENAME = "hadoop-metrics2.properties"
AMS_METRICS_GET_URL = "/ws/v1/timeline/metrics?%s"

# 配置键名
METRICS_COLLECTOR_WEBAPP_ADDRESS = "{{ams-site/timeline.metrics.service.webapp.address}}"
METRICS_COLLECTOR_VIP_HOST = "{{cluster-env/metrics_collector_external_hosts}}"
METRICS_COLLECTOR_VIP_PORT = "{{cluster-env/metrics_collector_external_port}}"
AMS_METRICS_COLLECTOR_USE_SSL = "{{ams-site/timeline.metrics.service.http.policy}}"
CONNECTION_TIMEOUT_KEY = "http.connection.timeout"
CONNECTION_TIMEOUT_DEFAULT = 5.0

# 高级配置
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 1
CONNECTION_POOL_SIZE = 5
REQUEST_TIMEOUT = 10  # �?
class CollectorType(Enum):
    """指标收集器类�?""
    VIP = "vip"  # 虚拟IP模式 (高可�?
    DIRECT = "direct"  # 直连模式
    AUTO_DISCOVER = "auto_discover"  # 自动发现

class MetricPrecision(Enum):
    """指标数据精度"""
    SECONDS = "seconds"
    MINUTES = "minutes"
    HOURS = "hours"

@dataclass
class MetricQuery:
    """指标查询参数"""
    metric_names: List[str]
    host_filter: str
    app_id: str
    start_time: Optional[int] = None  # UTC时间�?�?
    end_time: Optional[int] = None    # UTC时间�?�?
    precision: MetricPrecision = MetricPrecision.SECONDS

class ConfigurationError(Exception):
    """配置相关错误"""
    pass

class MetricServiceError(Exception):
    """指标服务错误"""
    pass

class MetricQueryError(Exception):
    """指标查询错误"""
    pass

class AmsResponseParser:
    """AMS响应解析�?""
    
    @staticmethod
    def parse_metrics_response(data: str) -> Dict[str, Any]:
        """解析AMS原始响应数据"""
        try:
            response = json.loads(data)
            if not isinstance(response, dict) or "metrics" not in response:
                raise MetricServiceError("无效的AMS响应格式")
            
            return response
        except json.JSONDecodeError as e:
            raise MetricServiceError(f"JSON解析失败: {str(e)}")
    
    @staticmethod
    def extract_metrics(data: Dict) -> Dict[str, List]:
        """从解析后的响应中提取指标"""
        metric_dict = {}
        for metrics_data in data.get("metrics", []):
            metric_name = metrics_data.get("metricname")
            if metric_name:
                metric_dict[metric_name] = metrics_data.get("metrics", [])
        return metric_dict
    
    @staticmethod
    def combine_metric_dicts(dicts: List[Dict]) -> Dict[str, List]:
        """合并多个指标字典"""
        combined = {}
        for d in dicts:
            for metric, values in d.items():
                if metric not in combined:
                    combined[metric] = []
                combined[metric].extend(values)
        return combined

class AMSClient:
    """cloud Metrics Service (AMS) 客户�?""
    
    def __init__(self,
                 collector_type: CollectorType = CollectorType.AUTO_DISCOVER,
                 hosts: List[str] = None,
                 port: int = None,
                 use_ssl: bool = False,
                 timeout: float = CONNECTION_TIMEOUT_DEFAULT,
                 app_id: str = "cloud_agent",
                 connection_pool_size: int = CONNECTION_POOL_SIZE):
        """
        参数:
            collector_type: 收集器类�?(VIP/DIRECT/AUTO_DISCOVER)
            hosts: 收集器主机列�?(仅当使用VIP或DIRECT�?
            port: 收集器端�?            use_ssl: 是否使用HTTPS
            timeout: 连接超时时间 (�?
            app_id: 应用程序ID
            connection_pool_size: HTTP连接池大�?        """
        self.collector_type = collector_type
        self.hosts = hosts or []
        self.port = port or 6188
        self.use_ssl = use_ssl
        self.timeout = timeout
        self.app_id = app_id
        self.conn_pool = self._init_conn_pool(connection_pool_size)
        self.last_active_host = None
    
    def _init_conn_pool(self, size: int) -> List['HTTPSConnection']:
        """初始化HTTP连接�?""
        if self.collector_type == CollectorType.AUTO_DISCOVER:
            self._auto_discover_config()
        
        if not self.hosts:
            raise ConfigurationError("未配置指标收集器主机")
        
        pool = []
        for host in random.sample(self.hosts, min(len(self.hosts), size)):
            try:
                if self.use_ssl:
                    ctx = ssl.create_default_context()
                    ctx.set_ciphers('HIGH:!aNULL:!eNULL:!MD5')
                    conn = HTTPSConnection(host, self.port, timeout=self.timeout, context=ctx)
                else:
                    conn = HTTPConnection(host, self.port, timeout=self.timeout)
                pool.append(conn)
            except Exception as e:
                logger.warning(f"创建连接�?{host}:{self.port} 失败: {str(e)}")
        
        if not pool:
            raise ConnectionError("无法创建任何有效的指标收集器连接")
        
        return pool
    
    def _auto_discover_config(self):
        """自动发现AMS配置"""
        try:
            self._load_config_from_properties()
            logger.info("已从配置文件加载AMS配置")
        except Exception as e:
            logger.warning(f"无法发现AMS配置: {str(e)}")
    
    def _load_config_from_properties(self):
        """从配置文件加载AMS配置"""
        # 获取Hadoop配置目录
        hadoop_conf_dir = self._get_hadoop_conf_dir()
        
        # 读取hadoop-metrics2.properties
        props = self._load_properties_file(
            hadoop_conf_dir / DEFAULT_METRICS2_PROPS_FILENAME
        )
        
        # 自动检测收集器主机
        self.hosts = []
        for key, value in props.items():
            if key.endswith(DEFAULT_COLLECTOR_SUFFIX):
                self.hosts.extend(value.split(","))
        
        # 检测端口和SSL使用
        self._detect_port_and_ssl(props)
        
        # 如未找到主机，则使用默认配置
        if not self.hosts:
            self.hosts = ["localhost"]
        
        logger.debug(f"从配置加载的AMS主机: {self.hosts}, 端口: {self.port}, SSL: {self.use_ssl}")
    
    def _get_hadoop_conf_dir(self) -> Path:
        """获取Hadoop配置目录"""
        # 示例逻辑 - 实际实现可能需要根据环境调�?        candidates = [
            "/etc/hadoop/conf",
            "/usr/hdp/current/hadoop-client/conf",
            os.environ.get("HADOOP_CONF_DIR")
        ]
        
        for candidate in candidates:
            if candidate and (path := Path(candidate)).exists():
                return path
        
        raise FileNotFoundError("找不到有效的Hadoop配置目录")
    
    def _load_properties_file(self, filepath: Path, sep: str = "=") -> Dict[str, str]:
        """加载属性文�?""
        if not filepath.exists():
            raise FileNotFoundError(f"属性文件不存在: {filepath}")
        
        props = {}
        with filepath.open('rt', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split(sep, 1)  # 只分割一�?                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip('" \t')
                        props[key] = value
        return props
    
    def _detect_port_and_ssl(self, props: Dict[str, str]):
        """从属性中检测端口和SSL使用"""
        # 检测端�?        for key, value in props.items():
            if "webapp.address" in key:
                if ":" in value:
                    self.port = int(value.split(":")[1])
                break
        
        # 检测SSL使用
        for key, value in props.items():
            if "http.policy" in key:
                self.use_ssl = value.lower() == "https_only"
                break
    
    def get_connection(self) -> 'HTTPSConnection':
        """从池中获取连�?""
        if not self.conn_pool:
            self._rotate_connections()
        
        # 优先使用上次成功的主�?        if self.last_active_host:
            for conn in self.conn_pool:
                if conn.host == self.last_active_host:
                    return conn
        
        # 随机选择连接
        return random.choice(self.conn_pool)
    
    def release_connection(self, conn: 'HTTPSConnection'):
        """释放连接回池�?""
        # 在此实现中，连接始终保持在池�?        pass
    
    def _rotate_connections(self):
        """轮换连接�?""
        # 关闭所有当前连�?        if hasattr(self, 'conn_pool'):
            for conn in self.conn_pool:
                try:
                    conn.close()
                except:
                    pass
        
        # 创建新连�?        self.conn_pool = self._init_conn_pool(len(self.conn_pool) if hasattr(self, 'conn_pool') else CONNECTION_POOL_SIZE)
        logger.info("轮换AMS连接�?)
    
    def query_metrics(self, query: MetricQuery) -> Dict[str, Any]:
        """查询指标数据"""
        for retry_count in range(MAX_RETRIES + 1):
            try:
                return self._try_query_metrics(query)
            except (MetricQueryError, ConnectionError) as e:
                if retry_count == MAX_RETRIES:
                    raise
                delay = RETRY_DELAY_SECONDS * (2 ** retry_count)  # 指数退�?                logger.warning(f"�?{retry_count+1} 次查询失�? {str(e)}，等�?{delay:.1f}秒后重试")
                time.sleep(delay)
                self._rotate_connections()  # 轮换连接�?    
    def _try_query_metrics(self, query: MetricQuery) -> Dict[str, Any]:
        """执行指标查询"""
        conn = self.get_connection()
        url = self._build_metrics_url(query)
        
        try:
            # 构造请�?            headers = {
                "User-Agent": "cloudMetricsClient/1.0",
                "Accept": "application/json"
            }
            
            # 发起请求
            conn.request("GET", url, headers=headers)
            response = conn.getresponse()
            
            # 检查响�?            if response.status != 200:
                raise MetricQueryError(f"AMS返回�?00状态码: {response.status} {response.reason}")
            
            # 读取响应数据
            data = response.read().decode('utf-8')
            
            # 记录成功的主�?            self.last_active_host = conn.host
            
            # 解析响应
            return self._parse_response(data, url, query)
        except (socket.timeout, socket.error) as e:
            conn.close()
            raise ConnectionError(f"连接错误: {str(e)}") from e
        finally:
            if hasattr(conn, 'release'):  # 确保兼容
                conn.release()
    
    def _build_metrics_url(self, query: MetricQuery) -> str:
        """构造指标查询URL"""
        params = {
            "metricNames": ",".join(query.metric_names),
            "appId": self.app_id,
            "hostname": query.host_filter,
            "precision": query.precision.value,
            "grouped": "true"
        }
        
        if query.start_time:
            params["startTime"] = str(query.start_time)
        if query.end_time:
            params["endTime"] = str(query.end_time)
        
        encoded_params = urllib.parse.urlencode(params)
        return AMS_METRICS_GET_URL % encoded_params
    
    def _parse_response(self, data: str, original_url: str, query: MetricQuery) -> Dict[str, Any]:
        """解析并处理响应数�?""
        try:
            # 解析原始响应
            response_data = AmsResponseParser.parse_metrics_response(data)
            
            # 提取指标
            metrics = AmsResponseParser.extract_metrics(response_data)
            
            # 丰富响应数据
            return {
                "request": {
                    "url": original_url,
                    "app_id": self.app_id,
                    "host_filter": query.host_filter,
                    "metrics": query.metric_names,
                    "timestamps": [query.start_time, query.end_time]
                },
                "response": {
                    "status": "success",
                    "metrics_count": len(metrics),
                    "collected_at": int(time.time()),
                    "data": metrics
                }
            }
        except MetricServiceError as e:
            # 详细错误诊断
            error_context = {
                "error": str(e),
                "query_metrics": query.metric_names,
                "response_data": data if len(data) < 1000 else data[:1000] + "...",
                "request_url": original_url
            }
            raise MetricQueryError(f"指标解析失败: {json.dumps(error_context, indent=2)}")
    
    def fetch_metric_value(self, metric_name: str, host_filter: str) -> float:
        """获取指标的最新值（简化接口）"""
        # 当前时间戳和5分钟前的时间�?        current_time = int(time.time())
        five_minutes_ago = current_time - 300
        
        query = MetricQuery(
            metric_names=[metric_name],
            host_filter=host_filter,
            app_id=self.app_id,
            start_time=five_minutes_ago,
            end_time=current_time,
            precision=MetricPrecision.SECONDS
        )
        
        result = self.query_metrics(query)
        metric_data = result["response"]["data"].get(metric_name, [])
        
        if not metric_data:
            raise MetricQueryError(f"未找到指�? {metric_name}")
        
        # 获取最新的指标�?        latest_point = sorted(metric_data, key=lambda x: x["timestamp"], reverse=True)[0]
        return latest_point["value"]

class HTTPSConnection(urllib.request.HTTPSConnection):
    """自定义HTTPS连接类，支持连接�?""
    def __init__(self, host, port=None, **kwargs):
        # 使用较新的TLS版本
        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        kwargs.setdefault("context", context)
        
        # 设置合理的超�?        kwargs.setdefault("timeout", REQUEST_TIMEOUT)
        
        super().__init__(host, port, **kwargs)
        self.host = host
    
    def release(self):
        """释放连接到池中（虚拟实现�?""
        pass

class HTTPConnection(urllib.request.HTTPConnection):
    """自定义HTTP连接类，支持连接�?""
    def release(self):
        """释放连接到池中（虚拟实现�?""
        pass

def create_ams_client_from_config(configurations: Dict[str, str], 
                                  parameters: Dict[str, str] = None, 
                                  default_app_id: str = "cloud_agent") -> AMSClient:
    """根据配置创建AMS客户�?""
    # 获取VIP配置
    vip_host = configurations.get(METRICS_COLLECTOR_VIP_HOST)
    vip_port = configurations.get(METRICS_COLLECTOR_VIP_PORT)
    
    # 优先使用VIP配置
    if vip_host and vip_port:
        try:
            vip_hosts = vip_host.split(",")
            vip_port = int(vip_port)
            use_ssl = configurations.get(AMS_METRICS_COLLECTOR_USE_SSL) == "HTTPS_ONLY"
            
            logger.info(f"使用VIP模式创建AMS客户�? hosts={vip_hosts}, port={vip_port}")
            return AMSClient(
                collector_type=CollectorType.VIP,
                hosts=vip_hosts,
                port=vip_port,
                use_ssl=use_ssl,
                timeout=float(parameters.get(CONNECTION_TIMEOUT_KEY, CONNECTION_TIMEOUT_DEFAULT)),
                app_id=default_app_id
            )
        except Exception as e:
            logger.error(f"VIP配置无效，尝试直连模�? {str(e)}")
    
    # 使用直连配置
    direct_address = configurations.get(METRICS_COLLECTOR_WEBAPP_ADDRESS)
    if direct_address and ":" in direct_address:
        host, port_str = direct_address.split(":", 1)
        try:
            port = int(port_str)
            use_ssl = configurations.get(AMS_METRICS_COLLECTOR_USE_SSL) == "HTTPS_ONLY"
            
            logger.info(f"使用直连模式创建AMS客户�? host={host}, port={port}")
            return AMSClient(
                collector_type=CollectorType.DIRECT,
                hosts=[host],
                port=port,
                use_ssl=use_ssl,
                timeout=float(parameters.get(CONNECTION_TIMEOUT_KEY, CONNECTION_TIMEOUT_DEFAULT)),
                app_id=default_app_id
            )
        except Exception as e:
            logger.error(f"直连配置无效: {str(e)}")
    
    # 自动发现模式
    logger.warning("使用默认配置，尝试自动发现AMS服务")
    return AMSClient(
        collector_type=CollectorType.AUTO_DISCOVER,
        timeout=float(parameters.get(CONNECTION_TIMEOUT_KEY, CONNECTION_TIMEOUT_DEFAULT)),
        app_id=default_app_id
    )

# =============== 高级用例示例 ===============
def monitor_cpu_usage(ams_client: AMSClient, hostname: str) -> float:
    """监控主机的CPU使用�?""
    try:
        return ams_client.fetch_metric_value("cpu_total.system.load", hostname)
    except Exception as e:
        logger.error(f"CPU使用率监控失�? {str(e)}")
        return 0.0

def gather_host_metrics(ams_client: AMSClient, hostname: str) -> Dict[str, Any]:
    """收集主机的关键指�?""
    try:
        query = MetricQuery(
            metric_names=[
                "cpu_total.system.load",
                "memory.free",
                "diskspace./.used",
                "network.tx.packets"
            ],
            host_filter=hostname,
            app_id="cloud_monitor",
            precision=MetricPrecision.MINUTES
        )
        
        return ams_client.query_metrics(query)
    except Exception as e:
        logger.error(f"主机指标采集失败: {str(e)}")
        return {}

def generate_system_report(ams_client: AMSClient, node_list: List[str]):
    """生成系统的性能报告"""
    start_time = int(time.time()) - 86400  # 过去24小时
    end_time = int(time.time())
    
    report_data = {
        "generated_at": end_time,
        "scope": "system",
        "time_range": [start_time, end_time],
        "nodes": []
    }
    
    # 收集每个节点的指�?    for node in node_list:
        logger.info(f"正在收集节点 {node} 的指�?..")
        
        query = MetricQuery(
            metric_names=[
                "cpu_total.system.load_avg",
                "memory.utilization",
                "disk.utilization",
                "network.traffic_in",
                "network.traffic_out"
            ],
            host_filter=node,
            app_id="cloud_system_report",
            start_time=start_time,
            end_time=end_time,
            precision=MetricPrecision.HOURS
        )
        
        try:
            node_metrics = ams_client.query_metrics(query)
            report_data["nodes"].append({
                "node": node,
                "metrics": {k: self._process_timeseries(v) for k, v in node_metrics["response"]["data"].items()}
            })
        except Exception as e:
            logger.error(f"节点 {node} 数据收集失败: {str(e)}")
            report_data["nodes"].append({
                "node": node,
                "error": str(e)
            })
    
    return report_data

if __name__ == "__main__":
    # 示例配置
    configs = {
        "{{ams-site/timeline.metrics.service.webapp.address}}": "metrics-collector.example.com:6188",
        "{{ams-site/timeline.metrics.service.http.policy}}": "HTTP_ONLY",
    }
    
    # 创建客户�?    try:
        client = create_ams_client_from_config(configs)
        
        # 示例使用: 获取CPU使用�?        cpu_usage = monitor_cpu_usage(client, "node01.example.com")
        logger.info(f"当前CPU使用�? {cpu_usage:.2f}%")
        
        # 获取完整度量数据
        host_metrics = gather_host_metrics(client, "node02.example.com")
        for metric, data in host_metrics["response"]["data"].items():
            logger.info(f"{metric} 最新�? {data[-1]['value']}")
        
        # 生成系统报告
        report = generate_system_report(client, ["node01", "node02", "node03"])
        logger.info(f"系统报告生成成功，共收集 {len(report['nodes'])} 个节点的数据")
        
    except Exception as e:
        logger.exception("AMS客户端初始化失败!")
        raise
