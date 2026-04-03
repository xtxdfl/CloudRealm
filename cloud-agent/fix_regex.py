#!/usr/bin/env python3
import re

filepath = r'c:\yj\CloudRealm\cloud-agent\service\main.py'
with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

pattern = r'# [^\x00-\x7F]+        '
replacement = lambda m: '# ' + re.sub(r'[^\x00-\x7F]+', '', m.group(0)).strip() or '#'
result = re.sub(pattern, replacement, content)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(result)
print('Done')