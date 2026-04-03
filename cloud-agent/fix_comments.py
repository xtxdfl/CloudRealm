#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re

def remove_garbled_comments(filepath):
    with open(filepath, 'rb') as f:
        content = f.read()

    text = content.decode('utf-8', errors='ignore')

    text = text.replace('\r\r', '\n')
    text = text.replace('\r\n', '\n')
    text = text.replace('\r', '\n')

    def fix_line(line):
        if '#' in line:
            parts = line.split('#', 1)
            before = parts[0]
            after = parts[1]
            
            ascii_after = ''.join(c for c in after if ord(c) < 128 or c in ' \t')
            
            if ascii_after.strip():
                line = before + '#' + ascii_after
            else:
                line = before.rstrip()
        return line

    lines = text.split('\n')
    fixed_lines = [fix_line(line) for line in lines]
    text = '\n'.join(fixed_lines)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)

    print(f"Fixed: {filepath}")

if __name__ == '__main__':
    remove_garbled_comments(r'c:\yj\CloudRealm\cloud-agent\service\main.py')