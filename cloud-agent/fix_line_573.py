#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def fix_corrupted_line(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    # Fix line 573: # 主日?        main_logger = agent_logger.setup_logger(
    content = content.replace(
        '# 主日?        main_logger = agent_logger.setup_logger(',
        '# 主日志\n        main_logger = agent_logger.setup_logger('
    )

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Fixed: {filepath}")

if __name__ == '__main__':
    fix_corrupted_line(r'c:\yj\CloudRealm\cloud-agent\service\main.py')