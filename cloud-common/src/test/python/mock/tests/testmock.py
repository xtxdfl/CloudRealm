#!/usr/bin/env python3
# Copyright (c) 2023 Mock Library Maintainers
# License: BSD-3-Clause

import sys
import copy
import pickle
import unittest
from unittest.mock import (
    call, DEFAULT, MagicMock, Mock, NonCallableMock, 
    NonCallableMagicMock, create_autospec, sentinel
)

# 定义辅助类和函数
class Iterable:
    """可迭代对象的测试类"""
    def __init__(self):
        self.items = ["this", "is", "an", "iterable"]
    
    def __iter__(self):
        return iter(self.items)
    
    def __next__(self):
        return next(iter(self.items))

class SubclassWithProperties(MagicMock):
    """带有属性的子类测试"""
    def _get_property(self):
        return 42
    
    def _set_property(self, value):
        raise ValueError("Property cannot be set")
    
    some_property = property(_get_property, _set_property)

class Thing:
    """基础属性测试类"""
    attribute = 6
    foo = "bar"

class MockConstructorTests(unittest.TestCase):
    """Mock 构造函数基础功能测试"""
    
    def test_default_initialization(self):
        """测试默认初始状态"""
        mock = Mock()
        self.assertFalse(mock.called, "新创建的 mock 应该未被调用")
        self.assertEqual(mock.call_count, 0, "初始调用次数应为 0")
        self.assertIsInstance(mock.return_value, Mock, "默认返回值应为 Mock 实例")
        self.assertIsNone(mock.call_args, "初始调用参数应为 None")
        self.assertEqual(mock.call_args_list, [], "调用参数列表应为空")
        self.assertEqual(mock.method_calls, [], "方法调用列表应为空")
        self.assertIsNone(mock._mock_parent, "初始父级应为 None")
        self.assertEqual(mock._mock_children, {}, "子级字典应为空")
    
    def test_return_value_in_constructor(self):
        """测试构造函数中返回值的设置"""
        mock = Mock(return_value="preset_value")
        self.assertEqual(mock(), "preset_value", "构造函数中设置的返回值未生效")

class MockReprTests(unittest.TestCase):
    """Mock 的 repr 表示测试"""
    
    def test_mock_repr_basic(self):
        """测试基础 repr 表示"""
        mock = Mock(name="basic_mock")
        repr_str = repr(mock)
        self.assertIn("name='basic_mock'", repr_str, "名称应在 repr 中显示")
        self.assertIn(str(id(mock)), repr_str, "对象 ID 应在 repr 中显示")
    
    def test_attribute_repr(self):
        """测试属性的 repr 表示"""
        mock = Mock(name="parent")
        parent_repr = repr(mock)
        child_repr = repr(mock.child)
        self.assertIn("name='parent.child'", child_repr, "属性名称应包含父级名称")
    
    def test_spec_repr(self):
        """测试带 spec 的 repr 表示"""
        class SpecClass: pass
        
        mock = Mock(spec=SpecClass, name="spec_mock")
        repr_str = repr(mock)
        self.assertIn("spec='SpecClass'", repr_str, "spec 信息应在 repr 中显示")
        
        mock = Mock(spec_set=SpecClass, name="spec_mock")
        repr_str = repr(mock)
        self.assertIn("spec_set='SpecClass'", repr_str, "spec_set 信息应在 repr 中显示")

class MockSideEffectTests(unittest.TestCase):
    """Mock 的 side_effect 功能测试"""
    
    def test_exception_side_effect(self):
        """测试异常副作用"""
        mock = Mock(side_effect=ValueError("Test Error"))
        with self.assertRaises(ValueError, msg="应抛出配置的异常"):
            mock()
    
    def test_iterable_side_effect(self):
        """测试可迭代对象的副作用"""
        mock = Mock(side_effect=[1, 2, 3])
        self.assertEqual(mock(), 1, "第一次调用应返回第一个值")
        self.assertEqual(mock(), 2, "第二次调用应返回第二个值")
        self.assertEqual(mock(), 3, "第三次调用应返回第三个值")
        with self.assertRaises(StopIteration, msg="迭代结束后应抛出 StopIteration"):
            mock()
    
    def test_dynamic_side_effect(self):
        """测试动态返回值副作用"""
        results = [10, 20, 30]
        mock = Mock(side_effect=results.pop)
        self.assertEqual(mock(), 30, "应从列表末尾返回")
        self.assertEqual(mock(), 20, "应从列表末尾返回")
        self.assertEqual(mock(), 10, "应从列表末尾返回")
    
    def test_mixed_side_effect(self):
        """测试混合异常和返回值的副作用"""
        mock = Mock(side_effect=[ValueError, "success"])
        with self.assertRaises(ValueError, msg="第一次调用应抛出异常"):
            mock()
        self.assertEqual(mock(), "success", "第二次调用应返回成功值")

