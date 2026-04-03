#!/usr/bin/env python3
filepath = r'c:\yj\CloudRealm\cloud-agent\service\main.py'
with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

fixes = [
    ('# 清除原有处理?        for handler in logger.handlers[:]:', '# Clear existing handlers\n        for handler in logger.handlers[:]:'),
    ('# 创建文件处理?        if log_file:', '# Create file handler\n        if log_file:'),
    ('# 启动所有线?        for thread in threads:', '# Start all threads\n        for thread in threads:'),
    ('# 周期健康检?                if int(time.time())', '# Periodic health check\n                if int(time.time())'),
    ('# 停止Ping监听?        if ping_port_listener:', '# Stop Ping listener\n        if ping_port_listener:'),
]

for old, new in fixes:
    content = content.replace(old, new)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed')