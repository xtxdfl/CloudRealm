#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re

def completely_fix(filepath):
    with open(filepath, 'rb') as f:
        content = f.read()

    text = content.decode('utf-8', errors='ignore')

    text = text.replace('\r\r', '\n')
    text = text.replace('\r\n', '\n')
    text = text.replace('\r', '\n')

    text = re.sub(r'"""[\s\S]*?"""', '"""', text)

    def fix_line(line):
        if '#' in line:
            line = line[:line.index('#')]
        return line

    lines = text.split('\n')
    fixed_lines = [fix_line(line) for line in lines]
    text = '\n'.join(fixed_lines)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)

    print(f"Fixed: {filepath}")

if __name__ == '__main__':
    completely_fix(r'c:\yj\CloudRealm\cloud-agent\service\main.py')