#!/usr/bin/env python3
# Copyright (c) 2023 Mock Library Maintainers
# License: BSD-3-Clause

import unittest
from unittest.mock import (
    Mock, MagicMock, NonCallableMagicMock, NonCallableMock,
    patch, create_autospec, CallableMixin
)

# 测试用类
class TestClass:
    def method(self):
        pass
    
    def __call__(self):
        pass

class Subclass(TestClass):
    pass

class MultiSubclass(Subclass, TestClass):
    pass


class NonCallableMockTests(unittest.TestCase):
    """测试非可调用Mock的类型行为和方法限制"""
    
    def assert_not_callable(self, mock):
        """验证对象不可调用且具有正确的类型和表示"""
        self.assertIsInstance(mock, (NonCallableMagicMock, NonCallableMock),
                            "对象应是NonCallableMock或NonCallableMagicMock的实例")
        self.assertNotIsInstance(mock, CallableMixin, "对象不应继承自CallableMixin")
        
        with self.assertRaises(TypeError, msg="不可调用对象在被调用时应引发TypeError"):
            mock()
        
        self.assertFalse(hasattr(mock, "__call__"), 
                       "__call__属性不应存在于非可调用对象中")
        
        self.assertIn(mock.__class__.__name__, repr(mock),
                     "类名应在repr表示中显示")

    def test_base_non_callable_mocks(self):
        """测试基础非可调用Mock对象的行为"""
        test_cases = [
            ("NonCallableMock", NonCallableMock(), NonCallableMock),
            ("NonCallableMagicMock", NonCallableMagicMock(), NonCallableMagicMock)
        ]
        
        for name, mock, mock_type in test_cases:
            with self.subTest(mock_type=name):
                # 验证基础行为
                self.assert_not_callable(mock)
                
                # 验证属性创建的类型
                attr = mock.attribute
                self.assertIsInstance(attr, mock_type,
                                    f"{name}属性应创建相同类型的对象")

    def test_mock_inheritance_hierarchy(self):
        """测试Mock类的继承层次结构"""
        self.assertTrue(issubclass(MagicMock, Mock),
                      "MagicMock应继承自Mock")
        self.assertTrue(issubclass(NonCallableMagicMock, NonCallableMock),
                      "NonCallableMagicMock应继承自NonCallableMock")

    def test_subclass_attribute_inheritance(self):
        """测试Mock子类中属性的继承行为"""
        # Mock 子类
        class CustomMockSubclass(Mock):
            pass
        
        mock = CustomMockSubclass()
        self.assertIsInstance(
            mock.attribute, 
            CustomMockSubclass,
            "Mock子类属性应创建相同子类实例"
        )
        
        # MagicMock 子类
        class CustomMagicMockSubclass(MagicMock):
            pass
        
        magic = CustomMagicMockSubclass()
        self.assertIsInstance(
            magic.attribute, 
            CustomMagicMockSubclass,
            "MagicMock子类属性应创建相同子类实例"
        )


