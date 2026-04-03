#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import threading
import time
import json
import platform
from typing import Dict, Optional

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logging.warning("psutil not available, some metrics will be unavailable")

logger = logging.getLogger(__name__)


class StatusReporter(threading.Thread):
    """
    上报Agent服务状态到CloudServer
    每5秒通过REST API上报主机状态
    """

    def __init__(self, config, stop_event: threading.Event):
        threading.Thread.__init__(self, name="StatusReporter")
        self.daemon = True
        self.config = config
        self.stop_event = stop_event
        
        self.server_hostname = config.server_hostname
        self.server_port = config.get("server", "url_port", fallback="8080")
        
        from cloud_agent import hostname
        try:
            self.agent_id = hostname.hostname(config)
        except:
            import socket
            self.agent_id = socket.gethostname()
        
        self.report_interval = 5
        self._last_report_time = 0
        
        self.hardware = None
        try:
            from Hardware import Hardware
            self.hardware = Hardware(config)
        except Exception as e:
            logger.warning(f"Failed to initialize Hardware collector: {e}")
        
        logger.info(f"StatusReporter initialized: server={self.server_hostname}:{self.server_port}, interval={self.report_interval}s")

    def run(self):
        logger.info("StatusReporter started")
        while not self.stop_event.is_set():
            try:
                self.report_status()
            except Exception as e:
                logger.error(f"Status report failed: {e}")
            
            self.stop_event.wait(self.report_interval)
        
        logger.info("StatusReporter stopped")

    def get_system_metrics(self) -> Dict:
        """获取系统性能指标"""
        metrics = {
            "cpuUsage": 0.0,
            "memoryUsed": 0,
            "memoryTotal": 0,
            "diskUsed": 0,
            "diskTotal": 0
        }
        
        if PSUTIL_AVAILABLE:
            try:
                cpu_percent = psutil.cpu_percent(interval=0.1)
                metrics["cpuUsage"] = cpu_percent
            except Exception as e:
                logger.debug(f"Failed to get CPU usage: {e}")
            
            try:
                mem = psutil.virtual_memory()
                metrics["memoryUsed"] = int(mem.used)
                metrics["memoryTotal"] = int(mem.total)
            except Exception as e:
                logger.debug(f"Failed to get memory info: {e}")
            
            try:
                disk = psutil.disk_usage('/')
                metrics["diskUsed"] = int(disk.used)
                metrics["diskTotal"] = int(disk.total)
            except Exception as e:
                logger.debug(f"Failed to get disk info: {e}")
        else:
            if self.hardware:
                try:
                    info = self.hardware.get_hardware_info(invalidate_cache=True)
                    memory_str = info.get("memory_total", "0")
                    if isinstance(memory_str, str):
                        metrics["memoryTotal"] = int(memory_str)
                    else:
                        metrics["memoryTotal"] = memory_str
                    
                    mounts = info.get("mounts", [])
                    if mounts:
                        total_disk = sum(int(m.get("size", 0)) for m in mounts)
                        used_disk = sum(int(m.get("used", 0)) for m in mounts)
                        metrics["diskTotal"] = total_disk
                        metrics["diskUsed"] = used_disk
                except Exception as e:
                    logger.debug(f"Failed to get hardware info: {e}")
        
        return metrics

    def report_status(self):
        """上报状态到CloudServer"""
        import urllib.request
        import urllib.error
        import socket
        
        url = f"http://{self.server_hostname}:{self.server_port}/api/agent/heartbeat"
        
        hostname = socket.gethostname()
        try:
            hostname = socket.gethostbyaddr(socket.gethostname())[0]
        except:
            pass
        
        metrics = self.get_system_metrics()
        
        payload = {
            "agentId": self.agent_id,
            "status": "RUNNING",
            "timestamp": int(time.time() * 1000),
            "cpuUsage": metrics["cpuUsage"],
            "memoryUsed": metrics["memoryUsed"],
            "memoryTotal": metrics["memoryTotal"],
            "diskUsed": metrics["diskUsed"],
            "diskTotal": metrics["diskTotal"],
            "components": [],
            "alerts": [],
            "metadata": {
                "hostname": hostname,
                "platform": platform.system(),
                "agent_version": "1.5.0"
            }
        }
        
        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                url,
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            
            with urllib.request.urlopen(req, timeout=5) as response:
                result = response.read().decode('utf-8')
                logger.debug(f"Heartbeat response: {result}")
                
        except urllib.error.HTTPError as e:
            if e.code == 404:
                logger.debug("Heartbeat endpoint not found on server, this is expected if agent is not registered yet")
            else:
                logger.warning(f"HTTP error during heartbeat: {e.code} {e.reason}")
        except urllib.error.URLError as e:
            logger.warning(f"Connection failed during heartbeat: {e.reason}")
        except Exception as e:
            logger.error(f"Unexpected error during heartbeat: {e}")

    def set_agent_id(self, agent_id: str):
        """设置Agent ID"""
        self.agent_id = agent_id
        logger.info(f"Agent ID set to: {agent_id}")
