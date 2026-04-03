#!/usr/bin/env python3
filepath = r'c:\yj\CloudRealm\cloud-agent\service\main.py'
with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

output = []
for i in range(125, 150):
    line = lines[i]
    leading_spaces = len(line) - len(line.lstrip())
    output.append(f'{i+1}: ({leading_spaces:2d}) {line.rstrip()[:70]}')

with open(r'c:\yj\CloudRealm\cloud-agent\lines_output2.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))