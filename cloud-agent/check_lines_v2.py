#!/usr/bin/env python3
filepath = r'c:\yj\CloudRealm\cloud-agent\service\main.py'
with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()
with open(r'c:\yj\CloudRealm\cloud-agent\lines_output.txt', 'w', encoding='utf-8') as out:
    for i in range(130, 145):
        out.write(f'{i+1}: {repr(lines[i][:60])}\n')