#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re

def fix_file_completely(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    lines = content.split('\n')
    fixed_lines = []

    for line in lines:
        if '#' in line:
            code_part, comment_part = line.split('#', 1)
            ascii_comment = ''.join(c for c in comment_part if ord(c) < 128 or c.isspace())
            if ascii_comment.strip():
                fixed_line = code_part + '# ' + ascii_comment.strip()
            else:
                fixed_line = code_part.rstrip()
            fixed_lines.append(fixed_line)
        else:
            fixed_lines.append(line)

    result = '\n'.join(fixed_lines)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(result)

    print(f"Fixed: {filepath}")

if __name__ == '__main__':
    fix_file_completely(r'c:\yj\CloudRealm\cloud-agent\service\main.py')