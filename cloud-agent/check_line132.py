#!/usr/bin/env python3
filepath = r'c:\yj\CloudRealm\cloud-agent\service\main.py'
with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

output = []
for i in range(130, 145):
    line = lines[i]
    output.append(f'{i+1}: {repr(line)}')

with open(r'c:\yj\CloudRealm\cloud-agent\lines_output3.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))