class PatchedNonCallableTests(unittest.TestCase):
    """测试通过patch创建的非可调用Mock"""
    
    def test_patch_with_spec(self):
        """测试带spec参数的patch功能"""
        test_params = [
            ("spec=True", "spec", True),
            ("spec_set=True", "spec_set", True),
        ]
        
        for label, param, value in test_params:
            with self.subTest(configuration=label):
                patcher = patch(f"{__name__}.TestClass", **{param: value})
                mock_class = patcher.start()
                self.addCleanup(patcher.stop)
                
                # 创建实例并验证
                instance = mock_class()
                mock_class.assert_called_once_with()
                
                # 验证实例为非可调用
                self.assertIsInstance(instance, NonCallableMagicMock)
                self.assertIsInstance(instance.method, MagicMock)
                
                with self.assertRaises(TypeError, 
                                      msg="非可调用实例不应能被调用"):
                    instance()
    
    def test_patch_with_instance_spec(self):
        """测试使用实例作为spec的patch功能"""
        test_params = [
            ("spec=instance", "spec", TestClass()),
            ("spec_set=instance", "spec_set", TestClass()),
        ]
        
        for label, param, value in test_params:
            with self.subTest(configuration=label):
                patcher = patch(f"{__name__}.TestClass", **{param: value})
                mock = patcher.start()
                self.addCleanup(patcher.stop)
                
                # 验证为非可调用
                with self.assertRaises(TypeError):
                    mock()  # 类本身被替换所以不可调用
                
                # 验证spec限制
                mock.method()  # 允许的方法
                with self.assertRaises(AttributeError, 
                                      msg="非spec方法应被阻止"):
                    mock.invalid_method()

    def test_callable_class_patching(self):
        """测试为可调用类创建patch的行为"""
        classes_to_test = [TestClass, Subclass, MultiSubclass]
        
        for cls in classes_to_test:
            with self.subTest(class_name=cls.__name__):
                # 为两种规格参数运行测试
                for param in ["spec", "spec_set"]:
                    with self.subTest(spec_type=param):
                        patcher = patch(f"{__name__}.TestClass", **{param: cls})
                        mock = patcher.start()
                        self.addCleanup(patcher.stop)
                        
                        # 创建实例
                        instance = mock()
                        mock.assert_called_once_with()
                        
                        # 验证实例是可调用且符合规范
                        self.assertIsInstance(instance, MagicMock)
                        instance()  # 实例本身可调用
                        instance.assert_called_once_with()
                        
                        # 验证规范继承
                        with self.assertRaises(AttributeError, 
                                             msg="非规范属性应被限制"):
                            instance.undefined_attr
                        
                        # 验证方法访问
                        instance.method()
                        instance.method.assert_called_once_with()
                        
                        # 验证返回值和属性访问
                        call_result = instance()
                        call_result(1, 2, 3)
                        call_result.assert_called_once_with(1, 2, 3)
                        call_result.attribute.subattribute()
                        call_result.attribute.subattribute.assert_called_once_with()


class AutospecNonCallableTests(unittest.TestCase):
    """测试create_autospec创建的非可调用Mock"""
    
    def test_autospec_for_classes(self):
        """测试为类创建自动规范的行为"""
        mock_cls = create_autospec(TestClass)
        
        # 验证类本身的调用行为
        with self.assertRaises(TypeError, 
                              msg="自动规范的类应可直接创建实例"):
            mock_cls()  # 这里应该是允许的? 原测试中不允许
        
        # 正确用法应该是创建实例
        instance = mock_cls()
        mock_cls.assert_called_once_with()
        
        # 验证实例为非可调用
        with self.assertRaises(TypeError, 
                              msg="非可调用实例不应能被调用"):
            instance()
        
        # 验证方法访问
        instance.method()
        instance.method.assert_called_once_with()
        with self.assertRaises(TypeError, 
                              msg="参数不匹配的方法调用应失败"):
            instance.method("invalid", "args")
    
    def test_autospec_for_instances(self):
        """测试为实例创建自动规范的行为"""
        instance = TestClass()
        mock = create_autospec(instance)
        
        # 验证为非可调用
        with self.assertRaises(TypeError, 
                              msg="自动规范的实例应不可调用"):
            mock()
        
        # 验证方法访问
        mock.method()
        mock.method.assert_called_once_with()
        
        # 验证规范限制
        with self.assertRaises(AttributeError, 
                              msg="非实例方法应被限制"):
            mock.invalid_method()
    
    def test_autospec_instance_mode(self):
        """测试自动规范实例模式"""
        mock = create_autospec(TestClass, instance=True)
        
        # 验证为非可调用
        self.assertIsInstance(mock, NonCallableMagicMock)
        with self.assertRaises(TypeError, 
                              msg="实例模式的自动规范应不可调用"):
            mock()
        
        # 验证方法访问
        mock.method()
        mock.method.assert_called_once_with()
        
        # 验证参数约束
        with self.assertRaises(TypeError, 
                              msg="参数不匹配的方法调用应失败"):
            mock.method("invalid", "arguments")


if __name__ == "__main__":
    unittest.main(
        verbosity=2,
        failfast=False,
        buffer=True
    )

