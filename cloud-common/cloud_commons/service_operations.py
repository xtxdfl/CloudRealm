#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloud Platform Service Operations Script
=========================================
This script handles start/stop/restart operations for big data services.
It uses systemctl/service commands to manage Hadoop ecosystem services.
"""

import os
import sys
import json
import logging
import subprocess
import argparse
from typing import Dict, Tuple, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("service_operations")

SERVICE_COMMAND_MAP = {
    "hdfs": {
        "start": "su - hadoop -c '/opt/hadoop/sbin/start-dfs.sh'",
        "stop": "su - hadoop -c '/opt/hadoop/sbin/stop-dfs.sh'",
        "status": "su - hadoop -c 'jps | grep Namenode'",
        "components": ["Namenode", "DataNode", "SecondaryNamenode"]
    },
    "yarn": {
        "start": "su - hadoop -c '/opt/hadoop/sbin/start-yarn.sh'",
        "stop": "su - hadoop -c '/opt/hadoop/sbin/stop-yarn.sh'",
        "status": "su - hadoop -c 'jps | grep ResourceManager'",
        "components": ["ResourceManager", "NodeManager"]
    },
    "zookeeper": {
        "start": "systemctl start zookeeper",
        "stop": "systemctl stop zookeeper",
        "status": "systemctl status zookeeper",
        "components": ["QuorumPeerMain"]
    },
    "hive": {
        "start": "systemctl start hive-metastore && systemctl start hive-server2",
        "stop": "systemctl stop hive-server2 && systemctl stop hive-metastore",
        "status": "systemctl status hive-metastore",
        "components": ["HiveMetaStore", "HiveServer2"]
    },
    "spark": {
        "start": "systemctl start spark-master && systemctl start spark-worker",
        "stop": "systemctl stop spark-worker && systemctl stop spark-master",
        "status": "systemctl status spark-master",
        "components": ["Master", "Worker"]
    },
    "kafka": {
        "start": "systemctl start kafka",
        "stop": "systemctl stop kafka",
        "status": "systemctl status kafka",
        "components": ["Kafka"]
    },
    "flink": {
        "start": "systemctl start flink-jobmanager",
        "stop": "systemctl stop flink-jobmanager",
        "status": "systemctl status flink-jobmanager",
        "components": ["JobManager", "TaskManager"]
    },
    "hbase": {
        "start": "su - hbase -c '/opt/hbase/bin/start-hbase.sh'",
        "stop": "su - hbase -c '/opt/hbase/bin/stop-hbase.sh'",
        "status": "su - hbase -c 'jps | grep HMaster'",
        "components": ["HMaster", "HRegionServer"]
    },
    "elasticsearch": {
        "start": "systemctl start elasticsearch",
        "stop": "systemctl stop elasticsearch",
        "status": "systemctl status elasticsearch",
        "components": ["elasticsearch"]
    },
    "prometheus": {
        "start": "systemctl start prometheus",
        "stop": "systemctl stop prometheus",
        "status": "systemctl status prometheus",
        "components": ["prometheus"]
    },
    "grafana": {
        "start": "systemctl start grafana-server",
        "stop": "systemctl stop grafana-server",
        "status": "systemctl status grafana-server",
        "components": ["grafana-server"]
    },
    "trino": {
        "start": "systemctl start trino",
        "stop": "systemctl stop trino",
        "status": "systemctl status trino",
        "components": ["TrinoCoordinator", "TrinoWorker"]
    },
    "doris": {
        "start": "/opt/doris/fe/bin/start_fe.sh && /opt/doris/be/bin/start_be.sh",
        "stop": "/opt/doris/be/bin/stop_be.sh && /opt/doris/fe/bin/stop_fe.sh",
        "status": "ps aux | grep FE | grep -v grep",
        "components": ["FE", "BE"]
    }
}

def run_command(cmd: str, timeout: int = 30) -> Tuple[int, str, str]:
    """Execute shell command and return (exit_code, stdout, stderr)"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout} seconds"
    except Exception as e:
        return -1, "", str(e)

