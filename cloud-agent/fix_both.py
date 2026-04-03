#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys

def fix_encoding(filepath):
    with open(filepath, 'rb') as f:
        content = f.read()

    try:
        text = content.decode('utf-8')
    except UnicodeDecodeError:
        text = content.decode('utf-8', errors='ignore')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)

    print(f"Fixed encoding: {filepath}")

if __name__ == '__main__':
    fix_encoding(r'c:\yj\CloudRealm\cloud-server-go\cmd\package\build\python\cloud_agent\main.py')
    fix_encoding(r'c:\yj\CloudRealm\cloud-agent\service\main.py')