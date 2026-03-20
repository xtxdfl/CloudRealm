#!/usr/bin/env python3
# Copyright (c) 2023 Mock Library Maintainers
# License: BSD-3-Clause (https://opensource.org/licenses/BSD-3-Clause)

import os
import sys
import unittest
from unittest.mock import (
    sentinel, DEFAULT, patch, MagicMock, Mock, NonCallableMagicMock, 
    NonCallableMock, call, _get_target
)

from tests.support import SomeClass, inPy3k

# 兼容性处理
builtin_string = "builtins" if inPy3k else "__builtin__"

# 当前模块引用
current_module = sys.modules[__name__]
module_name = __name__

# 测试用全局对象
something = sentinel.Something
something_else = sentinel.SomethingElse

class Foo:
    """测试使用的示例类"""
    def __init__(self, a):
        pass

    def f(self, a):
        pass

    def g(self):
        pass
    
    class Bar:
        def a(self):
            pass

class Container(dict):
    """测试用的类字典对象"""
    def __init__(self):
        self.values = {}
    
    def __getitem__(self, name):
        return self.values[name]
    
    def __setitem__(self, name, value):
        self.values[name] = value
    
    def __delitem__(self, name):
        del self.values[name]
    
    def __iter__(self):
        return iter(self.values)

class PatchTestBase(unittest.TestCase):
    """patch装饰器的基础功能测试"""
    
    def assert_not_callable(self, obj):
        """断言对象不可调用"""
        self.assertRaises(TypeError, obj)
        self.assertIsInstance(obj, (NonCallableMock, NonCallableMagicMock))

class SinglePatchTests(PatchTestBase):
    """单个patch对象的测试"""
    
    def test_patch_object_single_attribute(self):
        """测试patch.object装饰单个属性"""
        class TestClass:
            attribute = sentinel.Original
        
        @patch.object(TestClass, "attribute", sentinel.Patched)
        def test():
            self.assertEqual(TestClass.attribute, sentinel.Patched)
        
        test()
        self.assertEqual(TestClass.attribute, sentinel.Original)
        
    def test_patch_object_with_none(self):
        """测试用None值patch属性"""
        class TestClass:
            attribute = sentinel.Original
        
        @patch.object(TestClass, "attribute", None)
        def test():
            self.assertIsNone(TestClass.attribute)
        
        test()
        self.assertEqual(TestClass.attribute, sentinel.Original)
        
    def test_patch_object_multiple(self):
        """测试多个patch.object装饰器"""
        class TestClass:
            attribute = sentinel.Original
            next_attribute = sentinel.Original2
        
        @patch.object(TestClass, "attribute", sentinel.Patched)
        @patch.object(TestClass, "next_attribute", sentinel.Patched2)
        def test():
            self.assertEqual(TestClass.attribute, sentinel.Patched)
            self.assertEqual(TestClass.next_attribute, sentinel.Patched2)
        
        test()
        self.assertEqual(TestClass.attribute, sentinel.Original)
        self.assertEqual(TestClass.next_attribute, sentinel.Original2)

class PatchFunctionalityTests(PatchTestBase):
    """核心patch功能测试"""
    
    def test_basic_patch_decorator(self):
        """测试基本patch功能"""
        original_value = something
        
        @patch(f"{module_name}.something", sentinel.Something2)
        def test():
            self.assertEqual(current_module.something, sentinel.Something2)
        
        test()
        self.assertEqual(current_module.something, original_value)

    def test_patch_dynamic_object_construction(self):
        """测试动态对象构造的延迟查找"""
        global something
        original = something
        
        @patch(f"{module_name}.something", sentinel.Something2)
        def test():
            pass
        
        try:
            # 在patch执行前修改全局变量
            something = sentinel.replacement_value
            test()
            self.assertEqual(something, sentinel.replacement_value)
        finally:
            something = original

    def test_patch_stacked_decorators(self):
        """测试多个patch装饰器堆叠"""
        original_something = something
        original_something_else = something_else
        
        @patch(f"{module_name}.something", sentinel.Something2)
        @patch(f"{module_name}.something_else", sentinel.SomethingElse)
        def test():
            self.assertEqual(something, sentinel.Something2)
            self.assertEqual(something_else, sentinel.SomethingElse)
        
        test()
        self.assertEqual(something, original_something)
        self.assertEqual(something_else, original_something_else)

    def test_patch_builtin_function(self):
        """测试patch内置函数"""
        mock_open = Mock(return_value=sentinel.Handle)
        
        @patch(f"{builtin_string}.open", mock_open)
        def test():
            self.assertEqual(open("filename", "r"), sentinel.Handle)
        
        # 执行两次验证恢复功能
        test()
        test()
        self.assertNotEqual(open, mock_open)

