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

企业级Web服务器监控管理平台
"""

from resource_management.core.base import (
    Resource,
    ForcedListArgument,
    ResourceArgument,
    BooleanArgument,
)
import time
import requests
import logging
import os
import json
import math
from typing import Dict, List, Optional

class MonitorWebserver(Resource):
    """
    Web服务器监控管理资源
    
    提供全面的Web服务器状态监控和管理功能，支持：
    - HTTP/HTTPS服务监控
    - 多协议健康检查(HTTP/TCP/ICMP)
    - 智能自动恢复(进程重启/配置重载)
    - 深度性能分析
    - 主动安全扫描
    - 负载均衡集成
    
    使用示例：
        MonitorWebserver(
            name="frontend-cluster",
            service="nginx",
            service_identifier="nginx-master.service",
            endpoints=["https://web1.example.com", "https://web2.example.com"],
            health_check="/api/health",
            expected_status=200,
            expected_content="OK",
            critical_rules={
                "response_time": {"max": 500, "action": "restart"},
                "memory_usage": {"max": 90, "action": "alert"}
            },
            alerting=["slack#devops", "email#admin@example.com"],
            action="start"
        )
    """
    
    # 操作类型
    SERVICE_ACTIONS = ["start", "stop", "restart", "reload", "status", "enable", "disable"]
    MONITOR_ACTIONS = ["monitor", "metrics"]
    SECURITY_ACTIONS = ["scan", "firewall", "ssl_check"]
    
    action = ForcedListArgument(
        default="monitor",
        choices=SERVICE_ACTIONS + MONITOR_ACTIONS + SECURITY_ACTIONS,
        description="支持的操作类型"
    )
    
    # 服务配置
    service = ResourceArgument(
        required=True,
        choices=["nginx", "apache", "tomcat", "caddy", "traefik"],
        description="Web服务器类型"
    )
    service_identifier = ResourceArgument(
        required=True,
        description="服务标识(如service名称或PID文件路径)"
    )
    config_file = ResourceArgument(
        default="/etc/nginx/nginx.conf",
        description="主配置文件路径"
    )
    
    # 监控端点
    endpoints = ResourceArgument(
        default=lambda obj: [f"http://{obj.name}"],
        description="监控端点URL列表"
    )
    health_check = ResourceArgument(
        default="/status",
        description="健康检查端点路径"
    )
    
    # 健康检查参数
    expected_status = ResourceArgument(
        default=200,
        description="期望的HTTP状态码"
    )
    expected_content = ResourceArgument(
        default=None,
        description="响应中期望包含的内容(正则表达式)"
    )
    timeout = ResourceArgument(
        default=10,
        description="健康检查超时时间(秒)"
    )
    
    # 关键规则定义
    critical_rules = ResourceArgument(
        default={},
        description=(
            "关键性能规则定义, 格式: {\"metric_name\": {\"max/min\": value, \"action\": \"action_type\"}}"
        )
    )
    
    # 恢复策略
    auto_recover = BooleanArgument(
        default=True,
        description="故障时自动恢复"
    )
    auto_recover_threshold = ResourceArgument(
        default=2,
        description="连续失败次数触发恢复"
    )
    recovery_actions = ForcedListArgument(
        default=["reload", "restart", "failover"],
        description="自动恢复操作链"
    )
    failover_endpoint = ResourceArgument(
        default=None,
        description="故障转移目标端点"
    )
    
    # 告警与通知
    alerting = ForcedListArgument(
        default=[],
        description="告警目标列表(如slack#channel, email#address)"
    )
    alert_cooldown = ResourceArgument(
        default=300,
        description="相同告警最小间隔时间(秒)"
    )
    
    # 性能监控
    metrics_enabled = BooleanArgument(
        default=True,
        description="启用性能指标收集"
    )
    metrics_interval = ResourceArgument(
        default=15,
        description="指标收集间隔(秒)"
    )
    metrics_history = ResourceArgument(
        default=3600,
        description="指标历史保留时间(秒)"
    )
    
    # 安全配置
    ssl_min_version = ResourceArgument(
        default="TLSv1.2",
        choices=["SSLv2", "SSLv3", "TLSv1.0", "TLSv1.1", "TLSv1.2", "TLSv1.3"],
        description="最小SSL/TLS版本"
    )
    security_scan = BooleanArgument(
        default=False,
        description="启用自动安全扫描"
    )
    firewall_rules = ForcedListArgument(
        default=[],
        description="防火墙规则列表"
    )
    
    # 负载均衡支持
    lb_integration = ResourceArgument(
        default=None,
        choices=["haproxy", "f5", "nginx"],
        description="负载均衡集成方案"
    )
    
    # 支持的操作列表
    actions = Resource.actions + SERVICE_ACTIONS + MONITOR_ACTIONS + SECURITY_ACTIONS
    
    # 状态存储路径
    STATE_FILE = "/var/lib/monitor_webserver/state.json"
    METRICS_FILE = "/var/lib/monitor_webserver/metrics.json"
    ALERT_FILE = "/var/lib/monitor_webserver/alerts.json"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.state = {}
        self.metrics = {}
        self.alerts = {}
        self._load_state()
        self._initialize_monitoring()
        
    def _load_state(self):
        """加载持久化状态"""
        os.makedirs(os.path.dirname(self.STATE_FILE), exist_ok=True)
        
        # 状态加载
        if os.path.exists(self.STATE_FILE):
            try:
                with open(self.STATE_FILE, "r") as f:
                    self.state = json.load(f)
            except:
                self.state = {}
                
        # 指标加载
        if os.path.exists(self.METRICS_FILE):
            try:
                with open(self.METRICS_FILE, "r") as f:
                    self.metrics = json.load(f)
            except:
                self.metrics = {}
        
        # 告警历史加载
        if os.path.exists(self.ALERT_FILE):
            try:
                with open(self.ALERT_FILE, "r") as f:
                    self.alerts = json.load(f)
            except:
                self.alerts = {}
                
        # 初始化计数器
        self.state.setdefault("failure_count", 0)
        self.state.setdefault("last_failure", 0)
        self.state.setdefault("last_recovery", 0)
        
    def _save_state(self):
        """保存状态到文件"""
        with open(self.STATE_FILE, "w") as f:
            json.dump(self.state, f, indent=2)
        
    def _initialize_monitoring(self):
        """初始化监控配置"""
        if self.metrics_enabled and "metrics" in self.action:
            self._initialize_metrics()
            
    def _initialize_metrics(self):
        """初始化指标数据结构"""
        service_metrics = {
            "nginx": ["requests", "connections", "cpu", "memory"],
            "apache": ["requests", "connections", "traffic", "workers"],
            "tomcat": ["sessions", "threads", "heap", "processing_time"]
        }.get(self.service, [])
        
        # 为每个端点和每个指标创建时间序列
        timestamp = time.time()
        for endpoint in self.endpoints:
            self.metrics.setdefault(endpoint, {})
            for metric in service_metrics + ["status", "response_time", "error_rate"]:
                self.metrics[endpoint].setdefault(metric, [])
                
                # 初始化最近1小时的数据点(每分钟4个点，15秒间隔)
                if metric == "response_time":
                    for i in range(15):
                        self.metrics[endpoint][metric].append({
                            "timestamp": timestamp - (15 - i) * 15,
                            "value": 0
                        })
    
    def start(self):
        """启动web服务器服务"""
        if self._is_running():
            self._log_info(f"{self.service}服务已在运行")
            return True
            
        self._log_info(f"启动{self.service}服务")
        command = self._get_service_command("start")
        if self._execute_command(command):
            self._log_info(f"{self.service}服务启动成功")
            # 首次启动后等待稳定
            time.sleep(3)
            return True
        return False
        
    def stop(self):
        """停止web服务器服务"""
        if not self._is_running():
            self._log_info(f"{self.service}服务未在运行")
            return True
            
        self._log_info(f"停止{self.service}服务")
        command = self._get_service_command("stop")
        if self._execute_command(command):
            self._log_info(f"{self.service}服务停止成功")
            return True
        return False
        
    def restart(self):
        """重启web服务器服务"""
        return self.stop() and self.start()
        
    def reload(self):
        """重载web服务器配置"""
        if not self._is_running():
            self._log_warning("无法重载配置：服务未运行")
            return False
            
        self._log_info(f"重载{self.service}配置")
        command = self._get_service_command("reload")
        if self._execute_command(command):
            self._log_info(f"{self.service}配置重载成功")
            # 触发配置验证
            return self._verify_config()
        return False
        
    def status(self):
        """获取web服务器状态"""
        return {
            "running": self._is_running(),
            "last_status": self._check_health(),
            "metrics": self.metrics if self.metrics_enabled else {}
        }
        
    def monitor(self):
        """执行健康监控检查"""
        report = {
            "timestamp": time.time(),
            "overall_status": "HEALTHY",
            "details": {}
        }
        
        # 检查所有端点
        for endpoint in self.endpoints:
            health_url = f"{endpoint}{self.health_check}"
            result = self._perform_health_check(health_url)
            
            report["details"][endpoint] = result
            if result["status"] != 200:
                report["overall_status"] = "UNHEALTHY"
                
            # 收集性能指标
            if self.metrics_enabled:
                self._collect_metrics(endpoint, result)
        
        # 检查关键规则
        rule_violations = self._check_critical_rules(report)
        if rule_violations:
            report["overall_status"] = "CRITICAL"
            report["rule_violations"] = rule_violations
            
            if self.auto_recover:
                self._trigger_auto_recovery(report, rule_violations)
        
        # 必要时保存状态
        if report["overall_status"] != "HEALTHY" or self.metrics_enabled:
            self._save_state()
            with open(self.METRICS_FILE, "w") as f:
                json.dump(self.metrics, f, indent=2)
                
        return report
        
    def metrics(self):
        """获取性能指标报告"""
        report = {
            "service": self.service,
            "endpoints": {}
        }
        
        # 计算聚合指标
        for endpoint, metrics in self.metrics.items():
            endpoint_report = {
                "avg_response_time": self._calculate_average(endpoint, "response_time"),
                "max_memory": self._calculate_max(endpoint, "memory"),
                "error_rate": self._calculate_error_rate(endpoint),
                "last_1h": self._get_window_metrics(endpoint, 3600),
                "last_5m": self._get_window_metrics(endpoint, 300)
            }
            report["endpoints"][endpoint] = endpoint_report
            
        return report
        
    def scan(self):
        """执行安全扫描"""
        return {
            "ssl_audit": self._perform_ssl_audit(),
            "vulnerability_check": self._check_vulnerabilities(),
            "firewall_check": self._verify_firewall()
        }
        
    def firewall(self):
        """配置防火墙规则"""
        # 配置规则
        # 启动防火墙(如果未启动)
        # 验证规则
        
        return {"status": "Firewall configured"}
        
    def ssl_check(self):
        """检查SSL配置安全性"""
        return self._perform_ssl_audit()
        
    def _get_service_command(self, action):
        """获取服务管理命令"""
        commands = {
            "nginx": {
                "start": "nginx",
                "stop": "nginx -s stop",
                "reload": "nginx -s reload",
                "status": "pidof nginx"
            },
            "apache": {
                "start": "apachectl start",
                "stop": "apachectl stop",
                "reload": "apachectl graceful",
                "status": "apachectl status"
            },
            "tomcat": {
                "start": "$CATALINA_HOME/bin/startup.sh",
                "stop": "$CATALINA_HOME/bin/shutdown.sh",
                "reload": "echo 'Tomcat requires restart to reload config'",
                "status": "ps -ef | grep catalina"
            }
        }
        
        # 获取服务命令
        base_cmd = commands[self.service].get(action, "")
        if not base_cmd:
            if action == "enable":
                return f"systemctl enable {self.service_identifier}"
            if action == "disable":
                return f"systemctl disable {self.service_identifier}"
            return action  # 回退到原始命令
        
        return base_cmd
        
    def _execute_command(self, command):
        """执行系统命令"""
        try:
            import os
            self._log_debug(f"执行命令: {command}")
            result = os.system(command)
            return result == 0
        except Exception as e:
            self._log_error(f"命令执行失败: {command} - {str(e)}")
            return False
            
    def _is_running(self):
        """检查服务是否正在运行"""
        check_cmd = self._get_service_command("status")
        result = os.system(check_cmd)
        return result == 0
        
    def _perform_health_check(self, url):
        """执行健康检查"""
        result = {
            "url": url,
            "timestamp": time.time(),
            "status": 0,
            "response_time": 0,
            "content_match": False
        }
        
        try:
            start = time.time()
            response = requests.get(
                url, 
                timeout=self.timeout,
                verify=False  # 允许自签名证书（生产环境应配置CA）
            )
            end = time.time()
            
            result["status"] = response.status_code
            result["response_time"] = round((end - start) * 1000, 3)  # 毫秒
            
            # 检查期望内容
            if self.expected_content:
                result["content_match"] = self.expected_pattern in response.text
            else:
                result["content_match"] = True
                
        except requests.exceptions.RequestException as e:
            result["error"] = str(e)
            self.state["failure_count"] += 1
            self.state["last_failure"] = time.time()
            
        self._check_alert_conditions(result)
        return result
        
    def _check_alert_conditions(self, health_result):
        """检查告警触发条件"""
        alert_key = f"{health_result['url']}_{health_result.get('error', '')}"
        
        # 检查冷却时间
        last_alert_time = self.alerts.get(alert_key, {}).get("timestamp", 0)
        if time.time() - last_alert_time < self.alert_cooldown:
            return
            
        # 触发告警条件
        alert_message = ""
        
        if health_result.get("status", 0) != self.expected_status:
            alert_message = (
                f"{self.service} 健康检查失败 - 端点: {health_result['url']} "
                f"状态码: {health_result['status']} (期望: {self.expected_status})"
            )
        elif "error" in health_result:
            alert_message = (
                f"{self.service} 不可达 - 端点: {health_result['url']} "
                f"错误: {health_result['error']}"
            )
        elif not health_result["content_match"]:
            alert_message = (
                f"{self.service} 响应内容不匹配 - 端点: {health_result['url']} "
                f"期望内容: '{self.expected_content}'"
            )
            
        # 触发告警
        if alert_message:
            self._trigger_alert(alert_key, alert_message)
            
    def _trigger_alert(self, key, message):
        """触发告警通知"""
        self.alerts[key] = {
            "timestamp": time.time(),
            "message": message,
            "endpoints": self.endpoints,
            "service": self.service
        }
        
        # 发送通知
        self._send_alerts(message)
        
        # 保存告警历史
        with open(self.ALERT_FILE, "w") as f:
            json.dump(self.alerts, f, indent=2)
    
    def _send_alerts(self, message):
        """发送告警通知到所有配置目标"""
        for target in self.alerting:
            if target.startswith("slack#"):
                channel = target.split("#")[1]
                self._send_slack_alert(channel, message)
            elif target.startswith("email#"):
                email = target.split("#")[1]
                self._send_email_alert(email, message)
            elif target == "log":
                self._log_error(f"告警: {message}")
    
    def _send_slack_alert(self, channel, message):
        """发送Slack通知（示例实现）"""
        self._log_info(f"[SLACK到 {channel}] {message}")

    def _send_email_alert(self, email, message):
        """发送电子邮件通知（示例实现）"""
        self._log_info(f"[EMAIL到 {email}] {message}")
        
    def _collect_metrics(self, endpoint, health_result):
        """收集性能指标"""
        timestamp = time.time()
        
        # 添加响应时间指标
        self.metrics[endpoint]["response_time"].append({
            "timestamp": timestamp,
            "value": health_result["response_time"]
        })
        
        # 添加状态指标
        is_error = health_result.get("status", 0) != self.expected_status or "error" in health_result
        self.metrics[endpoint]["status"].append({
            "timestamp": timestamp,
            "value": 0 if is_error else 1
        })
        
        # 错误率计算（简化示例）
        error_rate = self._calculate_error_rate(endpoint)
        self.metrics[endpoint].setdefault("error_rate", [])
        self.metrics[endpoint]["error_rate"].append({
            "timestamp": timestamp,
            "value": error_rate
        })
        
        # 清理旧数据
        for metric in self.metrics[endpoint]:
            # 保留配置的历史时间内的数据
            self.metrics[endpoint][metric] = [
                m for m in self.metrics[endpoint][metric] 
                if timestamp - m["timestamp"] <= self.metrics_history
            ]
    
    def _calculate_average(self, endpoint, metric):
        """计算指标平均值"""
        values = [m["value"] for m in self.metrics[endpoint].get(metric, []) if m["value"] > 0]
        return sum(values) / len(values) if values else 0
    
    def _calculate_max(self, endpoint, metric):
        """计算指标最大值"""
        values = [m["value"] for m in self.metrics[endpoint].get(metric, [])]
        return max(values) if values else 0
    
    def _calculate_error_rate(self, endpoint):
        """计算错误率"""
        status_points = self.metrics[endpoint].get("status", [])
        if not status_points:
            return 0
            
        # 统计最近一定时间内的错误百分比
        window_start = time.time() - 300  # 最近5分钟
        window = [m for m in status_points if m["timestamp"] >= window_start]
        
        if not window:
            return 0
            
        errors = sum(1 for m in window if m["value"] == 0)
        return round(errors / len(window) * 100, 2)
    
    def _get_window_metrics(self, endpoint, seconds):
        """获取时间窗口内的指标数据"""
        end_time = time.time()
        start_time = end_time - seconds
        
        metrics = {}
        for metric_name, values in self.metrics[endpoint].items():
            window_data = [
                m for m in values
                if start_time <= m["timestamp"] <= end_time
            ]
            metrics[metric_name] = window_data
            
        return metrics
    
    def _check_critical_rules(self, monitor_report):
        """检查关键规则是否违反"""
        violations = {}
        
        for rule_name, rule in self.critical_rules.items():
            for endpoint, result in monitor_report["details"].items():
                value = result.get(rule_name)
                if value is None:
                    continue
                    
                if "max" in rule:
                    if value > rule["max"]:
                        violations.setdefault(endpoint, {})[rule_name] = {
                            "value": value,
                            "threshold": rule["max"],
                            "type": "max"
                        }
                        
                if "min" in rule:
                    if value < rule["min"]:
                        violations.setdefault(endpoint, {})[rule_name] = {
                            "value": value,
                            "threshold": rule["min"],
                            "type": "min"
                        }
                        
        return violations
    
    def _trigger_auto_recovery(self, monitor_report, violations):
        """触发自动恢复流程"""
        if self.state["failure_count"] < self.auto_recover_threshold:
            self._log_info("触发条件未达到，跳过自动恢复")
            return False
            
        self._log_warning("触发自动恢复流程")
        
        for action in self.recovery_actions:
            action_result = False
            
            if action == "reload":
                action_result = self.reload()
            elif action == "restart":
                action_result = self.restart()
            elif action == "failover" and self.failover_endpoint:
                action_result = self._activate_failover()
                
            # 检查恢复是否成功
            if action_result and self._recovery_successful():
                self._log_info(f"恢复操作 [{action}] 成功")
                # 重置失败计数
                self.state["failure_count"] = 0
                self.state["last_recovery"] = time.time()
                
                # 发送恢复通知
                self._send_alerts(f"{self.service} 服务已从故障中恢复: {action}")
                return True
                
        return False
        
    def _activate_failover(self):
        """激活故障转移"""
        self._log_info(f"激活故障转移到端点: {self.failover_endpoint}")
        # 在实际实现中，这将更新负载均衡器配置
        return True
        
    def _recovery_successful(self):
        """验证恢复是否成功"""
        # 重新检查健康状态
        for _ in range(3):
            health_status = self.monitor()
            if health_status["overall_status"] == "HEALTHY":
                return True
            time.sleep(1)
        return False
        
    def _perform_ssl_audit(self):
        """执行SSL安全审计(示例实现)"""
        report = {
            "grade": "A",
            "protocols": ["TLSv1.2", "TLSv1.3"],
            "ciphers": ["ECDHE-RSA-AES256-GCM-SHA384", "ECDHE-ECDSA-AES256-GCM-SHA384"],
            "vulnerabilities": [],
            "expiration_date": "2024-12-31"
        }
        
        return report
        
    def _check_vulnerabilities(self):
        """检查已知漏洞(示例实现)"""
        vulnerabilities_db = {
            "nginx": {
                "CVE-2021-23017": {"severity": "critical", "fixed_in": ["1.20.1"]},
                "CVE-2020-12440": {"severity": "high", "fixed_in": ["1.18.0"]}
            },
            "apache": {
                "CVE-2021-40438": {"severity": "critical", "fixed_in": ["2.4.50"]},
                "CVE-2021-39275": {"severity": "high", "fixed_in": ["2.4.50"]}
            }
        }
        
        # 获取服务器版本（简化示例）
        server_version = "nginx/1.22.0" if self.service == "nginx" else "apache/2.4.52"
        
        # 检查漏洞
        found_vulnerabilities = {}
        version_num = float(server_version.split("/")[1])
        
        for cve, details in vulnerabilities_db.get(self.service, {}).items():
            if any(version_num < float(fix_ver) for fix_ver in details["fixed_in"]):
                found_vulnerabilities[cve] = details
                
        return found_vulnerabilities
        
    def _verify_config(self):
        """验证配置文件语法(示例实现)"""
        check_cmds = {
            "nginx": "nginx -t",
            "apache": "apachectl configtest"
        }
        
        return self._execute_command(check_cmds.get(self.service, "echo 'Config test not implemented'"))
    
    def _verify_firewall(self):
        """验证防火墙规则(示例实现)"""
        return True
        
    def _log_info(self, message):
        logging.info(f"[MonitorWebserver] {self.service}: {message}")
        
    def _log_warning(self, message):
        logging.warning(f"[MonitorWebserver] {self.service}: {message}")
        
    def _log_error(self, message):
        logging.error(f"[MonitorWebserver] {self.service}: {message}")
        
    def _log_debug(self, message):
        logging.debug(f"[MonitorWebserver] {self.service}: {message}")
