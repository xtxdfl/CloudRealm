import os
import re

filepath = r"c:\yj\CloudRealm\cloud-agent\service\main.py"

with open(filepath, 'rb') as f:
    raw = f.read()

content = raw.decode('utf-8', errors='ignore')

content = content.replace('?', '吗')
content = content.replace('?"""', '吗"""')
content = content.replace('?"', '吗"')
content = content.replace('?:', '吗:')
content = content.replace('?,', '吗,')
content = content.replace('\ufffd', '')
content = content.replace('\xe2\x80\x9c', '"')
content = content.replace('\xe2\x80\x9d', '"')
content = content.replace('\xe2\x80\x94', '-')
content = content.replace('\xe2\x80\x93', '-')

content = content.replace('添加系统日志处理吗仅Linux', '添加系统日志处理(仅Linux)')
content = content.replace('更新所有日志记录器的日志级吗', '更新所有日志记录器的日志级别')
content = content.replace('从配置获取日志级吗', '从配置获取日志级别')
content = content.replace('服务生命周期管理吗', '服务生命周期管理')
content = content.replace('记录错误并决定恢复动吗', '记录错误并决定恢复动作')
content = content.replace('5, 10, 15吗', '5, 10, 15秒')

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed encoding issues in main.py")