class MockCallTests(unittest.TestCase):
    """Mock 的调用行为测试"""
    
    def test_basic_calling(self):
        """测试基本调用行为"""
        mock = Mock()
        result1 = mock()
        result2 = mock("arg")
        self.assertEqual(result1, result2, "相同 mock 的返回值应一致")
        self.assertTrue(mock.called, "应在调用后标记为已调用")
        self.assertEqual(mock.call_count, 2, "调用次数应增加")
    
    def test_call_arguments(self):
        """测试带参数的调用"""
        mock = Mock()
        mock(1, 2, key="value")
        self.assertEqual(mock.call_args, ((1, 2), {"key": "value"}))
        self.assertEqual(
            mock.call_args_list, 
            [((1, 2), {"key": "value"})]
        )
    
    def test_method_calls(self):
        """测试方法调用"""
        mock = Mock()
        mock.method(1, 2)
        mock.child.method(3, 4)
        
        self.assertEqual(
            mock.method_calls,
            [call.method(1, 2), call.child.method(3, 4)]
        )
        self.assertEqual(
            mock.mock_calls,
            [call.method(1, 2), call.child.method(3, 4)]
        )

class MockAssertionTests(unittest.TestCase):
    """Mock 的断言方法测试"""
    
    def setUp(self):
        self.mock = Mock()
        self.mock(1, 2, a=3)
        self.mock.method("foo", "bar")
    
    def test_assert_called_with(self):
        """测试 assert_called_with"""
        # 成功断言
        self.mock.assert_called_with(1, 2, a=3)
        
        # 失败断言
        with self.assertRaises(AssertionError, msg="参数不匹配时应失败"):
            self.mock.assert_called_with(4, 5)
    
    def test_assert_called_once_with(self):
        """测试 assert_called_once_with"""
        mock = Mock()
        mock("single")
        mock.assert_called_once_with("single")
        
        mock("another")
        with self.assertRaises(AssertionError, msg="多次调用时应失败"):
            mock.assert_called_once_with("another")
    
    def test_assert_any_call(self):
        """测试 assert_any_call"""
        self.mock.assert_any_call(1, 2, a=3)
        self.mock.assert_any_call.method("foo", "bar")
        
        with self.assertRaises(AssertionError, msg="未进行的调用应失败"):
            self.mock.assert_any_call("unused")
    
    def test_assert_has_calls(self):
        """测试 assert_has_calls"""
        expected_calls = [
            call(1, 2, a=3), 
            call.method("foo", "bar")
        ]
        self.mock.assert_has_calls(expected_calls)
        
        # 测试顺序不重要的情况
        self.mock.assert_has_calls(
            [call.method("foo", "bar"), call(1, 2, a=3)], 
            any_order=True
        )
        
        with self.assertRaises(AssertionError, msg="缺少调用时应失败"):
            self.mock.assert_has_calls(expected_calls + [call.extra()])

class MockAttributeTests(unittest.TestCase):
    """Mock 的属性处理测试"""
    
    def test_attribute_creation(self):
        """测试属性自动创建"""
        mock = Mock()
        # 访问未定义属性应生成新 mock
        self.assertIsInstance(mock.new_attribute, Mock)
        self.assertEqual(
            mock.new_attribute._mock_name, "new_attribute",
            "属性应有正确的名称"
        )
    
    def test_spec_restrictions(self):
        """测试 spec 约束"""
        class SpecClass:
            allowed = 1
            
            def method(self):
                pass
        
        for spec_type in ['spec', 'spec_set']:
            mock = Mock(**{spec_type: SpecClass})
            # 允许存在的属性
            mock.allowed
            mock.method()
            
            # 不允许的属性
            with self.assertRaises(AttributeError, msg="未在 spec 中的属性应被阻止"):
                mock.forbidden_attribute
    
    def test_wrapped_attributes(self):
        """测试包装对象的属性"""
        real = Thing()
        mock = Mock(wraps=real)
        self.assertEqual(mock.attribute, 6, "应访问真实对象的属性")
        
        with self.assertRaises(AttributeError, msg="真实对象不存在的属性应引发错误"):
            mock.nonexistent_attribute

