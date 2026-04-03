#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import sys

def fix_main_py(filepath):
    with open(filepath, 'rb') as f:
        content = f.read()

    try:
        text = content.decode('utf-8')
    except UnicodeDecodeError:
        text = content.decode('latin-1').encode('utf-8', errors='ignore').decode('utf-8')

    text = text.replace('\r\r', '\n')
    text = text.replace('\r\n', '\n')
    text = text.replace('\r', '\n')

    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

    text = re.sub(r'\u0085', '\n', text)
    text = re.sub(r'\u2028', '\n', text)
    text = re.sub(r'\u2029', '\n', text)

    replacements = {
        '添加系统日志处理吗仅Linux': '添加系统日志处理(仅Linux)',
        '更新所有日志记录器的日志级吗': '更新所有日志记录器的日志级别',
        '从配置获取日志级吗': '从配置获取日志级别',
        '服务生命周期管理吗': '服务生命周期管理',
        '记录错误并决定恢复动吗': '记录错误并决定恢复动作',
        '5, 10, 15吗': '5, 10, 15秒',
        '设置命令行选项解析吗': '设置命令行选项解析器',
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)

    print(f"Fixed: {filepath}")

if __name__ == '__main__':
    fix_main_py(r'c:\yj\CloudRealm\cloud-agent\service\main.py')