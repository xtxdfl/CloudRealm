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

import os
import ssl
import tempfile
import shutil
import unittest
from unittest.mock import patch, MagicMock
from security import CertificateManager
from cloudConfig import cloudConfig
from cloud_commons import OSCheck

class CertificateTestBase(unittest.TestCase):
    """证书管理测试基类，提供通用工具方法"""
    
    KEY_SIZE = 2048
    DEFAULT_PERMISSION = 0o600
    
    def setUp(self):
        """创建测试环境"""
        # 创建临时证书目录
        self.keys_dir = tempfile.mkdtemp(prefix="cloud_certs_test_")
        
        # 准备测试配置
        self.config = cloudConfig()
        self.config.add_section("server")
        self.config.add_section("security")
        self.config.set("server", "hostname", "test-server.example.com")
        self.config.set("server", "url_port", "8443")
        self.config.set("security", "keysdir", self.keys_dir)
        self.config.set("security", "passphrase", "securepass")
        self.config.set("security", "server_crt", "ca.crt")
        
        # 创建证书管理器实?        self.cert_manager = CertificateManager(
            self.config, self.config.get("server", "hostname")
        )
        
        # 创建初始证书
        self._create_initial_certificates()
        
    def tearDown(self):
        """清理测试环境"""
        shutil.rmtree(self.keys_dir, ignore_errors=True)
    
    def _create_initial_certificates(self):
        """创建初始证书文件"""
        # 创建CA证书
        self.ca_cert_path = os.path.join(self.keys_dir, "ca.crt")
        with open(self.ca_cert_path, "w") as f:
            f.write("-----BEGIN CERTIFICATE-----\nCA_CERTIFICATE_CONTENT\n-----END CERTIFICATE-----\n")
        
        # 创建代理私钥
        self.agent_key_path = os.path.join(self.keys_dir, "agent.key")
        with open(self.agent_key_path, "w") as f:
            f.write("-----BEGIN PRIVATE KEY-----\nAGENT_PRIVATE_KEY\n-----END PRIVATE KEY-----\n")
        
        # 设置有效权限
        os.chmod(self.ca_cert_path, 0o644)
        os.chmod(self.agent_key_path, 0o600)
    
    def _validate_certificate(self, cert_path):
        """验证证书文件的有效?""
        try:
            with open(cert_path, "r") as cert_file:
                content = cert_file.read()
            
            # 基本格式验证
            self.assertIn("-----BEGIN", content)
            self.assertIn("-----END", content)
            
            return True
        except Exception as e:
            self.fail(f"Certificate validation failed: {str(e)}")
            return False


class CertificateGenerationTests(CertificateTestBase):
    """测试证书生成功能"""
    
    @patch("os.chmod")
    @patch("cloud_agent.security.OpenSSL")
    def test_certificate_creation(self, openssl_mock, chmod_mock):
        """测试新证书生成流?""
        # 配置OpenSSL模拟
        key_mock = MagicMock()
        key_mock.generate_key.return_value = None
        
        req_mock = MagicMock()
        req_mock.set_pubkey.return_value = None
        req_mock.sign.return_value = None
        req_mock.get_pubkey.return_value = None
        
        pkey_mock = MagicMock()
        pkey_mock.to_cryptography_key.return_value = None
        
        openssl_mock.crypto.PKey.return_value = pkey_mock
        openssl_mock.crypto.X509Req.return_value = req_mock
        
        # 执行证书生成
        key_path = os.path.join(self.keys_dir, "new.key")
        req_path = os.path.join(self.keys_dir, "new.csr")
        
        self.cert_manager.genAgentCrtReq(key_path)
        
        # 验证文件存在?        self.assertTrue(os.path.exists(key_path))
        self.assertTrue(os.path.exists(req_path))
        
        # 验证权限设置
        chmod_mock.assert_called_with(key_path, self.DEFAULT_PERMISSION)
    
    def test_consecutive_certificate_generation(self):
        """测试连续证书生成"""
        # 首次生成
        key_path = os.path.join(self.keys_dir, "regen.key")
        self.cert_manager.genAgentCrtReq(key_path)
        first_mod_time = os.path.getmtime(key_path)
        
        # 二次生成 - 应覆盖原有文?        self.cert_manager.genAgentCrtReq(key_path)
        second_mod_time = os.path.getmtime(key_path)
        
        self.assertNotEqual(first_mod_time, second_mod_time)
    
    @patch("cloud_agent.security.OpenSSL", side_effect=Exception("Crypto error"))
    def test_certificate_generation_failure(self, openssl_mock):
        """测试证书生成失败处理"""
        key_path = os.path.join(self.keys_dir, "invalid.key")
        
        with self.assertRaises(RuntimeError):
            self.cert_manager.genAgentCrtReq(key_path)
        
        # 验证未创建不完整文件
        self.assertFalse(os.path.exists(key_path))


