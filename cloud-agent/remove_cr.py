#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def remove_all_cr(filepath):
    with open(filepath, 'rb') as f:
        content = f.read()

    content = content.replace(b'\r', b'')

    with open(filepath, 'wb') as f:
        f.write(content)

    print(f"Removed CR: {filepath}")

if __name__ == '__main__':
    remove_all_cr(r'c:\yj\CloudRealm\cloud-server-go\cmd\package\build\python\cloud_agent\main.py')
    remove_all_cr(r'c:\yj\CloudRealm\cloud-agent\service\main.py')