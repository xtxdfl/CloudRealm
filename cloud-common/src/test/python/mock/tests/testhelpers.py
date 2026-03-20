#!/usr/bin/env python3
# Copyright (c) 2023 Mock Library Maintainers
# License: BSD-3-Clause (https://opensource.org/licenses/BSD-3-Clause)

import unittest
import datetime
from unittest.mock import (
    call, 
    _Call, 
    _CallList, 
    ANY, 
    create_autospec, 
    MagicMock, 
    PropertyMock,
    patch
)

# 测试用类
class SomeClass:
    def one(self, a, b):
        pass

    def two(self):
        pass

    def three(self, a=None):
        pass
    
    @property
    def one_property(self):
        return 3

    @one_property.setter
    def one_property(self, value):
        pass

    __slots__ = ['slotted_attribute']


class AnyTests(unittest.TestCase):
    """测试 ANY 对象的特性和行为"""
    
    def test_any_object_equality(self):
        """测试 ANY 对象与任何对象相等"""
        self.assertEqual(ANY, "any object")
        self.assertEqual(ANY, {"key": "value"})
        self.assertEqual(ANY, 12345)
        self.assertEqual(ANY, None)
    
    def test_any_in_assertions(self):
        """测试在断言中使用 ANY"""
        mock = Mock()
        mock(datetime.datetime.now())
        mock.assert_called_with(ANY)
    
    def test_any_with_keyword_arguments(self):
        """测试 ANY 在关键字参数中的使用"""
        mock = Mock()
        mock(foo=datetime.datetime.now(), bar=datetime.datetime.now())
        mock.assert_called_with(foo=ANY, bar=ANY)
    
    def test_any_repr_and_str(self):
        """测试 ANY 的字符串表示"""
        self.assertEqual(repr(ANY), "<ANY>")
        self.assertEqual(str(ANY), "<ANY>")
    
    def test_any_in_complex_mock_calls(self):
        """测试 ANY 在复杂调用链中的比较"""
        mock = Mock()
        
        # 模拟多个调用
        current_time = datetime.datetime.now()
        mock(current_time, foo=current_time)
        mock.method(current_time, zinga=current_time, alpha=current_time)
        mock().method(a1=current_time, z99=current_time)
        
        # 使用 ANY 验证
        expected_calls = [
            call(ANY, foo=ANY),
            call.method(ANY, zinga=ANY, alpha=ANY),
            call(),
            call().method(a1=ANY, z99=ANY)
        ]
        self.assertEqual(mock.mock_calls, expected_calls)