class CertificateValidationTests(CertificateTestBase):
    """测试证书验证功能"""
    
    def test_ca_certificate_validation(self):
        """测试CA证书验证流程"""
        certs = self.cert_manager.getCACerts()
        self.assertIsNotNone(certs)
        self.assertGreater(len(certs), 0)
        
        # 测试有效性验?        self.assertTrue(self.cert_manager.validateCACertificates(certs))
    
    def test_missing_ca_certificate(self):
        """测试缺失CA证书的情?""
        # 删除CA证书
        os.remove(self.ca_cert_path)
        
        with self.assertRaises(IOError):
            self.cert_manager.getCACerts()
    
    @patch("ssl.SSLContext.load_verify_locations")
    def test_certificate_chain_validation(self, load_mock):
        """测试完整证书链验?""
        # 创建证书?        server_cert = MagicMock()
        
        # 验证证书?        self.assertTrue(self.cert_manager.validateCertChain(
            [server_cert], self.ca_cert_path
        ))
        
        # 验证SSL上下文加?        load_mock.assert_called_once()
    
    @patch("ssl.SSLContext.load_verify_locations", side_effect=ssl.SSLError)
    def test_invalid_certificate_chain(self, load_mock):
        """测试无效证书链验?""
        server_cert = MagicMock()
        
        self.assertFalse(self.cert_manager.validateCertChain(
            [server_cert], self.ca_cert_path
        ))


class PrivateKeyManagementTests(CertificateTestBase):
    """测试私钥管理功能"""
    
    @patch("os.chmod")
    def test_private_key_permission_enforcement(self, chmod_mock):
        """测试私钥权限强制设置"""
        key_path = os.path.join(self.keys_dir, "perms.key")
        
        # 创建文件
        with open(key_path, "w") as f:
            f.write("Insecure key content")
        
        # 设置不安全权?        os.chmod(key_path, 0o777)
        
        # 验证权限修复
        self.cert_manager.enforceKeyPermissions(key_path)
        chmod_mock.assert_called_with(key_path, self.DEFAULT_PERMISSION)
    
    def test_private_key_loading(self):
        """测试私钥加载功能"""
        key = self.cert_manager.loadKey(self.agent_key_path)
        self.assertIsNotNone(key)
    
    @patch("cryptography.hazmat.primitives.serialization.load_pem_private_key")
    def test_encrypted_key_loading(self, load_key_mock):
        """测试加密私钥加载流程"""
        # 模拟加载加密密钥
        key_mock = MagicMock()
        load_key_mock.return_value = key_mock
        
        key = self.cert_manager.loadKey(
            self.agent_key_path,
            passphrase="securepass".encode()
        )
        
        self.assertIsNotNone(key)
        load_key_mock.assert_called_once()
    
    def test_missing_key_handling(self):
        """测试缺失私钥处理"""
        key_path = os.path.join(self.keys_dir, "missing.key")
        
        with self.assertRaises(IOError):
            self.cert_manager.loadKey(key_path)
    
    @patch("cryptography.hazmat.primitives.serialization.load_pem_private_key")
    def test_invalid_passphrase(self, load_key_mock):
        """测试无效密码处理"""
        load_key_mock.side_effect = ValueError("Invalid passphrase")
        
        with self.assertRaises(ValueError):
            self.cert_manager.loadKey(
                self.agent_key_path,
                passphrase="wrongpass".encode()
            )


class CertificateSigningTests(CertificateTestBase):
    """测试证书签名功能"""
    
    @patch("cloud_agent.security.urllib3.PoolManager")
    @patch("cloud_agent.security.CertificateManager._sign_request")
    def test_certificate_signing_request(self, sign_mock, http_mock):
        """测试证书签名请求流程"""
        # 模拟HTTP响应
        response_mock = MagicMock()
        response_mock.status = 200
        response_mock.data = b'{"SignedCert": "CERT_DATA"}'
        
        http_mock.return_value.request.return_value = response_mock
        
        # 模拟签名过程
        sign_mock.return_value = ("key_id", "signature")
        
        # 创建证书请求
        csr_content = "CERTIFICATE_REQUEST_CONTENT"
        
        # 发送签名请?        signed_cert = self.cert_manager.signCert(csr_content)
        
        # 验证签名证书
        self.assertEqual(signed_cert, "CERT_DATA")
        
        # 验证HTTP调用
        self.assertTrue(http_mock.called)
        self.assertTrue(sign_mock.called)
    
    @patch("cloud_agent.security.urllib3.PoolManager")
    def test_server_request_failure(self, http_mock):
        """测试证书签名服务失败"""
        # 模拟服务端错?        response_mock = MagicMock()
        response_mock.status = 500
        
        http_mock.return_value.request.return_value = response_mock
        
        # 发送签名请?        with self.assertRaises(RuntimeError):
            self.cert_manager.signCert("REQUEST_CONTENT")


class CertificateLifecycleTests(CertificateTestBase):
    """测试证书全生命周期管?""
    
    def test_full_certificate_lifecycle(self):
        """测试证书全生命周期流?""
        # 1. 生成私钥和CSR
        key_path = os.path.join(self.keys_dir, "lifecycle.key")
        csr_path = os.path.join(self.keys_dir, "lifecycle.csr")
        
        self.cert_manager.genAgentCrtReq(key_path)
        self.assertTrue(os.path.exists(key_path))
        self.assertTrue(os.path.exists(csr_path))
        
        # 2. 读取CSR内容
        with open(csr_path, "r") as f:
            csr_content = f.read()
        
        # 模拟签名过程
        with patch.object(self.cert_manager, "signCert") as sign_mock:
            sign_mock.return_value = "SIGNED_CERT_CONTENT"
            
            # 3. 发送签名请?            signed_cert = self.cert_manager.signCert(csr_content)
            self.assertEqual(signed_cert, "SIGNED_CERT_CONTENT")
        
        # 4. 保存签名后的证书
        cert_path = os.path.join(self.keys_dir, "lifecycle.crt")
        self.cert_manager.saveSignedCert(signed_cert, cert_path)
        self.assertTrue(os.path.exists(cert_path))
        
        # 5. 验证证书?        ca_certs = self.cert_manager.getCACerts()
        with open(cert_path, "rb") as f:
            agent_cert = f.read()
        
        validation_result = self.cert_manager.validateCert(
            agent_cert, ca_certs
        )
        self.assertTrue(validation_result)


if __name__ == "__main__":
    unittest.main()