def get_service_config(service_name: str) -> Optional[Dict]:
    """Get service command configuration"""
    service_key = service_name.lower()
    return SERVICE_COMMAND_MAP.get(service_key)

def get_service_status(service_name: str) -> Dict:
    """Check service status"""
    config = get_service_config(service_name)
    if not config:
        return {
            "success": False,
            "error": f"Service {service_name} not found in configuration"
        }
    
    status_cmd = config.get("status", "")
    if not status_cmd:
        return {
            "success": False,
            "error": "No status command configured"
        }
    
    code, out, err = run_command(status_cmd, timeout=10)
    
    is_running = code == 0 and (out.strip() != "" or "running" in err.lower())
    
    return {
        "success": True,
        "service": service_name,
        "status": "RUNNING" if is_running else "STOPPED",
        "output": out,
        "error": err if err else None
    }

def start_service(service_name: str) -> Dict:
    """Start a service"""
    config = get_service_config(service_name)
    if not config:
        return {
            "success": False,
            "error": f"Service {service_name} not found in configuration"
        }
    
    start_cmd = config.get("start", "")
    if not start_cmd:
        return {
            "success": False,
            "error": "No start command configured"
        }
    
    logger.info(f"Starting service {service_name}: {start_cmd}")
    code, out, err = run_command(start_cmd, timeout=60)
    
    if code == 0:
        return {
            "success": True,
            "service": service_name,
            "operation": "start",
            "message": f"Service {service_name} started successfully"
        }
    else:
        return {
            "success": False,
            "service": service_name,
            "operation": "start",
            "error": err or "Failed to start service",
            "output": out
        }

def stop_service(service_name: str) -> Dict:
    """Stop a service"""
    config = get_service_config(service_name)
    if not config:
        return {
            "success": False,
            "error": f"Service {service_name} not found in configuration"
        }
    
    stop_cmd = config.get("stop", "")
    if not stop_cmd:
        return {
            "success": False,
            "error": "No stop command configured"
        }
    
    logger.info(f"Stopping service {service_name}: {stop_cmd}")
    code, out, err = run_command(stop_cmd, timeout=60)
    
    if code == 0:
        return {
            "success": True,
            "service": service_name,
            "operation": "stop",
            "message": f"Service {service_name} stopped successfully"
        }
    else:
        return {
            "success": False,
            "service": service_name,
            "operation": "stop",
            "error": err or "Failed to stop service",
            "output": out
        }

def restart_service(service_name: str) -> Dict:
    """Restart a service (stop then start)"""
    stop_result = stop_service(service_name)
    if not stop_result.get("success"):
        return stop_result
    
    return start_service(service_name)

def list_services() -> Dict:
    """List all supported services"""
    services = []
    for name, config in SERVICE_COMMAND_MAP.items():
        services.append({
            "name": name,
            "components": config.get("components", [])
        })
    
    return {
        "success": True,
        "services": services
    }

def main():
    parser = argparse.ArgumentParser(description="Cloud Service Operations")
    parser.add_argument("operation", choices=["start", "stop", "restart", "status", "list"],
                        help="Operation to perform")
    parser.add_argument("service", nargs="?", help="Service name")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    if args.operation == "list":
        result = list_services()
    elif args.service:
        if args.operation == "start":
            result = start_service(args.service)
        elif args.operation == "stop":
            result = stop_service(args.service)
        elif args.operation == "restart":
            result = restart_service(args.service)
        elif args.operation == "status":
            result = get_service_status(args.service)
    else:
        result = {
            "success": False,
            "error": "Service name required for this operation"
        }
    
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if result.get("success"):
            print(f"SUCCESS: {result.get('message', result)}")
        else:
            print(f"ERROR: {result.get('error', 'Unknown error')}")
            sys.exit(1)

if __name__ == "__main__":
    main()