class CallTests(unittest.TestCase):
    """测试 Call 对象的特性和行为"""
    
    def test_call_equality(self):
        """测试 Call 对象的相等性比较"""
        # 基本相等性
        self.assertEqual(call(), call())
        self.assertEqual(call(1, 2), call(1, 2))
        self.assertEqual(call(foo="bar"), call(foo="bar"))
        
        # 不同构造方式的相等性
        self.assertEqual(call("foo", "bar"), call().foo("bar"))
        self.assertEqual(call().foo.bar(), call().foo.bar())
        
        # 不同参数的相等性
        self.assertEqual(call(1, 2, a=3), call(1, 2, a=3))
        self.assertEqual(call().foo(1, 2), call().foo(1, 2))
        
        # 不等的情况
        self.assertNotEqual(call(1, 2), call(3, 4))
        self.assertNotEqual(call(foo="bar"), call(baz="qux"))
    
    def test_call_repr_and_str(self):
        """测试 Call 对象的字符串表示"""
        # 基本调用
        self.assertEqual(str(call), "call")
        self.assertEqual(repr(call), "call")
        
        # 无参数调用
        self.assertEqual(repr(call()), "call()")
        
        # 位置参数
        self.assertEqual(repr(call(1, 2, 3)), "call(1, 2, 3)")
        
        # 关键字参数
        self.assertEqual(repr(call(a=1, b=2)), "call(a=1, b=2)")
        
        # 混合参数
        self.assertEqual(repr(call("test", 123, key="value")), "call('test', 123, key='value')")
        
        # 方法链调用
        self.assertEqual(repr(call().foo.bar(1, 2)), "call().foo.bar(1, 2)")
        
        # 深层链式调用
        self.assertEqual(
            repr(call().foo().bar().baz("test")), 
            "call().foo().bar().baz('test')"
        )
    
    def test_call_packing(self):
        """测试调用参数的打包"""
        # 基本调用
        self.assertEqual(call(), ("", (), {}))
        
        # 带位置参数
        self.assertEqual(call(1, 2, 3), ("", (1, 2, 3), {}))
        
        # 带关键字参数
        self.assertEqual(call(x=10, y=20), ("", (), {"x": 10, "y": 20}))
        
        # 混合参数
        self.assertEqual(
            call("pos", key="word"), 
            ("", ("pos",), {"key": "word"})
        )
        
        # 方法调用
        self.assertEqual(
            call.method(1, 2), 
            ("method", (1, 2), {})
        )
    
    def test_call_in_mocks(self):
        """测试 Call 对象在 Mock 中的使用"""
        mock = Mock()
        
        # 记录调用
        mock(1, 2, 3)
        mock.method(key="value")
        mock().result("test")
        
        # 使用 call() 进行断言
        mock.assert_called_with(1, 2, 3)
        self.assertEqual(mock.call_args_list, [call(1, 2, 3)])
        self.assertEqual(mock.method_calls, [call.method(key="value")])
        self.assertEqual(
            mock.mock_calls,
            [call(1, 2, 3), call.method(key="value"), call(), call().result("test")]
        )
    
    def test_call_unpacking(self):
        """测试调用对象的解包"""
        # 创建带参数的调用对象
        c = call(1, 2, a=3, b=4)
        
        # 解包为两部分 (args, kwargs)
        args, kwargs = c
        self.assertEqual(args, (1, 2))
        self.assertEqual(kwargs, {"a": 3, "b": 4})