class MockAutospecTests(unittest.TestCase):
    """Mock 的 auto_spec 功能测试"""
    
    def test_autospec_basic(self):
        """测试基础 auto_spec 行为"""
        class Target:
            def method(self, a, b):
                return a + b
        
        # 创建带自动规范的对象
        mock = create_autospec(Target)
        mock.method(1, 2)
        
        # 验证调用
        mock.method.assert_called_once_with(1, 2)
        
        # 测试参数数量验证
        with self.assertRaises(TypeError, msg="参数数量错误应引发 TypeError"):
            mock.method(1)
        
        # 测试未定义方法
        with self.assertRaises(AttributeError, msg="未定义的方法应被阻止"):
            mock.undefined()

class MockConfigureTests(unittest.TestCase):
    """Mock 的配置方法测试"""
    
    def test_configure_mock(self):
        """测试 configure_mock 方法"""
        mock = Mock()
        
        # 初始配置
        mock.configure_mock(
            return_value=10,
            side_effect=ValueError,
            attribute=20
        )
        
        self.assertEqual(mock(), 10, "返回值配置未生效")
        with self.assertRaises(ValueError, msg="副作用配置未生效"):
            mock()
        self.assertEqual(mock.attribute, 20, "属性配置未生效")
        
        # 更新配置
        mock.configure_mock(return_value=30, side_effect=None)
        self.assertEqual(mock(), 30, "更新后的返回值未生效")
    
    def test_nested_configuration(self):
        """测试嵌套属性配置"""
        mock = Mock()
        mock.configure_mock(
            child=Mock(),
            child.return_value={"key": "value"},
            another.method.return_value=42
        )
        
        self.assertIsInstance(mock.child(), dict, "嵌套属性配置未生效")
        self.assertEqual(
            mock.another.method(), 
            42, 
            "深度嵌套配置未生效"
        )

class MockResetTests(unittest.TestCase):
    """Mock 的 reset 功能测试"""
    
    def test_reset_mock(self):
        """测试 reset_mock 方法"""
        mock = Mock(return_value=Mock())
        mock.child = Mock()
        
        # 执行一些操作
        result = mock(1, 2, a=3)
        result.method()
        mock.child.attribute = 10
        mock.child.method(4, 5)
        
        # 重置
        mock.reset_mock()
        
        # 验证状态被重置
        self.assertFalse(mock.called, "called 状态未被重置")
        self.assertEqual(mock.call_count, 0, "call_count 未被重置")
        self.assertEqual(mock.method_calls, [], "method_calls 未被重置")
        
        # 子对象也应被重置
        self.assertFalse(mock.child.called, "子对象的 called 状态未被重置")
        self.assertEqual(
            mock.child.method_calls, 
            [], 
            "子对象的方法调用未被重置"
        )
    
    def test_reset_recursive(self):
        """测试递归重置是否安全"""
        mock = Mock()
        mock.self_ref = mock  # 创建循环引用
        
        # 应不会导致递归错误
        mock.reset_mock()

class MagicMockTests(unittest.TestCase):
    """MagicMock 特殊功能测试"""
    
    def test_magic_methods(self):
        """测试魔术方法支持"""
        mock = MagicMock()
        
        # 长度测试
        mock.__len__.return_value = 3
        self.assertEqual(len(mock), 3, "__len__ 魔术方法未正确实现")
        
        # 迭代测试
        mock.__iter__.return_value = iter([1, 2, 3])
        self.assertEqual(list(mock), [1, 2, 3], "__iter__ 魔术方法未正确实现")
        
        # 包含测试
        mock.__contains__.return_value = True
        self.assertIn("anything", mock, "__contains__ 魔术方法未正确实现")
    
    def test_mock_calls_hierarchy(self):
        """测试复杂调用层次结构"""
        mock = MagicMock()
        
        # 多层调用
        mock().foo().bar().baz()
        
        # 验证调用层次
        expected_calls = [call(), call().foo(), call().foo().bar(), call().foo().bar().baz()]
        self.assertEqual(
            mock.mock_calls, 
            expected_calls,
            "复杂调用层次记录不正确"
        )