class SpecificationTests(PatchTestBase):
    """spec/spec_set/autospec相关测试"""
    
    def test_patch_with_spec(self):
        """测试带spec的patch"""
        @patch(f"{module_name}.SomeClass", spec=SomeClass)
        def test(MockClass):
            self.assertEqual(SomeClass, MockClass)
            # 验证spec执行
            SomeClass.wibble
            self.assertRaises(AttributeError, lambda: SomeClass.not_wibble)
        
        test()
        
    def test_patch_with_spec_as_list(self):
        """测试使用列表作为spec"""
        @patch(f"{module_name}.SomeClass", spec=["wibble"])
        def test(MockClass):
            self.assertEqual(SomeClass, MockClass)
            # 验证spec执行
            SomeClass.wibble
            self.assertRaises(AttributeError, lambda: SomeClass.not_wibble)
        
        test()
    
    def test_patch_with_spec_set(self):
        """测试spec_set属性约束"""
        @patch(f"{module_name}.SomeClass", spec_set=SomeClass)
        def test(MockClass):
            # 应禁止设置新属性
            self.assertRaises(AttributeError, setattr, MockClass, "z", "foo")
        
        self.assertRaises(AttributeError, test)
    
    def test_autospec_basic_functionality(self):
        """测试autospec基本功能"""
        @patch(f"{module_name}.Foo", autospec=True)
        def test(MockClass):
            # 验证自动规范
            instance = MockClass(1)
            instance.f(1)
            MockClass.assert_called_with(1)
            instance.f.assert_called_with(1)
            
            # 验证不存在的方法应引发错误
            self.assertRaises(AttributeError, getattr, instance, "non_existent_method")
        
        test()

class AdvancedPatchTests(PatchTestBase):
    """高级patch场景测试"""
    
    def test_patch_dict_basic(self):
        """测试字典patch基础功能"""
        target_dict = {"initial": "value", "other": "something"}
        original = target_dict.copy()
        
        @patch.dict(target_dict)
        def test():
            target_dict["a"] = 3
            del target_dict["initial"]
            target_dict["other"] = "modified"
        
        test()
        self.assertEqual(target_dict, original)
    
    def test_patch_dict_with_clear(self):
        """测试带clear选项的字典patch"""
        target_dict = {"key1": "value1", "key2": "value2"}
        original = target_dict.copy()
        
        @patch.dict(target_dict, {"new_key": "new_value"}, clear=True)
        def test():
            self.assertEqual(target_dict, {"new_key": "new_value"})
        
        test()
        self.assertEqual(target_dict, original)
    
    def test_patch_start_stop_lifecycle(self):
        """测试手动start/stop的生命周期管理"""
        original_value = something
        patcher = patch(f"{module_name}.something")
        
        self.assertIs(something, original_value)
        mock = patcher.start()
        try:
            self.assertIsNot(mock, original_value)
            self.assertIs(something, mock)
        finally:
            patcher.stop()
        
        self.assertIs(something, original_value)
    
    def test_patch_multiple_attributes(self):
        """测试多个属性一次性patch"""
        original_f = Foo.f
        original_g = Foo.g
        
        @patch.multiple(
            Foo, 
            f=Mock(return_value="patched_f"),
            g=Mock(return_value="patched_g")
        )
        def test():
            self.assertEqual(Foo.f(), "patched_f")
            self.assertEqual(Foo.g(), "patched_g")
        
        test()
        self.assertEqual(Foo.f, original_f)
        self.assertEqual(Foo.g, original_g)

