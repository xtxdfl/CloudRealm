#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def fix_all_corrupted_comments(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    replacements = [
        ('# 清除原有处理?', '# Clear existing handlers'),
        ('# 创建文件处理?', '# Create file handler'),
        ('# 添加syslog处理?', '# Add syslog handler'),
        ('# 主日?', '# Main log'),
        ('# 警?', '# Alert log'),
        ('# 资源管理日?', '# Resource management log'),
    ]

    for old, new in replacements:
        content = content.replace(old, new)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Fixed corrupted comments: {filepath}")

if __name__ == '__main__':
    fix_all_corrupted_comments(r'c:\yj\CloudRealm\cloud-agent\service\main.py')