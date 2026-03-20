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
from unittest.mock import patch, MagicMock, call
import os
import ssl
import tempfile
import configparser
import subprocess
import cloud_agent.security as security
from cloud_agent.cloudConfig import cloudConfig


class BaseSecurityTestCase(unittest.TestCase):
    """安全模块测试基类"""
    
    def setUp(self):
        # 创建配置对象
        self.config = cloudConfig()
        self.config.set("security", "ssl_verify_cert", "0")
        self.config.set("security", "keysdir", "/dummy/keys")
        self.config.set("server", "hostname", "example.com")
        self.config.set("server", "secured_url_port", "8443")
        
        # 模拟OS环境
        os.environ["DUMMY_PASSPHRASE"] = "test-passphrase"
        self.config.set("security", "passphrase_env_var_name", "DUMMY_PASSPHRASE")


class CachedHTTPSConnectionTests(BaseSecurityTestCase):
    """测试可缓存的HTTPS连接功能"""
    
    @patch.object(security.VerifiedHTTPSConnection, "connect")
    def test_connection_management(self, connect_mock):
        """测试连接建立与重�?""
        with security.CachedHTTPSConnection(self.config, "test-server") as conn:
            # 初始连接
            conn.connect()
            self.assertTrue(connect_mock.called)
            connect_mock.reset_mock()
            
            # 连接重用
            conn.connect()
            self.assertFalse(connect_mock.called)
    
    @patch.object(security.VerifiedHTTPSConnection, "close")
    def test_implicit_cleanup(self, close_mock):
        """测试上下文管理器自动清理"""
        with security.CachedHTTPSConnection(self.config, "test-server"):
            pass
        self.assertTrue(close_mock.called)
    
    @patch.object(security.CachedHTTPSConnection, "connect")
    def test_request_handling(self, connect_mock):
        """测试HTTP请求处理"""
        # 创建模拟连接
        http_response = MagicMock()
        http_response.read.return_value = b"response data"
        
        https_conn = MagicMock()
        https_conn.getresponse.return_value = http_response
        
        conn = security.CachedHTTPSConnection(self.config, "test-server")
        conn.httpsconn = https_conn
        
        # 执行请求
        method = "GET"
        url = "/api/data"
        data = b"payload"
        headers = {"Content-Type": "application/json"}
        
        response = conn.request(MagicMock(
            get_method=lambda: method,
            get_full_url=lambda: url,
            get_data=lambda: data,
            headers=headers
        ))
        
        # 验证请求参数
        https_conn.request.assert_called_with(method, url, data, headers)
        self.assertEqual(response, http_response.read.return_value)
    
    @patch.object(security.VerifiedHTTPSConnection, "request")
    def test_error_handling(self, request_mock):
        """测试网络异常处理"""
        request_mock.side_effect = Exception("Network failure")
        
        conn = security.CachedHTTPSConnection(self.config, "test-server")
        
        with self.assertRaises(IOError):
            conn.request(MagicMock())


class CertificateManagerTests(BaseSecurityTestCase):
    """测试证书管理功能"""
    
    @patch("cloud_agent.hostname.hostname")
    def test_certificate_path_management(self, hostname_mock):
        """测试证书路径管理"""
        hostname_mock.return_value = "test-server.example.com"
        manager = security.CertificateManager(self.config, "cluster-01")
        
        # 测试证书路径获取
        self.assertEqual(
            manager.getAgentKeyName(), 
            os.path.abspath("/dummy/keys/test-server.example.com.key")
        )
        self.assertEqual(
            manager.getAgentCrtName(),
            os.path.abspath("/dummy/keys/test-server.example.com.crt")
        )
        self.assertEqual(
            manager.getAgentCrtReqName(),
            os.path.abspath("/dummy/keys/test-server.example.com.csr")
        )
        self.assertEqual(
            manager.getSrvrCrtName(),
            os.path.abspath("/dummy/keys/ca.crt")
        )
    
    @patch("os.path.exists")
    def test_certificate_existence_checking(self, exists_mock):
        """测试证书存在性检�?""
        manager = security.CertificateManager(self.config, "cluster-01")
        
        # 所有证书都存在
        exists_mock.side_effect = [True, True, True]
        self.assertTrue(manager.checkCertExists())
        
        # 服务器证书缺�?        exists_mock.side_effect = [False, True, True]
        self.assertFalse(manager.checkCertExists())
        
        # 代理私钥缺失
        exists_mock.side_effect = [True, False, True]
        self.assertFalse(manager.checkCertExists())
        
        # 代理证书缺失
        exists_mock.side_effect = [True, True, False]
        self.assertFalse(manager.checkCertExists())
    
    @patch.object(security.CertificateManager, "loadSrvrCrt")
    @patch.object(security.CertificateManager, "getSrvrCrtName")
    def test_server_certificate_loading(self, srvcrt_mock, load_mock):
        """测试服务器证书加�?""
        srvcrt_mock.return_value = "/dummy/keys/ca.crt"
        manager = security.CertificateManager(self.config, "cluster-01")
        
        # 证书不存在时需要加�?        with patch("os.path.exists", return_value=False):
            manager.checkCertExists()
            self.assertTrue(load_mock.called)
        
        # 证书已存在时不加�?        with patch("os.path.exists", return_value=True):
            load_mock.reset_mock()
            manager.checkCertExists()
            self.assertFalse(load_mock.called)
    
    @patch("urllib.request.urlopen")
    def test_server_certificate_download(self, urlopen_mock):
        """测试服务器证书下�?""
        # 创建临时文件
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            target_path = tmp_file.name
        
        # 设置模拟响应
        mock_response = MagicMock()
        mock_response.read.return_value = b"-----BEGIN CERTIFICATE-----"
        urlopen_mock.return_value = mock_response
        
        manager = security.CertificateManager(self.config, "cluster-01")
        manager.getSrvrCrtName = MagicMock(return_value=target_path)
        
        # 执行下载
        manager.loadSrvrCrt()
        
        # 验证文件内容
        with open(target_path, "rb") as f:
            content = f.read()
            self.assertEqual(content, mock_response.read.return_value)
        
        # 清理
        os.unlink(target_path)
    
    @patch.object(subprocess, "Popen")
    def test_certificate_request_generation(self, popen_mock):
        """测试证书请求生成"""
        # 设置模拟进程
        process_mock = MagicMock()
        process_mock.communicate.return_value = (b"", b"")
        popen_mock.return_value = process_mock
        
        manager = security.CertificateManager(self.config, "cluster-01")
        key_path = "/dummy/keys/test.key"
        csr_path = "/dummy/keys/test.csr"
        
        # 生成证书请求
        with patch.object(manager, "getAgentCrtReqName", return_value=csr_path):
            manager.genAgentCrtReq(key_path)
        
        # 验证命令执行
        expected_cmd = [
            "openssl", "req", "-new", "-batch",
            "-key", key_path,
            "-out", csr_path,
            "-subj", f"/CN={manager.agent_hostname}/OU={manager.cluster_name}"
        ]
        popen_mock.assert_called_once_with(expected_cmd, stderr=subprocess.PIPE)
    
    @patch.object(security.CertificateManager, "getAgentCrtName")
    @patch.object(security.CertificateManager, "getAgentCrtReqName")
    @patch("builtins.open", new_callable=MagicMock)
    @patch("urllib.request.urlopen")
    def test_certificate_signing_request(self, urlopen_mock, open_mock, csr_mock, crt_mock):
        """测试证书签名请求处理"""
        # 配置文件模拟
        open_mock.return_value.__enter__.return_value.read.return_value = b"CSR_CONTENT"
        
        # 设置模拟响应（成功）
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"result":"OK","signedCa":"CERT_CONTENT"}'
        urlopen_mock.return_value = mock_response
        
        manager = security.CertificateManager(self.config, "cluster-01")
        
        # 执行签名请求
        manager.reqSignCrt()
        
        # 验证证书写入
        open_mock().write.assert_called_with(b"CERT_CONTENT")
    
    @patch("urllib.request.urlopen")
    def test_certificate_signing_errors(self, urlopen_mock):
        """测试证书签名错误处理"""
        manager = security.CertificateManager(self.config, "cluster-01")
        
        # 测试服务端拒绝签�?        mock_response = MagicMock()
        mock_response.read.return_value = b'{"result":"FAIL","message":"Invalid CSR"}'
        urlopen_mock.return_value = mock_response
        
        with self.assertLogs(level="ERROR") as logs:
            with self.assertRaises(ssl.SSLError):
                manager.reqSignCrt()
        self.assertIn("Invalid CSR", logs.output[0])
        
        # 测试无效JSON响应
        urlopen_mock.return_value.read.return_value = b"{invalid json"
        with self.assertRaises(ssl.SSLError):
            manager.reqSignCrt()
        
        # 测试网络错误
        urlopen_mock.side_effect = Exception("Connection error")
        with self.assertRaises(ssl.SSLError):
            manager.reqSignCrt()


