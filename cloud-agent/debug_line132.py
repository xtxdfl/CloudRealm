#!/usr/bin/env python3
filepath = r'c:\yj\CloudRealm\cloud-agent\service\main.py'
with open(filepath, 'rb') as f:
    content = f.read()

lines = content.split(b'\n')
for i, line in enumerate(lines):
    if b'# ' in line and b'for' in line:
        print(f'Line {i+1}: {line[:60]}...')
        if i == 131:
            print(f'  Full: {line}')