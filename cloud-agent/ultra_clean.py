#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re

def ultra_clean(filepath):
    with open(filepath, 'rb') as f:
        content = f.read()

    text = content.decode('utf-8', errors='ignore')

    text = text.replace('\r\r', '\n')
    text = text.replace('\r\n', '\n')
    text = text.replace('\r', '\n')

    def remove_non_ascii_from_docstring(match):
        return '"""'

    text = re.sub(r'"""[^"]*"""', remove_non_ascii_from_docstring, text)

    def clean_comment(line):
        if '#' in line:
            code_part, comment_part = line.split('#', 1)
            ascii_comment = ''.join(c for c in comment_part if ord(c) < 128)
            if ascii_comment.strip():
                return code_part + '# ' + ascii_comment.strip()
            else:
                return code_part.rstrip()
        return line

    lines = text.split('\n')
    fixed_lines = [clean_comment(line) for line in lines]
    text = '\n'.join(fixed_lines)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)

    print(f"Ultra cleaned: {filepath}")

if __name__ == '__main__':
    ultra_clean(r'c:\yj\CloudRealm\cloud-agent\service\main.py')