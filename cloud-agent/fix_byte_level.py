#!/usr/bin/env python3
filepath = r'c:\yj\CloudRealm\cloud-agent\service\main.py'
with open(filepath, 'rb') as f:
    content = f.read()

# Fix line 132: remove spaces between comment and 'for'
old = b'# \xe6\xb8\x85\xe9\x99\xa4\xe5\x8e\x9f\xe6\x9c\x89\xe5\xa4\x84\xe7\x90\x86\xef\xbf\xbd?        for'
new = b'# Clear existing handlers\n        for'
content = content.replace(old, new)

# Fix line 138
old2 = b'# \xe5\x88\x9b\xe5\xbb\xba\xe6\x96\x87\xe4\xbb\xb6\xe5\xa4\x84\xe7\x90\x86\xef\xbf\xbd?        if'
new2 = b'# Create file handler\n        if'
content = content.replace(old2, new2)

# Fix line 1012
old3 = b'# \xe5\x90\xaf\xe5\x8a\xa8\xe6\x89\x80\xe6\x9c\x89\xe7\xba\xbf\xef\xbf\xbd?        for'
new3 = b'# Start all threads\n        for'
content = content.replace(old3, new3)

# Fix line 1032 (indent is different)
old4 = b'# \xe5\x91\xa8\xe6\x9c\x9f\xe5\x81\xa5\xe5\xba\xa7\xe6\xa3\x80\xef\xbf\xbd?                if'
new4 = b'# Periodic health check\n                if'
content = content.replace(old4, new4)

# Fix line 1098
old5 = b'# \xe5\x81\x9c\xe6\xad\xa2Ping\xe7\x9b\x91\xe5\x90\xac\xef\xbf\xbd?        if'
new5 = b'# Stop Ping listener\n        if'
content = content.replace(old5, new5)

with open(filepath, 'wb') as f:
    f.write(content)
print('Fixed')