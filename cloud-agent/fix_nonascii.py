#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re

def fix_file(filepath):
    with open(filepath, 'rb') as f:
        content = f.read()

    text = content.decode('utf-8', errors='ignore')

    text = text.replace('\r\r', '\n')
    text = text.replace('\r\n', '\n')
    text = text.replace('\r', '\n')

    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)

    def clean_docstring(match):
        return '"""'

    text = re.sub(r'"""[^"]*"""', clean_docstring, text)

    text = re.sub(r'#[^\n]*', lambda m: m.group(0).encode('ascii', 'ignore').decode('ascii') if all(ord(c) < 128 or c in ' \t' for c in m.group(0)) else m.group(0), text)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)

    print(f"Fixed: {filepath}")

if __name__ == '__main__':
    fix_file(r'c:\yj\CloudRealm\cloud-agent\service\main.py')