class AutospecTests(unittest.TestCase):
    """测试 create_autospec 功能和 spec_set 特性"""
    
    def test_autospec_basic_signature(self):
        """测试类方法签名匹配"""
        # 创建带自动规范的 mock
        spec_mock = create_autospec(SomeClass)
        
        # 合法调用
        spec_mock.one(1, 2)
        spec_mock.one.assert_called_with(1, 2)
        
        # 参数不匹配
        with self.assertRaises(TypeError):
            spec_mock.one("wrong", "type")
        
        # 缺少参数
        with self.assertRaises(TypeError):
            spec_mock.one(1)  # 缺少 b 参数
    
    def test_autospec_nonexistent_attributes(self):
        """测试未定义方法的处理"""
        spec_mock = create_autospec(SomeClass)
        
        # 未在 spec 中定义的方法
        with self.assertRaises(AttributeError):
            spec_mock.nonexistent_method()
    
    def test_autospec_return_value(self):
        """测试设置自动规范的返回值"""
        # 带返回值的指定类
        spec_mock = create_autospec(SomeClass, return_value="custom_result")
        result = spec_mock()
        self.assertEqual(result, "custom_result")
        
        # 带返回值的函数
        def test_function():
            return "original_result"
        
        func_mock = create_autospec(test_function, return_value="mocked_result")
        self.assertEqual(func_mock(), "mocked_result")
    
    def test_autospec_recursive(self):
        """测试递归属性规范"""
        # 创建递归规范
        spec_mock = create_autospec(SomeClass)
        spec_mock.one(1, 2)  # 这是允许的
        
        # 对 nested 属性应用规范
        with self.assertRaises(TypeError):
            spec_mock.one.incorrect("signature")
    
    def test_autospec_spec_set_behavior(self):
        """测试严格规范限制"""
        # 创建带严格规范的 mock
        strict_mock = create_autospec(SomeClass, spec_set=True)
        
        # 读取属性是允许的
        _ = strict_mock.one
        
        # 设置新属性被禁止
        with self.assertRaises(AttributeError):
            strict_mock.new_attribute = 10
    
    def test_autospec_property_handling(self):
        """测试属性处理的规范"""
        # 创建规范 mock
        spec_mock = create_autospec(SomeClass)
        
        # 访问属性
        self.assertIsInstance(spec_mock.one_property, PropertyMock)
        self.assertEqual(spec_mock.one_property, spec_mock.one_property)
        
        # 设置属性值
        spec_mock.one_property = 10
        spec_mock.one_property.assert_called_with(10)
    
    def test_autospec_slotted_attributes(self):
        """测试 slotted 属性的处理"""
        # 创建规范 mock
        spec_mock = create_autospec(SomeClass)
        
        # 访问 slotted 属性
        self.assertIsInstance(spec_mock.slotted_attribute, MagicMock)
        
        # 调用 slotted 属性
        spec_mock.slotted_attribute(1, 2, 3)
        spec_mock.slotted_attribute.assert_called_with(1, 2, 3)
    
    def test_autospec_with_classes(self):
        """测试类自动规范"""
        # 类级别的规范
        class_spec = create_autospec(SomeClass)
        
        # 类调用（实例化）
        instance = class_spec(1, 2)
        class_spec.assert_called_with(1, 2)
        
        # 实例方法调用
        instance.one(3, 4)
        instance.one.assert_called_with(3, 4)
    
    def test_autospec_with_functions(self):
        """测试函数自动规范"""
        # 普通函数
        def test_func(a, b=2):
            return a + b
        
        # 创建函数规范
        func_spec = create_autospec(test_func)
        
        # 合法调用
        func_spec(1)
        func_spec.assert_called_with(1)
        
        # 非法调用
        with self.assertRaises(TypeError):
            func_spec("invalid", "arguments")
    
    def test_autospec_keyword_only_arguments(self):
        """测试带关键字参数的自动规范"""
        # 带关键字参数的函数
        def kw_func(a, b, *, c=None, d=None):
            pass
        
        # 创建规范
        spec = create_autospec(kw_func)
        
        # 位置参数调用
        spec(1, 2)
        spec.assert_called_with(1, 2)
        
        # 带关键字参数调用
        spec(1, 2, c=3)
        spec.assert_called_with(1, 2, c=3)
        
        # 无效参数调用
        with self.assertRaises(TypeError):
            spec(1, 2, 3)  # 位置传递关键字参数
    
    def test_autospec_reset_mock(self):
        """测试自动规范 mock 的重置"""
        spec_mock = create_autospec(int)
        int(spec_mock)
        
        # 重置 mock
        spec_mock.reset_mock()
        self.assertEqual(spec_mock.__int__.call_count, 0)
    
    def test_autospec_with_builtins(self):
        """测试内置类型与函数的自动规范"""
        for builtin_type in (int, str, list, dict, set, float, complex, bool):
            mock_builtin = create_autospec(builtin_type)
            
            # 验证方法访问
            method_name = f"__{builtin_type.__name__.lower()}__"
            self.assertTrue(hasattr(mock_builtin, method_name)
    
    def test_autospec_inheritance(self):
        """测试自动规范的继承行为"""
        class Parent:
            def parent_method(self):
                pass
        
        class Child(Parent):
            def child_method(self):
                pass
        
        # 自动规范子类
        child_spec = create_autospec(Child)
        
        # 测试继承的方法
        child_spec.parent_method()
        child_spec.parent_method.assert_called_once_with()
        
        # 测试子类方法
        child_spec.child_method()
        child_spec.child_method.assert_called_once_with()
    
    def test_autospec_method_calls_recording(self):
        """测试自动规范的方法调用记录"""
        mock = create_autospec(SomeClass)
        mock.attr = create_autospec(SomeClass)
        
        # 记录调用
        mock.one(1, 2)
        mock.two()
        mock.attr.one(3, 4)
        mock.attr.two()
        
        # 检查方法调用列表
        expected_calls = [
            call.one(1, 2),
            call.two(),
            call.attr.one(3, 4),
            call.attr.two()
        ]
        self.assertEqual(mock.method_calls, expected_calls)


class CallListTests(unittest.TestCase):
    """测试 CallList 类的特性和行为"""
    
    def test_call_list_contains_operation(self):
        """测试包含操作符"""
        mock = Mock()
        
        # 记录多个调用
        mock(1, 2)
        mock(a=3)
        mock(3, 4)
        mock(b=6)
        
        # 单个调用包含
        self.assertIn(call(1, 2), mock.call_args_list)
        self.assertIn(call(a=3), mock.call_args_list)
        self.assertIn(call(3, 4), mock.call_args_list)
        self.assertIn(call(b=6), mock.call_args_list)
        
        # 子序列包含
        self.assertIn([call(a=3), call(3, 4)], mock.call_args_list)
        self.assertIn([call(1, 2), call(a=3)], mock.call_args_list)
        self.assertIn([call(3, 4), call(b=6)], mock.call_args_list)
        
        # 单个元素子序列
        self.assertIn([call(3, 4)], mock.call_args_list)
        
        # 不包含的调用
        self.assertNotIn(call("fish"), mock.call_args_list)
        self.assertNotIn([call("fish")], mock.call_args_list)
    
    def test_complex_call_representation(self):
        """测试复杂调用的字符串表示"""
        mock = MagicMock()
        
        # 创建复杂调用链
        mock(1, 2)
        mock.foo(a=3)
        mock.foo.bar().baz("fish", cat="dog")
        
        # 预期的字符串表示
        expected = (
            "[call(1, 2),\n"
            " call.foo(a=3),\n"
            " call.foo.bar(),\n"
            " call.foo.bar().baz('fish', cat='dog')]"
        )
        
        # 验证字符串表示
        self.assertEqual(str(mock.mock_calls), expected)
    
    def test_property_mock_behavior(self):
        """测试 PropertyMock 行为"""
        with patch(f"{__name__}.SomeClass.one", new_callable=PropertyMock) as mock_prop:
            # 属性访问
            _ = SomeClass.one  # 1次访问
            mock_prop.assert_called_once_with()
            
            # 实例属性访问
            s = SomeClass()
            _ = s.one  # 2次访问
            self.assertEqual(mock_prop.call_count, 2)
            
            # 设置属性值
            s.one = 3
            self.assertEqual(mock_prop.mock_calls, [call(), call(), call(3)])
    
    def test_property_mock_return_value(self):
        """测试 PropertyMock 返回值处理"""
        parent_mock = MagicMock()
        prop_mock = PropertyMock()
        
        # 为父类 mock 添加属性
        type(parent_mock).foo = prop_mock
        
        # 访问属性
        result = parent_mock.foo
        prop_mock.assert_called_once_with()
        
        # 验证返回值不是 PropertyMock
        self.assertIsInstance(result, MagicMock)
        self.assertNotIsInstance(result, PropertyMock)
    
    def test_call_list_equality(self):
        """测试 CallList 相等性比较"""
        mock = Mock()
        mock.method_a(1)
        mock.method_b(2)
        mock.method_c(3)
        
        # 创建两个相同的调用列表
        list1 = mock.mock_calls
        list2 = _CallList([
            call.method_a(1),
            call.method_b(2),
            call.method_c(3)
        ])
        
        # 测试相等性
        self.assertEqual(list1, list2)
        
        # 测试顺序不同的调用列表
        list3 = _CallList([
            call.method_c(3),
            call.method_a(1),
            call.method_b(2)
        ])
        self.assertNotEqual(list1, list3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
