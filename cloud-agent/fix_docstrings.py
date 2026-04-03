#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re

def fix_docstrings(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    text = re.sub(r'"""[^"]*[^"]*"', lambda m: m.group(0).replace('', ''), text)

    replacements = [
        ('添加系统日志处理吗仅Linux', '添加系统日志处理(仅Linux)'),
        ('更新所有日志记录器的日志级吗', '更新所有日志记录器的日志级别'),
        ('从配置获取日志级吗', '从配置获取日志级别'),
        ('服务生命周期管理吗', '服务生命周期管理'),
        ('记录错误并决定恢复动吗', '记录错误并决定恢复动作'),
        ('5, 10, 15吗', '5, 10, 15秒'),
        ('设置命令行选项解析吗', '设置命令行选项解析器'),
    ]

    for old, new in replacements:
        text = text.replace(old, new)

    text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)

    print(f"Docstrings fixed: {filepath}")

if __name__ == '__main__':
    fix_docstrings(r'c:\yj\CloudRealm\cloud-agent\service\main.py')