#!/usr/bin/env python3
filepath = r'c:\yj\CloudRealm\cloud-agent\service\main.py'
with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()
for i in range(130, 140):
    print(f'{i+1}: {repr(lines[i][:60])}')