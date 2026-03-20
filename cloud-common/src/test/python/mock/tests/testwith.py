#!/usr/bin/env python3
"""Python 3单元测试启动脚本：自动化测试环境设置和执行"""
import sys
import unittest
import os

# 验证Python版本要求
def validate_python_version():
    """确保使用Python 3.5+版本"""
    required = (3, 5)
    if sys.version_info < required:
        sys.stderr.write(f"错误: 需要Python {required[0]}.{required[1]}+版本\n")
        sys.exit(1)

def discover_and_run_tests():
    """
    自动发现并运行所有测试
    """
    # 配置测试发现参数
    test_dir = os.path.abspath(os.path.dirname(__file__))
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover(
        start_dir=test_dir,
        pattern='test_*.py',
        top_level_dir=os.path.dirname(test_dir)
    )
    
    # 配置测试运行器
    runner = unittest.TextTestRunner(
        verbosity=2,
        failfast=False,
        buffer=True
    )
    
    # 执行测试套件
    print(f"在目录: {test_dir}")
    print(f"搜索测试模式: test_*.py")
    print(f"发现测试套件数量: {test_suite.countTestCases()}\n")
    
    return runner.run(test_suite)

def main():
    """主执行函数"""
    # 验证Python版本
    validate_python_version()
    
    # 执行测试并返回结果
    result = discover_and_run_tests()
    
    # 返回退出代码
    sys.exit(not result.wasSuccessful())

if __name__ == '__main__':
    print("=" * 70)
    print(f"Python单元测试框架: {sys.version}")
    print("=" * 70)
    
    main()

