#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re

def fix_file(filepath):
    with open(filepath, 'rb') as f:
        content = f.read()

    text = content.decode('utf-8', errors='ignore')

    text = text.replace('\r\r', '\n')
    text = text.replace('\r\n', '\n')
    text = text.replace('\r', '\n')

    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)

    chinese_map = {
        '¨å±å®ä¹': '定义',
        'ç½®æå®åç§°çæ¥å¿è®记å½': '配置指定名称的日志记录器',
        'æ·»å¼å¹æ»¤åæ¨å°å±': '添加滚动文件日志处理器',
        'ç¡®ä¿æ—¥¿¬ç®å½å­': '确保日志目录存在',
        'æ£æ¥æ¯å¯çµæå­': '检查是否启用syslog',
        'æ´ææ‰æ®è®°å½å¨æ—¥¿¬çº§å': '更新所有日志记录器的日志级别',
        'æåŠ¡ç"Ÿååæœ': '服务生命周期管理',
        'ä»£ççè‡ªåŠåæå': '代理自动恢复机制',
        'è®°å½é"è¯å¹¶å†³å®定型æå': '记录错误并决定恢复动作',
        'å³å®定型æ': '决定恢复动作',
        'Cloudä»£ççæ å®¹': 'Cloud代理核心容器',
        'åå¯æå': '启动前检查',
        'æ£æ¥æå‰ç¼ç›®å½æ': '检查前缀目录是否存在',
        'ä½œä¸ºæå®¡è¿°ç¨': '作为守护进程运行',
        'å¯åŠæåŠ¡': '启动服务',
        'æ£æ¥å‰å‰ç¼': '检查当前进程',
        'æ°æærootç"¥ææ': 'root用户无需检查',
        'å¼åŠåŠè¿ç»æ': '启动所有线程',
        'æ»å¹æ­': '健康',
        'äºå»ºåå§ååååã': '创建初始化和核心容器',
        'æåŠ¡': '服务',
        'æåŠ¡çæ¥': '服务进程',
        'æåŠ¡å': '服务组件',
        'æ£æ¥': '检查',
        'å¼åŠ': '启动',
        'åæ': '停止',
        'åæ¥': '停止服务',
        'æ£æ¥å': '检查状态',
        'å¯å': '启动',
        'ç¡': '检查',
    }

    for garbled, correct in chinese_map.items():
        text = text.replace(garbled, correct)

    replacements = [
        ('添加系统日志处理吗仅Linux', '添加系统日志处理(仅Linux)'),
        ('更新所有日志记录器的日志级吗', '更新所有日志记录器的日志级别'),
        ('从配置获取日志级吗', '从配置获取日志级别'),
        ('服务生命周期管理吗', '服务生命周期管理'),
        ('记录错误并决定恢复动吗', '记录错误并决定恢复动作'),
        ('5, 10, 15吗', '5, 10, 15秒'),
        ('设置命令行选项解析吗', '设置命令行选项解析器'),
    ]

    for old, new in replacements:
        text = text.replace(old, new)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)

    print(f"Fixed: {filepath}")

if __name__ == '__main__':
    fix_file(r'c:\yj\CloudRealm\cloud-agent\service\main.py')