#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re

def fix_line_endings(filepath):
    with open(filepath, 'rb') as f:
        content = f.read()

    text = content.decode('utf-8', errors='ignore')

    while '\r\r' in text:
        text = text.replace('\r\r', '\n')
    
    text = text.replace('\r\n', '\n')
    text = text.replace('\r', '\n')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)

    print(f"Fixed line endings: {filepath}")

if __name__ == '__main__':
    fix_line_endings(r'c:\yj\CloudRealm\cloud-server-go\cmd\package\build\python\cloud_agent\main.py')
    fix_line_endings(r'c:\yj\CloudRealm\cloud-agent\service\main.py')