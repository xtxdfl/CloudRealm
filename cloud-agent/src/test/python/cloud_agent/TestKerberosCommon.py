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
"""

import unittest
from cloud_commons.kerberos.kerberos_common import (
    resolve_encryption_family_list,
    resolve_encryption_families,
)


class KerberosEncryptionTestBase(unittest.TestCase):
    """Kerberos加密类型测试基类"""
    
    # 定义标准加密类型集合
    ALL_AES_TYPES = {
        "aes256-cts-hmac-sha1-96",
        "aes128-cts-hmac-sha1-96",
        "aes256-cts-hmac-sha384-192",
        "aes128-cts-hmac-sha256-128"
    }
    
    RC4_TYPE = {"rc4-hmac"}


class EncryptionFamilyListTests(KerberosEncryptionTestBase):
    """测试加密家族列表解析功能"""
    
    def test_resolve_family_groups(self):
        """测试解析加密家族组（如aes、rc4�?""
        result = resolve_encryption_family_list(["rc4", "aes"])
        expected = self.ALL_AES_TYPES | self.RC4_TYPE
        self.assertEqual(result, expected)
    
    def test_handle_single_family(self):
        """测试处理单个加密家族"""
        result = resolve_encryption_family_list(["aes"])
        self.assertEqual(result, self.ALL_AES_TYPES)
    
    def test_ignore_invalid_families(self):
        """测试忽略无效的加密家�?""
        result = resolve_encryption_family_list(["invalid", "aes"])
        self.assertEqual(result, self.ALL_AES_TYPES)
    
    def test_return_specific_types_as_is(self):
        """测试直接返回具体的加密类型（无家族组�?""
        specific_types = {"rc4-hmac", "aes256-cts-hmac-sha1-96"}
        result = resolve_encryption_family_list(specific_types)
        self.assertEqual(result, specific_types)
    
    def test_remove_duplicate_values(self):
        """测试移除重复的加密类�?""
        input_list = ["aes", "aes128-cts-hmac-sha1-96", "aes"]
        result = resolve_encryption_family_list(input_list)
        expected = self.ALL_AES_TYPES
        self.assertEqual(result, expected)
    
    def test_case_insensitivity(self):
        """测试大小写不敏感解析"""
        result = resolve_encryption_family_list(["AES", "RC4"])
        expected = self.ALL_AES_TYPES | self.RC4_TYPE
        self.assertEqual(result, expected)
    
    def test_whitespace_handling(self):
        """测试正确处理包含空格的输�?""
        result = resolve_encryption_family_list([" aes ", " rc4 "])
        expected = self.ALL_AES_TYPES | self.RC4_TYPE
        self.assertEqual(result, expected)
    
    def test_empty_input_handling(self):
        """测试处理空输�?""
        result = resolve_encryption_family_list([])
        self.assertEqual(result, set())


class EncryptionFamilyTranslationTests(KerberosEncryptionTestBase):
    """测试单个加密家族名称翻译功能"""
    
    def test_translate_aes_family(self):
        """测试翻译aes家族名称"""
        self.assertEqual(resolve_encryption_families("aes"), "aes")
    
    def test_translate_rc4_family(self):
        """测试翻译rc4家族名称"""
        self.assertEqual(resolve_encryption_families("rc4"), "rc4-hmac")
    
    def test_return_specific_types(self):
        """测试返回具体的加密类型名�?""
        for enc_type in self.ALL_AES_TYPES | self.RC4_TYPE:
            with self.subTest(enc_type=enc_type):
                self.assertEqual(resolve_encryption_families(enc_type), enc_type)
    
    def test_case_insensitive_translation(self):
        """测试大小写不敏感翻译"""
        self.assertEqual(resolve_encryption_families("RC4"), "rc4-hmac")
        self.assertEqual(resolve_encryption_families("AES"), "aes")
    
    def test_ignore_whitespace(self):
        """测试忽略输入中的空格"""
        self.assertEqual(resolve_encryption_families(" rc4 "), "rc4-hmac")
    
    def test_untranslatable_values(self):
        """测试无法翻译的值应该原样返�?""
        self.assertEqual(resolve_encryption_families("unknown"), "unknown")
        self.assertEqual(resolve_encryption_families("custom-type"), "custom-type")
    
    def test_empty_input_translation(self):
        """测试空输入翻�?""
        self.assertEqual(resolve_encryption_families(""), "")


class EncryptionCompatibilityTests(KerberosEncryptionTestBase):
    """测试加密类型兼容性功�?""
    
    def test_backward_compatibility(self):
        """测试向后兼容�?""
        # 验证旧名称映射仍然有�?        old_names = ["des", "des3", "arcfour"]
        for name in old_names:
            result = resolve_encryption_families(name)
            self.assertNotEqual(result, name)  # 应该被映�?

class EncryptionPerformanceTests(KerberosEncryptionTestBase):
    """测试加密类型解析性能"""
    
    def test_large_input_performance(self):
        """测试大输入集合的性能"""
        # 创建大型输入集合（包�?0000个条目）
        large_input = ["aes"] * 5000 + ["rc4"] * 5000
        
        # 执行解析
        result = resolve_encryption_family_list(large_input)
        
        # 验证结果（应仅包含唯一值）
        self.assertEqual(len(result), len(self.ALL_AES_TYPES | self.RC4_TYPE))
        self.assertTrue(self.ALL_AES_TYPES.issubset(result))
        self.assertIn("rc4-hmac", result)


class EdgeCaseTests(KerberosEncryptionTestBase):
    """测试边界情况处理"""
    
    def test_unsupported_family(self):
        """测试不支持的加密家族"""
        result = resolve_encryption_family_list(["unsupported"])
        self.assertEqual(result, set())
    
    def test_single_character_families(self):
        """测试单字符家族名�?""
        self.assertEqual(resolve_encryption_families("a"), "a")
    
    def test_special_characters(self):
        """测试特殊字符处理"""
        special_chars = ["!@#$%", "aes!rc4", "rc4-hmac?"]
        for char in special_chars:
            with self.subTest(char=char):
                result = resolve_encryption_families(char)
                self.assertEqual(result, char)
    
    def test_mixed_types_and_families(self):
        """测试混合加密类型和家族名�?""
        input_list = ["rc4", "aes", "aes256-cts-hmac-sha1-96", "custom-enc"]
        result = resolve_encryption_family_list(input_list)
        expected = self.ALL_AES_TYPES | self.RC4_TYPE | {"custom-enc"}
        self.assertEqual(result, expected)
    
    def test_none_input_handling(self):
        """测试处理None输入"""
        self.assertEqual(resolve_encryption_families(None), None)
        self.assertEqual(resolve_encryption_family_list(None), set())


if __name__ == "__main__":
    unittest.main()
