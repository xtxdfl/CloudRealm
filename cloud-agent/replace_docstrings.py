#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re

def replace_chinese_docstrings(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    chinese_docstrings = [
        (r'"""配置指定名称的日志记录器"""', '"""Configure named logger"""'),
        (r'"""添加系统日志处理?仅Linux)"""', '"""Add system logging handler (Linux only)"""'),
        (r'"""检查是否启用syslog"""', '"""Check if syslog is enabled"""'),
        (r'"""解析PID文件路径"""', '"""Parse PID file path"""'),
        (r'"""写入PID文件"""', '"""Write PID file"""'),
        (r'"""移除PID文件"""', '"""Remove PID file"""'),
        (r'"""代理自动恢复机制"""', '"""Agent auto-recovery mechanism"""'),
        (r'"""处理连接错误"""', '"""Handle connection error"""'),
        (r'"""增加资源限制"""', '"""Increase resource limits"""'),
        (r'"""Cloud代理核心容器"""', '"""Cloud agent core container"""'),
        (r'"""执行代理主逻辑"""', '"""Execute agent main logic"""'),
        (r'"""打印启动横幅"""', '"""Print startup banner"""'),
        (r'"""解析配置文件"""', '"""Parse config file"""'),
        (r'"""配置日志系统"""', '"""Configure logging system"""'),
        (r'"""设置系统区域设置"""', '"""Set system locale"""'),
        (r'"""验证sudo权限"""', '"""Verify sudo permission"""'),
        (r'"""检查是否有其他实例运行"""', '"""Check if other instance is running"""'),
        (r'"""检查前缀目录是否存在"""', '"""Check if prefix directory exists"""'),
        (r'"""更新资源限制"""', '"""Update resource limits"""'),
        (r'"""作为守护进程运行"""', '"""Run as daemon"""'),
        (r'"""更新日志级别"""', '"""Update log level"""'),
        (r'"""启动服务"""', '"""Start services"""'),
        (r'"""启动核心工作线程"""', '"""Start core worker threads"""'),
        (r'"""清理资源"""', '"""Cleanup resources"""'),
        (r'"""处理致命错误"""', '"""Handle fatal error"""'),
    ]

    for chinese, english in chinese_docstrings:
        content = content.replace(chinese, english)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Replaced docstrings: {filepath}")

if __name__ == '__main__':
    replace_chinese_docstrings(r'c:\yj\CloudRealm\cloud-agent\service\main.py')