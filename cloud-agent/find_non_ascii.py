#!/usr/bin/env python3
import ast

filepath = r'c:\yj\CloudRealm\cloud-agent\service\main.py'
with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

tree = ast.parse(content)

def find_non_ascii_strings(node):
    results = []
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            if any(ord(c) > 127 for c in child.value):
                results.append((child.lineno, child.value))
        elif isinstance(child, ast.Str):
            if any(ord(c) > 127 for c in child.s):
                results.append((child.lineno, child.s))
    return results

non_ascii = find_non_ascii_strings(tree)
print(f"Found {len(non_ascii)} strings with non-ASCII:")
for lineno, s in non_ascii[:10]:
    print(f"  Line {lineno}: {repr(s)[:50]}")