class MockPickleTests(unittest.TestCase):
    """Mock 的序列化测试（预期失败）"""
    
    @unittest.expectedFailure
    def test_pickling(self):
        """测试序列化/反序列化（预期失败）"""
        for Klass in (Mock, MagicMock, NonCallableMagicMock):
            # 创建配置好的 mock
            mock = Klass(name="test_mock")
            mock.attribute = 42
            mock.method(1, 2, 3)
            
            # 序列化
            data = pickle.dumps(mock)
            
            # 反序列化
            new_mock = pickle.loads(data)
            
            # 验证配置
            self.assertEqual(
                new_mock.attribute, 
                42, 
                "属性未正确反序列化"
            )
            new_mock.method.assert_called_once_with(1, 2, 3)

class MockEdgeCaseTests(unittest.TestCase):
    """Mock 的边缘情况测试"""
    
    def test_infinite_recursion_safety(self):
        """测试无限递归安全性"""
        mock = Mock()
        
        # 创建循环引用
        mock.self_reference = mock
        mock().return_value = mock
        
        # 应不会导致无限递归
        self.assertIs(mock(), mock)
        self.assertIs(mock().self_reference, mock)
    
    def test_add_spec_dynamically(self):
        """测试动态添加 spec"""
        class InitialSpec:
            allowed_method = Mock()
        
        class NewSpec:
            new_method = Mock()
            forbidden_method = Mock()
        
        mock = Mock(spec=InitialSpec)
        
        # 初始允许的方法
        mock.allowed_method()
        
        # 初始不允许的方法
        with self.assertRaises(AttributeError):
            mock.forbidden_method()
        
        # 动态添加新 spec
        mock.mock_add_spec(NewSpec)
        
        # 验证新方法
        mock.new_method()
        
        # 验证旧方法被禁止
        with self.assertRaises(AttributeError):
            mock.allowed_method()
    
    def test_property_in_subclass(self):
        """测试子类中的属性处理"""
        mock = SubclassWithProperties(spec_set=SubclassWithProperties)
        
        # 测试属性访问
        self.assertEqual(
            mock.some_property, 
            42, 
            "属性未正确处理"
        )
        
        # 测试属性设置
        with self.assertRaises(ValueError, msg="只读属性设置未引发错误"):
            mock.some_property = 99

class MockDirTests(unittest.TestCase):
    """Mock 的 __dir__ 方法测试（Python 2.6+）"""
    
    @unittest.skipIf(sys.version_info < (2, 6), "__dir__ requires Python 2.6+")
    def test_dir_basic(self):
        """测试基础的 __dir__ 实现"""
        mock = Mock()
        attrs = dir(mock)
        
        # 应包含标准 mock 方法
        for name in ["assert_called", "reset_mock", "call_count"]:
            self.assertIn(name, attrs, f"基本方法 {name} 未包含在 dir 中")
        
        # 添加属性
        mock.new_attribute = None
        self.assertIn("new_attribute", dir(mock), "新增属性未包含在 dir 中")
    
    @unittest.skipIf(sys.version_info < (2, 6), "__dir__ requires Python 2.6+")
    def test_dir_with_spec(self):
        """测试带 spec 的 __dir__"""
        class SpecClass:
            SPEC_ATTR = "value"
            
            def spec_method(self):
                pass
        
        mock = Mock(spec=SpecClass)
        attrs = dir(mock)
        
        # 应包含 spec 的成员
        self.assertIn("SPEC_ATTR", attrs, "spec 属性未包含")
        self.assertIn("spec_method", attrs, "spec 方法未包含")
        
        # 不应包含未在 spec 中的成员
        self.assertNotIn("non_spec_method", attrs, "非 spec 成员被包含")

if __name__ == "__main__":
    unittest.main(
        verbosity=2,
        failfast=False,
        buffer=True,
    )
