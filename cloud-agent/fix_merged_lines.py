#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def fix_merged_comment_lines(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    replacements = [
        ('# 清除原有处理?        for handler in logger.handlers[:]:',
         '# Clear existing handlers\n        for handler in logger.handlers[:]:'),
        ('# 创建文件处理?        if log_file:',
         '# Create file handler\n        if log_file:'),
        ('# 添加syslog处理?        self._add_syslog_handler',
         '# Add syslog handler\n        self._add_syslog_handler'),
    ]

    for old, new in replacements:
        content = content.replace(old, new)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Fixed merged lines: {filepath}")

if __name__ == '__main__':
    fix_merged_comment_lines(r'c:\yj\CloudRealm\cloud-agent\service\main.py')