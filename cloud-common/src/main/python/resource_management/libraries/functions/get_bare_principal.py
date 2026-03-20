#!/usr/bin/env python3
"""
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Advanced Kerberos Principal Parser
"""

import re
import logging
from enum import Enum

# 配置日志记录
logger = logging.getLogger(__name__)

__all__ = ["get_bare_principal", "KerberosPrincipal", "parse_principal"]

class PrincipalType(Enum):
    USER = 1
    SERVICE = 2
    UNKNOWN = 3

class KerberosPrincipal:
    """Kerberos 主体结构化表�?""
    
    __slots__ = ('primary', 'instance', 'realm', 'principal_type')
    
    def __init__(self, principal_str=None):
        self.primary = None
        self.instance = None
        self.realm = None
        self.principal_type = PrincipalType.UNKNOWN
        if principal_str:
            self.parse(principal_str)
    
    def parse(self, principal_str):
        """解析 Kerberos 主体字符�?""
        # 完整解析正则：支持多种格式和特殊字符
        pattern = r"""
            ^
            (?P<primary>[\w$.\-][\w$.\-]*)         # 主部分：字母数字、点、破折号�?
            (?:/(?P<instance>[\w$.\-\*]+))?        # 可选实例部�?            (?:@(?P<realm>[A-Z0-9.$:\-]+\.[A-Z]{2,}))?  # 可选域�?            $
        """
        match = re.search(pattern, principal_str, re.IGNORECASE | re.VERBOSE)
        
        if not match:
            logger.error(f"无法解析的主体格�? {principal_str}")
            return False
        
        self.primary = match.group('primary')
        self.instance = match.group('instance')
        self.realm = match.group('realm')
        
        # 自动推导主体类型
        if not self.instance:
            self.principal_type = PrincipalType.USER
        elif not self.realm:
            logger.warning(f"服务主体缺少域名: {principal_str}")
            self.principal_type = PrincipalType.SERVICE
        else:
            self.principal_type = PrincipalType.SERVICE
        
        return True
    
    @property
    def bare_principal(self):
        """获取主体主要部分"""
        return self.primary
    
    @property
    def full_principal(self):
        """获取完整主体名称"""
        components = [self.primary]
        if self.instance:
            components.append('/')
            components.append(self.instance)
        if self.realm:
            components.append('@')
            components.append(self.realm)
        return ''.join(components)
    
    def normalize(self, default_realm=None):
        """规范主体格式（补充缺失域名）"""
        if not self.realm:
            if default_realm:
                self.realm = default_realm.upper()
            elif self.principal_type == PrincipalType.SERVICE:
                logger.warning(f"服务主体缺少域名且未提供默认�? {self.primary}")
        
        return self.full_principal
    
    def validate(self):
        """验证主体有效�?""
        errors = []
        if not self.primary:
            errors.append("缺少主要部分")
        if self.principal_type == PrincipalType.SERVICE and not self.realm:
            errors.append("服务主体缺少域名")
        if self.realm and not re.match(r'^[A-Z0-9.\-]+\.[A-Z]{2,}$', self.realm, re.IGNORECASE):
            errors.append(f"无效域名格式: {self.realm}")
        
        return len(errors) == 0, errors
    
    def __str__(self):
        return self.full_principal
    
    def __repr__(self):
        return (f"<KerberosPrincipal primary={self.primary!r} "
                f"instance={self.instance!r} realm={self.realm!r} "
                f"type={self.principal_type.name}>")

def parse_principal(principal_str):
    """解析并验�?Kerberos 主体
    
    返回: KerberosPrincipal 对象
    """
    principal = KerberosPrincipal(principal_str)
    is_valid, errors = principal.validate()
    if not is_valid:
        logger.error(f"无效的主�?'{principal_str}': {', '.join(errors)}")
    return principal

def get_bare_principal(normalized_principal_name):
    """从标准化主体名称中提取主要部�?    
    参数规范�?    1. 支持用户主体: username@REALM.COM
    2. 支持服务主体: service/hostname@REALM.COM
    3. 支持特殊字符: _, $, -, .
    
    :param normalized_principal_name: 待解析的主体名称
    :return: 主体主要部分�?None
    """
    # 空值处�?    if not normalized_principal_name:
        logger.warning("传入空主体名�?)
        return None
    
    # 直接解析主体对象
    principal = parse_principal(normalized_principal_name)
    
    # 返回主要部分
    return principal.bare_principal if principal.primary else None


# --------------- 测试用例 -----------------
def test_principal_parser():
    """执行主体解析验证测试"""
    test_cases = [
        ("nimbus/c6501.cloud.apache.org@EXAMPLE.COM", "nimbus", True),
        ("hdfs-dn/node7.cluster@EXAMPLE.ORG", "hdfs-dn", True),
        ("kafka_user@REALM.NET", "kafka_user", True),
        ("admin@SECURE-DOMAIN.COM", "admin", True),
        ("user-with.dash$ymbol", "user-with.dash$ymbol", True),
        ("service/multi.level.subdomain@DOMAIN.COM", "service", True),
        ("invalid/realm", None, False),  # 无效域名
        ("@REALM.COM", None, False),     # 无主部分
        ("service/", None, False),       # 无实�?        ("service@invali|d.realm", None, False),  # 无效域名
        (12345, None, False),            # 非字符串
        (None, None, False)              # None�?    ]
    
    results = {"passed": 0, "failed": 0}
    
    print("\nKerberos 主体解析测试:")
    print("=" * 60)
    for principal_str, expected, should_pass in test_cases:
        try:
            result = get_bare_principal(principal_str)
            test_pass = (result == expected) and (should_pass or result is None)
            status = "PASS" if test_pass else "FAIL"
            
            # 更新统计
            if test_pass:
                results["passed"] += 1
            else:
                results["failed"] += 1
            
            print(f"输入: {principal_str!r}")
            print(f"期望: {expected!r} | 实际: {result!r}")
            print(f"状�? [{status}]\n{"-" * 60}")
        except Exception as e:
            results["failed"] += 1
            print(f"输入: {principal_str!r} 引发异常: {str(e)}")
            print(f"状�? [ERROR]\n{"-" * 60}")
    
    # 打印结果
    print(f"\n测试完成: 通过 {results['passed']}, 失败 {results['failed']}")
    return results["failed"] == 0

if __name__ == "__main__":
    # 执行自测
    if test_principal_parser():
        print("所有测试成功通过 �?)
    else:
        print("部分测试未通过 �?)
