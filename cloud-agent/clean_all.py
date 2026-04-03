#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re

def remove_all_garbled(filepath):
    with open(filepath, 'rb') as f:
        content = f.read()

    text = content.decode('utf-8', errors='ignore')

    text = text.replace('\r\r', '\n')
    text = text.replace('\r\n', '\n')
    text = text.replace('\r', '\n')

    def clean_line(line):
        if '#' not in line:
            return line
        
        parts = line.split('#', 1)
        code = parts[0]
        comment = parts[1] if len(parts) > 1 else ''
        
        clean_comment = ''.join(c for c in comment if ord(c) < 128 or c.isspace())
        clean_comment = clean_comment.strip()
        
        if clean_comment:
            return code + '# ' + clean_comment
        else:
            return code.rstrip()

    lines = text.split('\n')
    fixed_lines = [clean_line(line) for line in lines]
    text = '\n'.join(fixed_lines)

    text = re.sub(r'"""[^"]*"""', '"""', text)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)

    print(f"Fixed: {filepath}")

if __name__ == '__main__':
    remove_all_garbled(r'c:\yj\CloudRealm\cloud-agent\service\main.py')