class SecurityIntegrationTests(BaseSecurityTestCase):
    """安全功能集成测试"""
    
    @patch.object(security.CertificateManager, "checkCertExists")
    def test_security_initialization(self, check_mock):
        """测试安全系统初始�?""
        manager = security.CertificateManager(self.config, "cluster-01")
        manager.initSecurity()
        self.assertTrue(check_mock.called)
    
    @patch.object(security.CertificateManager, "reqSignCrt")
    @patch.object(security.CertificateManager, "genAgentCrtReq")
    @patch.object(security.CertificateManager, "loadSrvrCrt")
    def test_full_cert_flow(self, load_mock, gen_mock, sign_mock):
        """测试完整证书生命周期"""
        manager = security.CertificateManager(self.config, "cluster-01")
        
        # 模拟证书缺失场景
        with patch("os.path.exists", side_effect=[False, True, False]):
            manager.checkCertExists()
        
        # 验证处理流程
        self.assertTrue(load_mock.called)    # 加载服务器证�?        self.assertTrue(gen_mock.called)     # 生成证书请求
        self.assertTrue(sign_mock.called)    # 请求签名


class HostnameMockTests(BaseSecurityTestCase):
    """测试主机名相关功�?""
    
    def test_hostname_sanitization(self):
        """测试主机名清�?""
        # 创建临时证书管理�?        manager = security.CertificateManager(self.config, "cluster-01")
        
        with patch("cloud_agent.hostname.hostname", return_value="invalid host/name"):
            cleaned_name = manager._clean_hostname()
            self.assertEqual(cleaned_name, "invalid_host_name")
        
        with patch("cloud_agent.hostname.hostname", return_value="valid-hostname"):
            cleaned_name = manager._clean_hostname()
            self.assertEqual(cleaned_name, "valid-hostname")
    
    @patch("cloud_agent.hostname.hostname")
    def test_certificate_subject(self, hostname_mock):
        """测试证书主题生成"""
        hostname_mock.return_value = "app-server-01"
        manager = security.CertificateManager(self.config, "production-cluster")
        
        # 测试主题格式
        self.assertEqual(
            manager._get_certificate_subject(),
            f"/CN=app-server-01/OU=production-cluster"
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
