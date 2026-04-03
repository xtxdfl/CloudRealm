#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re

def fix_mojibake(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        text = f.read()

    replacements = {
        '¨å±å®ä¹': '定义',
        'ç½®æå®åç§°çæ¥å¿è®记å½': '配置指定名称的日志记录器',
        'æ·»å¼å¹æ»¤åæ¨å°å±': '添加滚动文件日志处理器',
        'ç¡®ä¿æ—¥¿¬ç®å½å­': '确保日志目录存在',
        'æ£æ¥æ¯å¯çµæå­': '检查是否启用syslog',
        'æ´ææ‰æ®è®°å½å¨æ—¥¿¬çº§å': '更新所有日志记录器的日志级别',
        'æåŠ¡ç"Ÿå'å'æœ': '服务生命周期管理',
        'ä»£ççè‡ªåŠåæå': '代理自动恢复机制',
        'è®°å½é"è¯å¹¶å†³å®定型æå': '记录错误并决定恢复动作',
        'å³å®定型æ': '决定恢复动作',
        'Cloudä»£ççæ å®¹': 'Cloud代理核心容器',
        'åå¯æå': '启动前检查',
        'æ£æ¥æå‰ç¼ç›®å½æ': '检查前缀目录是否存在',
        'ä½œä¸ºæå®¡è¿°ç¨': '作为守护进程运行',
        'å¯åŠæåŠ¡': '启动服务',
        'æ£æ¥å‰å‰ç¼': '检查当前进程',
        'æ£æ¥å‰å‰ç¼ç›®å½æ': '检查前缀目录是否存在',
        'æ°æærootç"¥ææ': 'root用户无需检查',
        'å¼åŠåŠè¿ç»æ': '启动所有线程',
        'å"åŠè¿ç»': '守护进程',
        'æ»å¹æ­': '健康',
        'äºå»ºåå§åå'å'å'ã': '创建初始化和核心容器',
    }

    for garbled, correct in replacements.items():
        text = text.replace(garbled, correct)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)

    print(f"Mojibake fixed: {filepath}")

if __name__ == '__main__':
    fix_mojibake(r'c:\yj\CloudRealm\cloud-agent\service\main.py')