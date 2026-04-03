#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def remove_all_r(filepath):
    with open(filepath, 'rb') as f:
        content = f.read()

    content = content.replace(b'\r', b'')

    with open(filepath, 'wb') as f:
        f.write(content)

    print(f"Removed \\r: {filepath}")

if __name__ == '__main__':
    remove_all_r(r'c:\yj\CloudRealm\cloud-agent\service\main.py')