class EdgeCaseTests(PatchTestBase):
    """边界条件和错误处理测试"""
    
    def test_patch_nonexistent_without_create(self):
        """测试patch不存在的属性(无create选项)"""
        @patch(f"{builtin_string}.non_existent_attr", sentinel.Value)
        def test():
            self.fail("不应允许patch不存在的属性")
        
        self.assertRaises(AttributeError, test)
        self.assertRaises(NameError, lambda: non_existent_attr)
    
    def test_patch_nonexistent_with_create(self):
        """测试patch不存在的属性(带create选项)"""
        @patch(f"{builtin_string}.non_existent_attr", sentinel.Value, create=True)
        def test():
            self.assertEqual(non_existent_attr, sentinel.Value)
        
        test()
        self.assertRaises(NameError, lambda: non_existent_attr)
    
    def test_patch_protected_with_slots(self):
        """测试带__slots__的类属性patch"""
        class SlottedClass:
            __slots__ = ("attribute",)
            attribute = sentinel.Original
        
        instance = SlottedClass()
        
        @patch.object(instance, "attribute", "patched")
        def test():
            self.assertEqual(instance.attribute, "patched")
        
        test()
        self.assertEqual(instance.attribute, sentinel.Original)
    
    def test_patch_error_propagation(self):
        """测试patch期间的错误传播"""
        @patch.dict("os.environ", {"key": "value"})
        def test():
            raise ValueError("测试异常")
        
        try:
            test()
        except ValueError:
            pass
        else:
            self.fail("异常未被传播")
        
        # 验证环境恢复
        self.assertNotIn("key", os.environ)

class PatchIntegrationTests(PatchTestBase):
    """patch集成特性测试"""
    
    def test_name_preservation(self):
        """测试函数名保留"""
        @patch(f"{module_name}.SomeClass")
        @patch.dict({})
        def sample_function():
            pass
        
        self.assertEqual(sample_function.__name__, "sample_function")
    
    def test_patch_class_decorator(self):
        """测试类级别的patch装饰器"""
        original_value = something
        
        class TestClass:
            def test_method(self, mock_something):
                self.assertIs(mock_something, something)
                self.assertIs(current_module.something, mock_something)
            
            def regular_method(self):
                self.assertEqual(current_module.something, original_value)
        
        # 应用类级别的patch
        PatchedClass = patch(f"{module_name}.something")(TestClass)
        
        instance = PatchedClass()
        instance.test_method()
        instance.regular_method()
        
        # 验证全局状态恢复
        self.assertEqual(something, original_value)
    
    def test_new_callable_functionality(self):
        """测试new_callable选项"""
        class CustomMock:
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs
        
        patcher = patch(
            f"{module_name}.Foo", 
            new_callable=CustomMock,
            arg1=1,
            arg2=2
        )
        
        mock = patcher.start()
        try:
            self.assertIsInstance(mock, CustomMock)
            self.assertEqual(mock.kwargs, {"arg1": 1, "arg2": 2})
        finally:
            patcher.stop()

class PatchTest(
    SinglePatchTests,
    PatchFunctionalityTests,
    SpecificationTests,
    AdvancedPatchTests,
    EdgeCaseTests,
    PatchIntegrationTests
):
    """所有patch测试的组合类"""
    
    # 这里可以根据需要添加类特定测试
    
    def test_comprehensive_autospec(self):
        """测试autospec的全面行为"""
        @patch(f"{module_name}.SomeClass", autospec=True)
        def test(MockClass):
            instance = MockClass()
            
            # 调用方法
            instance.wibble()
            
            # 验证调用记录
            instance.wibble.assert_called_once()
            MockClass.assert_called_once()
            
            # 验证不存在的方法
            self.assertRaises(AttributeError, getattr, instance, "non_existent")
        
        test()

if __name__ == "__main__":
    unittest.main(verbosity=2)

