#!/usr/bin/env python3
import sys
import unittest

# 现代兼容处理：Python 2.5之前版本的支持层
if sys.version_info[:2] < (2, 5):
    # 创建跳过测试的桩模块
    class SkipWithTests(unittest.TestCase):
        """跳过所有with语句测试（Python <2.5不支持）"""
        
        @unittest.skip("with语句在Python 2.5以下版本不受支持")
        def test_with_statement_features(self):
            """占位方法：跳过with语句相关测试"""
            
    # 使用跳过类作为替代实现
    TestWith = SkipWithTests
else:
    # Python 2.5+ 导入实际测试
    from tests._testwith import TestWith


if __name__ == "__main__":
    # 统一测试执行
    unittest.main(
        verbosity=2,
        failfast=True,
        module=__name__,
        argv=sys.argv
    )

