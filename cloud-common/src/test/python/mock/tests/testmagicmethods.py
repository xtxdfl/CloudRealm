#!/usr/bin/env python3
# Copyright (c) 2023 Mock Library Maintainers
# License: BSD-3-Clause (https://opensource.org/licenses/BSD-3-Clause)

import sys
import unittest
import inspect
from mock import Mock, MagicMock, _magics

# Python版本兼容处理
PY3 = sys.version_info[0] == 3
PYTHON_VERSION = sys.version_info[:2]

class MagicMethodBehaviorTests(unittest.TestCase):
    """验证Mock对象对Python魔术方法的支持行为"""
    
    def test_magic_method_lifecycle_management(self):
        """测试魔术方法的创建、使用和删除"""
        mock = Mock()
        self.assertFalse(hasattr(mock, '__getitem__'),
                         "新创建的Mock不应有__getitem__方法")
        
        # 添加魔术方法
        mock.__getitem__ = lambda s, k: f"value-{k}"
        self.assertTrue(hasattr(mock, '__getitem__'),
                       "应为Mock添加__getitem__方法")
        self.assertEqual(mock["key"], "value-key",
                         "添加的__getitem__方法应正常工作")
        
        # 删除魔术方法
        del mock.__getitem__
        self.assertFalse(hasattr(mock, '__getitem__'),
                         "删除__getitem__后方法应消失")
        with self.assertRaises(TypeError):
            _ = mock["key"]

    def test_magic_method_types(self):
        """测试不同类型的魔术方法绑定"""
        mock = Mock()
        
        # 函数类型魔术方法
        def func_getitem(s, key):
            return f"func-{key}"
        mock.__getitem__ = func_getitem
        self.assertEqual(mock["key"], "func-key",
                         "函数类型的魔术方法应正常工作")
        self.assertIsInstance(mock.__getitem__, types.FunctionType)
        
        # Mock类型魔术方法
        mock_getitem = Mock(return_value="mock-value")
        mock.__getitem__ = mock_getitem
        self.assertEqual(mock["key"], "mock-value",
                         "Mock类型的魔术方法应正常工作")
        self.assertIsInstance(mock.__getitem__, Mock)

    def test_magic_method_independence(self):
        """测试不同Mock实例间魔术方法的独立性"""
        mock1 = Mock()
        mock2 = Mock()
        
        # 只在mock1上设置迭代方法
        mock1.__iter__ = lambda s: iter([1, 2, 3])
        
        # 验证独立行为
        self.assertEqual(list(mock1), [1, 2, 3],
                         "mock1应可迭代")
        with self.assertRaises(TypeError):
            _ = list(mock2)  # mock2不应支持迭代

    def test_string_representation_methods(self):
        """测试字符串表示相关魔术方法"""
        mock = Mock()
        
        # 默认实现
        default_repr = repr(mock)
        self.assertIn("Mock id='", default_repr,
                     "默认repr应包含对象ID")
        
        # 自定义repr
        mock.__repr__ = lambda s: "CustomRepr"
        self.assertEqual(repr(mock), "CustomRepr",
                         "应使用自定义__repr__方法")
        
        # 自定义str
        mock.__str__ = lambda s: "CustomStr"
        self.assertEqual(str(mock), "CustomStr",
                         "应使用自定义__str__方法")
        
        # Python 2的unicode方法
        if not PY3:
            mock.__unicode__ = lambda s: u"CustomUnicode"
            self.assertEqual(unicode(mock), u"CustomUnicode")

    def test_container_methods_behavior(self):
        """测试容器相关魔术方法的集成实现"""
        mock = MagicMock()
        mock_data = {"key1": "value1", "key2": "value2"}
        
        # 设置魔术方法
        mock.__contains__ = lambda s, k: k in mock_data
        mock.__getitem__ = lambda s, k: mock_data[k]
        mock.__setitem__ = lambda s, k, v: mock_data.__setitem__(k, v)
        mock.__delitem__ = lambda s, k: mock_data.__delitem__(k)
        
        # 验证行为
        self.assertTrue("key1" in mock, "__contains__应正确工作")
        self.assertEqual(mock["key2"], "value2", "__getitem__应正确工作")
        
        mock["key3"] = "value3"
        self.assertEqual(mock_data["key3"], "value3", "__setitem__应正确工作")
        
        del mock["key1"]
        self.assertNotIn("key1", mock_data, "__delitem__应正确工作")

    def test_numeric_operations_support(self):
        """测试数值操作魔术方法"""
        mock = Mock()
        mock.value = 10
        
        # 加法操作
        def add(s, other):
            s.value += other
            return s
        
        mock.__add__ = add
        result = mock + 5
        self.assertEqual(result, mock, "__add__应返回对象自身")
        self.assertEqual(mock.value, 15, "__add__应修改内部状态")
        
        # 就地加法
        def iadd(s, other):
            s.value += other
            return s
        
        mock.__iadd__ = iadd
        mock += 3
        self.assertEqual(mock.value, 18, "__iadd__应修改内部状态")
        
        # 反向加法
        def radd(s, other):
            return other + s.value
        
        mock.__radd__ = radd
        result = 7 + mock
        self.assertEqual(result, 25, "__radd__应正确处理反向加法")

    def test_boolean_evaluation_handling(self):
        """测试布尔值评估的实现"""
        mock = MagicMock()
        
        # Python版本兼容处理
        if PY3:
            bool_attr = '__bool__'
        else:
            bool_attr = '__nonzero__'
        
        # 默认值
        self.assertTrue(bool(mock), "默认应为真")
        
        # 修改为False
        setattr(mock, bool_attr, lambda s: False)
        self.assertFalse(bool(mock), "自定义布尔方法应生效")

    def test_comparison_operations(self):
        """测试比较运算符的行为"""
        # 在Python 3中比较不同类型对象会引发TypeError
        if PY3:
            mock = MagicMock()
            with self.assertRaises(TypeError):
                _ = mock < 3
            with self.assertRaises(TypeError):
                _ = mock > object()
        else:
            # Python 2行为
            mock = Mock()
            self.assertEqual(mock < 3, object() < 3)
            
            # 自定义比较方法
            mock.__lt__ = lambda s, o: True
            self.assertTrue(mock < 3)

    def test_iterable_support(self):
        """测试可迭代对象的魔术方法支持"""
        mock = Mock()
        
        # 未定义方法时的行为
        with self.assertRaises(TypeError):
            _ = len(mock)
        with self.assertRaises(TypeError):
            _ = iter(mock)
        with self.assertRaises(TypeError):
            _ = 3 in mock
        
        # 自定义方法
        mock.__len__ = lambda s: 5
        self.assertEqual(len(mock), 5, "__len__应正确工作")
        
        mock.__contains__ = lambda s, o: o == 'test'
        self.assertTrue('test' in mock, "__contains__应正确工作")
        
        mock.__iter__ = lambda s: iter('abc')
        self.assertEqual(list(mock), ['a', 'b', 'c'], "__iter__应正确工作")

    def test_magicmock_special_attributes(self):
        """验证MagicMock自动创建的特殊方法"""
        mock = MagicMock()
        
        # 自动存在的魔术方法
        self.assertTrue(hasattr(mock, '__getitem__'), "应有__getitem__方法")
        self.assertTrue(hasattr(mock, '__iter__'), "应有__iter__方法")
        
        # 设置返回值
        mock.__iter__.return_value = iter([1, 2, 3])
        self.assertEqual(list(mock), [1, 2, 3], "__iter__应返回指定值")
        
        # 不存在的魔术方法
        self.assertFalse(hasattr(mock, '__nonexistent_magic__'),
                         "不应有不存在的魔术方法")

    def test_spec_constrained_mock(self):
        """测试带spec约束的Mock对象魔术方法行为"""
        class IterableSpec:
            def __iter__(self):
                pass
        
        # 使用spec
        mock = Mock(spec=IterableSpec)
        self.assertTrue(hasattr(mock, '__iter__'), "spec约束下应有__iter__")
        
        # 未在spec中的魔术方法
        if PY3:
            method = '__bool__'
        else:
            method = '__nonzero__'
        self.assertFalse(hasattr(mock, method), 
                         f"spec约束下不应有未定义的{method}方法")
        
        # 设置未在spec中的魔术方法应失败
        with self.assertRaises(AttributeError):
            setattr(mock, method, lambda: True)

    def test_unsupported_magic_methods(self):
        """测试试图设置不支持的魔术方法时的行为"""
        mock = MagicMock()
        
        # 设置不支持的魔术方法
        with self.assertRaisesRegex(AttributeError, 
                                   "Attempting to set unsupported magic method"):
            mock.__setattr__ = lambda self, name: None

    def test_magic_method_chaining(self):
        """测试复杂操作中的魔术方法链式调用"""
        mock = MagicMock()
        
        # 链式方法调用
        mock[1].get(2).values().__contains__(3).return_value = True
        
        # 验证链式调用
        self.assertTrue(mock[1].get(2).values().__contains__(3))
        self.assertTrue(mock[1].get(2).values().__contains__(3),
                       "链式调用应返回最终结果")

    def test_resetting_magic_methods(self):
        """测试魔术方法使用reset_mock后的状态"""
        mock = MagicMock()
        
        # 使用魔术方法
        str(mock)
        iter(mock)
        
        # 验证使用记录
        self.assertTrue(mock.__str__.called, "__str__应被调用")
        self.assertTrue(mock.__iter__.called, "__iter__应被调用")
        
        # 重置调用状态
        mock.reset_mock()
        self.assertFalse(mock.__str__.called, "__str__调用状态应重置")
        self.assertFalse(mock.__iter__.called, "__iter__调用状态应重置")
        
        # 验证返回值保持
        mock.__iter__.return_value = iter([42])
        mock.reset_mock()
        self.assertEqual(list(mock), [42], "重置后返回值应保持")

    @unittest.skipUnless(PYTHON_VERSION >= (2, 6), "__dir__ 需要 Python 2.6+")
    def test_directory_handling(self):
        """测试__dir__魔术方法的支持"""
        for mock in (Mock(), MagicMock()):
            # 自定义__dir__
            mock.__dir__ = lambda s: ['attrs', 'methods']
            self.assertEqual(dir(mock), ['attrs', 'methods'],
                             "__dir__应返回自定义属性列表")

    def test_bound_method_limitation(self):
        """测试预绑定方法的受限行为"""
        m = Mock()
        
        # 绑定方法来自其他对象
        m.__iter__ = [1, 2, 3].__iter__
        
        # 验证受限行为
        with self.assertRaises(TypeError):
            _ = iter(m)

if __name__ == '__main__':
    unittest.main()
