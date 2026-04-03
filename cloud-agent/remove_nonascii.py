#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def remove_all_non_ascii(filepath):
    with open(filepath, 'rb') as f:
        content = f.read()

    text = content.decode('utf-8', errors='ignore')

    text = text.replace('\r\r', '\n')
    text = text.replace('\r\n', '\n')
    text = text.replace('\r', '\n')

    ascii_only = []
    in_string = False
    string_char = None
    i = 0
    
    while i < len(text):
        char = text[i]
        
        if char in ('"', "'") and not in_string:
            in_string = True
            string_char = char
            ascii_only.append(char)
        elif char == string_char and in_string:
            in_string = False
            string_char = None
            ascii_only.append(char)
        elif in_string:
            ascii_only.append(char)
        elif ord(char) < 128 or char in '\n\t ':
            ascii_only.append(char)
        i += 1
    
    result = ''.join(ascii_only)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(result)

    print(f"Removed all non-ASCII: {filepath}")

if __name__ == '__main__':
    remove_all_non_ascii(r'c:\yj\CloudRealm\cloud-agent\service\main.py')