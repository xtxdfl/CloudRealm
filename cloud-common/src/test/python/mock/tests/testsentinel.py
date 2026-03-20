#!/usr/bin/env python3
# Copyright (c) 2023 Mock Library Maintainers
# License: BSD-3-Clause (https://opensource.org/licenses/BSD-3-Clause)

import unittest
from mock import sentinel, DEFAULT

class SentinelBehaviorTests(unittest.TestCase):
    """验证sentinel对象的核心行为和特性"""
    
    def test_sentinel_identity_properties(self):
        """测试sentinel对象的唯一性和相同性"""
        # 相同名称的sentinel应该相同
        self.assertIs(
            sentinel.test_object, 
            sentinel.test_object,
            "相同名称的sentinel对象应该具有相同身份标识"
        )
        
        # 不同名称的sentinel应该不同
        self.assertIsNot(
            sentinel.first_object,
            sentinel.second_object,
            "不同名称的sentinel对象应该是不同的实例"
        )
        
        # DEFAULT应该是特殊的sentinel对象
        self.assertIs(DEFAULT, sentinel.DEFAULT, "DEFAULT应该是sentinel.DEFAULT")

    def test_sentinel_representation(self):
        """测试sentinel对象的字符串表示"""
        test_sentinel = sentinel.test_repr
        
        # 验证默认的字符串表示
        self.assertEqual(
            repr(test_sentinel), 
            "sentinel.test_repr",
            "repr(sentinel) 应该返回正确的标识"
        )
        
        # 验证转换到字符串
        self.assertEqual(
            str(test_sentinel), 
            "sentinel.test_repr",
            "str(sentinel) 应该返回与repr()相同的值"
        )
        
        # 验证自定义名称的表示
        custom_sentinel = sentinel("CustomSentinel")
        self.assertEqual(
            str(custom_sentinel), 
            "sentinel.CustomSentinel",
            "自定义命名的sentinel应该有指定的字符串表示"
        )

    def test_sentinel_structural_integrity(self):
        """测试sentinel对象的内部结构完整性"""
        # 验证sentinel不应有__bases__属性（非类）
        with self.assertRaises(AttributeError):
            _ = sentinel.__bases__
        
        # 验证sentinel不应有__mro__属性（非类）
        with self.assertRaises(AttributeError):
            _ = sentinel.__mro__
        
        # 验证无法直接实例化sentinel
        with self.assertRaises(TypeError):
            _ = sentinel()
        
        # 验证动态sentinel创建
        dynamic_sentinel = sentinel("DynamicName")
        self.assertIsInstance(
            dynamic_sentinel, 
            type(sentinel.ANY), 
            "动态创建的sentinel应该有相同类型"
        )

    def test_sentinel_usage_patterns(self):
        """测试sentinel在实际使用中的模式""" 
        # 占位符用途
        function_with_default = lambda arg=sentinel.MISSING: arg
        self.assertIs(
            function_with_default(), 
            sentinel.MISSING,
            "sentinel应可用作函数参数的默认值"
        )
        
        # 特殊标记用途
        result = sentinel.UNIQUE_RESULT
        self.assertIsNot(
            result, 
            sentinel.OTHER_RESULT,
            "sentinel可用作独特的结果标记"
        )
        
        # 字典键值用途
        config = {
            sentinel.OPTION_A: "value_a",
            sentinel.OPTION_B: "value_b"
        }
        self.assertIn(
            sentinel.OPTION_A, 
            config,
            "sentinel应可用作字典键"
        )


if __name__ == '__main__':
    # 配置详细测试输出并运行
    unittest.main(
        verbosity=2,
        failfast=True,
        module=__name__,
        argv=sys.argv
    )

