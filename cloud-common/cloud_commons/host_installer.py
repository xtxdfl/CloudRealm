#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import json
import time
import socket
import subprocess
import tempfile
from typing import Dict, Any, Optional, Tuple

def debug(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

class SubprocessSSHConnection:
    def __init__(self, host: str, port: int, username: str, password: Optional[str] = None,
                 private_key: Optional[str] = None, public_key: Optional[str] = None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.private_key_content = private_key
        self.public_key_content = public_key
        self._key_file = None
        self._connected = False
        self._use_password = False
        
    def connect(self) -> Tuple[bool, str]:
        try:
            print(f"DEBUG: SSH connecting to {self.host}:{self.port} with user {self.username}", file=sys.stderr)
            
            print(f"DEBUG: Checking if port {self.port} is reachable...", file=sys.stderr)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            try:
                result = sock.connect_ex((self.host, self.port))
                sock.close()
                if result == 0:
                    print(f"DEBUG: Port {self.port} is open", file=sys.stderr)
                else:
                    print(f"DEBUG: Port {self.port} is closed (connect_ex returned {result})", file=sys.stderr)
            except Exception as e:
                print(f"DEBUG: Port check failed: {e}", file=sys.stderr)
            
            if self.private_key_content and self.private_key_content.startswith("-----BEGIN"):
                print(f"DEBUG: Has private key, trying private key auth...", file=sys.stderr)
                return self._try_private_key()
            
            if self.public_key_content and self.password:
                print(f"DEBUG: Has public key + password, trying public key auth with password setup...", file=sys.stderr)
                return self._try_public_key_with_password()
            
            if self.password:
                print(f"DEBUG: Has password only, trying password auth...", file=sys.stderr)
                return self._try_password_only()
            
            return False, "No authentication method available (need private_key or public_key+password)"
            
        except Exception as e:
            return False, str(e)
    
    def _try_private_key(self) -> Tuple[bool, str]:
        if not self.private_key_content:
            return False, "No private key"
        
        print(f"DEBUG: === Using private key for SSH ===", file=sys.stderr)
        
        key_content = self.private_key_content
        key_content = key_content.replace('\r\n', '\n').replace('\r', '\n')
        if not key_content.endswith('\n'):
            key_content = key_content + '\n'
        
        temp_dir = tempfile.gettempdir()
        key_file = os.path.join(temp_dir, f"ssh_key_{os.getpid()}.tmp")
        
        with open(key_file, 'w', newline='\n', encoding='utf-8') as f:
            f.write(key_content)
        os.chmod(key_file, 0o600)
        self._key_file = key_file
        
        print(f"DEBUG: Testing private key: {key_file}", file=sys.stderr)
        
        cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10", 
               "-o", "BatchMode=yes", "-i", key_file, 
               "-p", str(self.port), f"{self.username}@{self.host}", "echo", "test"]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        print(f"DEBUG: Private key SSH stdout: {result.stdout}", file=sys.stderr)
        print(f"DEBUG: Private key SSH stderr: {result.stderr}", file=sys.stderr)
        
        if result.returncode == 0:
            self._connected = True
            return True, "Connected with private key"
        
        return False, f"Private key auth failed: {result.stderr}"
    
    def _try_public_key_with_password(self) -> Tuple[bool, str]:
        if not self.public_key_content or not self.password:
            return False, "Need both public_key and password"
        
        print(f"DEBUG: === Public key + password auth ===", file=sys.stderr)
        
        print(f"DEBUG: Step 1 - Connect with password to deploy public key...", file=sys.stderr)
        
        success, msg = self._deploy_public_key_with_password()
        if not success:
            return False, f"Failed to deploy public key: {msg}"
        
        print(f"DEBUG: Step 2 - Test public key auth (passwordless)...", file=sys.stderr)
        
        success, msg = self._test_public_key_auth()
        if success:
            self._connected = True
            return True, "Connected with public key (passwordless)"
        
        return False, f"Public key auth failed after deployment: {msg}"
    
    def _deploy_public_key_with_password(self) -> Tuple[bool, str]:
        if not self.public_key_content or not self.password:
            return False, "Need public_key and password"
        
        public_key_clean = self.public_key_content.strip()
        print(f"DEBUG: Deploying public key to remote server...", file=sys.stderr)
        
        try:
            cmd = ["sshpass", "-p", self.password, "ssh", "-o", "StrictHostKeyChecking=no", 
                   "-o", "ConnectTimeout=10", "-p", str(self.port), 
                   f"{self.username}@{self.host}", 
                   f"mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo '{public_key_clean}' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && echo 'done'"]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            print(f"DEBUG: Deploy stdout: {result.stdout}", file=sys.stderr)
            print(f"DEBUG: Deploy stderr: {result.stderr}", file=sys.stderr)
            
            if result.returncode != 0:
                if "sshpass" in result.stderr.lower() or "sshpass" in result.stdout.lower():
                    print(f"DEBUG: sshpass not found, trying expect...", file=sys.stderr)
                    return self._deploy_public_key_with_expect()
                return False, f"Failed to deploy: {result.stderr}"
            
            return True, "Public key deployed"
        except FileNotFoundError:
            return self._deploy_public_key_with_expect()
    
    def _deploy_public_key_with_expect(self) -> Tuple[bool, str]:
        import tempfile
        try:
            result = subprocess.run(["where", "expect"], capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                return False, "expect not found on Windows. Please install expect or use SSH private key auth instead."
        except Exception:
            pass
        
        expect_script = tempfile.mktemp(suffix='.exp')
        public_key_clean = self.public_key_content.strip()
        
        with open(expect_script, 'w') as f:
            f.write(f'''#!/usr/bin/expect -f
set timeout 30
spawn ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -p {self.port} {self.username}@{self.host}
expect {{
    -re "password:|Password:"
    send "{self.password}\\r"
}}
expect {{
    -re "#|$|\\>"
    send "mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo '{public_key_clean}' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys\\r"
}}
expect {{
    -re "#|$|\\>"
    send "exit\\r"
}}
expect eof
''')
        
        os.chmod(expect_script, 0o700)
        try:
            result = subprocess.run(["expect", expect_script], capture_output=True, text=True, timeout=35)
            os.unlink(expect_script)
            print(f"DEBUG: expect deploy stdout: {result.stdout}", file=sys.stderr)
            print(f"DEBUG: expect deploy stderr: {result.stderr}", file=sys.stderr)
            
            if result.returncode == 0:
                return True, "Public key deployed with expect"
            return False, f"Expect failed: {result.stderr}"
        except Exception as e:
            return False, f"Expect error: {e}"
    
    def _test_public_key_auth(self) -> Tuple[bool, str]:
        if not self.private_key_content:
            return False, "No private key for testing"
        
        key_content = self.private_key_content.replace('\r\n', '\n').replace('\r', '\n')
        if not key_content.endswith('\n'):
            key_content = key_content + '\n'
        
        temp_dir = tempfile.gettempdir()
        key_file = os.path.join(temp_dir, f"ssh_key_{os.getpid()}.tmp")
        
        with open(key_file, 'w', newline='\n', encoding='utf-8') as f:
            f.write(key_content)
        os.chmod(key_file, 0o600)
        self._key_file = key_file
        
        cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10", 
               "-o", "BatchMode=yes", "-i", key_file, 
               "-p", str(self.port), f"{self.username}@{self.host}", "echo", "test"]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        print(f"DEBUG: Test public key stdout: {result.stdout}", file=sys.stderr)
        print(f"DEBUG: Test public key stderr: {result.stderr}", file=sys.stderr)
        
        if result.returncode == 0:
            return True, "Public key auth works"
        
        return False, result.stderr
    
    def _try_password_only(self) -> Tuple[bool, str]:
        if not self.password:
            return False, "No password"
        
        print(f"DEBUG: === Password only auth ===", file=sys.stderr)
        
        # First check if sshpass is available
        try:
            check_result = subprocess.run(["sshpass", "-V"], capture_output=True, text=True, timeout=5)
            if check_result.returncode != 0:
                print(f"DEBUG: sshpass not available, checking for expect...", file=sys.stderr)
                return self._try_password_with_expect()
        except FileNotFoundError:
            print(f"DEBUG: sshpass not found, trying expect...", file=sys.stderr)
            return self._try_password_with_expect()
        
        try:
            cmd = ["sshpass", "-p", self.password, "ssh", "-o", "StrictHostKeyChecking=no", 
                   "-o", "ConnectTimeout=10", "-o", "BatchMode=yes", "-p", str(self.port), 
                   f"{self.username}@{self.host}", "echo", "test"]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            print(f"DEBUG: Password SSH stdout: {result.stdout}", file=sys.stderr)
            print(f"DEBUG: Password SSH stderr: {result.stderr}", file=sys.stderr)
            
            if result.returncode == 0:
                self._connected = True
                self._use_password = True
                return True, "Connected with password"
            
            # Check if it's an authentication error
            if "Permission denied" in result.stderr or "incorrect" in result.stderr.lower():
                return False, "SSH authentication failed: incorrect password"
            
            return False, f"Password auth failed: {result.stderr}"
        except Exception as e:
            return False, f"SSH connection error: {str(e)}"
    
    def _try_password_with_expect(self) -> Tuple[bool, str]:
        import tempfile
        # Check if expect is available first
        try:
            result = subprocess.run(["where", "expect"], capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                return False, "Neither sshpass nor expect is available on Windows. Please install sshpass or use SSH private key auth."
        except Exception:
            pass
        
        expect_script = tempfile.mktemp(suffix='.exp')
        
        with open(expect_script, 'w') as f:
            f.write(f'''#!/usr/bin/expect -f
set timeout 20
spawn ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -o BatchMode=yes -p {self.port} {self.username}@{self.host} echo test
expect {{
    -re "password:|Password:"
    send "{self.password}\\r"
}}
expect {{
    -re "#|$|\\>"
    exit 0
    timeout
    exit 1
}}
expect eof
''')
        
        os.chmod(expect_script, 0o700)
        try:
            result = subprocess.run(["expect", expect_script], capture_output=True, text=True, timeout=25)
            os.unlink(expect_script)
            
            print(f"DEBUG: expect stdout: {result.stdout}", file=sys.stderr)
            print(f"DEBUG: expect stderr: {result.stderr}", file=sys.stderr)
            
            if result.returncode == 0:
                self._connected = True
                self._use_password = True
                return True, "Connected with expect"
            
            return False, f"Expect failed: {result.stderr}"
        except Exception as e:
            return False, f"Expect error: {e}"
    
    def execute(self, command: str) -> Tuple[bool, str, str]:
        if not self._connected:
            return False, "", "Not connected"
        
        if self._use_password:
            cmd = ["sshpass", "-p", self.password, "ssh", "-o", "StrictHostKeyChecking=no", 
                   "-p", str(self.port), f"{self.username}@{self.host}", command]
        elif self._key_file:
            cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", self._key_file, 
                   "-p", str(self.port), f"{self.username}@{self.host}", command]
        else:
            return False, "", "No authentication method"
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return result.returncode == 0, result.stdout, result.stderr
    
    def upload_file(self, local_path: str, remote_path: str) -> Tuple[bool, str]:
        if not self._connected:
            return False, "Not connected"
        
        if self._use_password:
            cmd = ["sshpass", "-p", self.password, "scp", "-o", "StrictHostKeyChecking=no", 
                   "-P", str(self.port), local_path, f"{self.username}@{self.host}:{remote_path}"]
        elif self._key_file:
            cmd = ["scp", "-o", "StrictHostKeyChecking=no", "-i", self._key_file, 
                   "-P", str(self.port), local_path, f"{self.username}@{self.host}:{remote_path}"]
        else:
            return False, "No authentication method"
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            return True, f"Uploaded {local_path} to {remote_path}"
        return False, result.stderr
    
    def close(self):
        if self._key_file and os.path.exists(self._key_file):
            try:
                os.unlink(self._key_file)
            except:
                pass


def install_host(host_name: str, host_ip: str, ssh_port: int, ssh_user: str,
                ssh_password: Optional[str] = None, ssh_private_key: Optional[str] = None,
                ssh_public_key: Optional[str] = None,
                ssh_key_type: str = "rsa", agent_port: int = 8123,
                agent_download_url: str = "http://repo.cloud.com/packages/cloud-agent.rpm",
                local_agent_binary: Optional[str] = None,
                server_url: str = "http://172.25.147.213:8080") -> Dict[str, Any]:
    
    print(f"DEBUG: install_host called with ssh_port={ssh_port}", file=sys.stderr)
    
    result = {
        "success": False,
        "message": "",
        "hostInfo": None
    }
    
    ssh = SubprocessSSHConnection(host_ip, ssh_port, ssh_user, ssh_password, ssh_private_key, ssh_public_key)
    
    success, message = ssh.connect()
    if not success:
        result["message"] = f"SSH connection failed: {message}"
        return result
    
    installer = CloudAgentInstaller(ssh, agent_port)
    installer.agent_download_url = agent_download_url
    installer.server_url = server_url
    
    install_result = installer.install_agent(local_agent_binary)
    
    ssh.close()
    
    if install_result["success"]:
        result["success"] = True
        result["message"] = install_result["message"]
        result["hostInfo"] = install_result["hostInfo"]
        if result["hostInfo"]:
            result["hostInfo"]["hostName"] = host_name
    else:
        result["message"] = install_result["message"]
    
    return result


class CloudAgentInstaller:
    def __init__(self, ssh_connection, agent_port: int = 8123, server_url: str = ""):
        self.ssh = ssh_connection
        self.agent_port = agent_port
        self.agent_download_url = "http://repo.cloud.com/packages/cloud-agent.tar.gz"
        self.server_url = server_url
        
    def install_agent(self, local_binary: Optional[str] = None) -> Dict[str, Any]:
        result = {
            "success": False,
            "message": "",
            "hostInfo": None
        }
        
        print(f"DEBUG: Installing cloud-agent on remote host...", file=sys.stderr)
        
        if local_binary and os.path.exists(local_binary):
            print(f"DEBUG: Using local binary: {local_binary}")
            success, msg = self._install_from_local(local_binary)
        else:
            print(f"DEBUG: No local binary, trying download...")
            success, msg = self._install_from_download()
        
        if not success:
            result["message"] = msg
            return result
        
        if self.server_url:
            print(f"DEBUG: Configuring cloud-agent to connect to {self.server_url}")
            success, msg = self._configure_server_url()
            if not success:
                print(f"WARNING: Failed to configure server URL: {msg}")
        
        host_info = self._collect_host_info()
        result["success"] = True
        result["message"] = "Agent installed successfully"
        result["hostInfo"] = host_info
        
        return result
    
    def _configure_server_url(self) -> Tuple[bool, str]:
        from urllib.parse import urlparse
        parsed = urlparse(self.server_url)
        server_hostname = parsed.hostname or parsed.host
        server_port = parsed.port or (443 if parsed.scheme == "https" else 80)
        
        ini_path = "/usr/local/cloud-agent/conf/cloud-agent.ini"
        
        success, stdout, stderr = self.ssh.execute(f"sed -i 's/^hostname=.*/hostname={server_hostname}/' {ini_path}")
        if not success:
            return False, f"Failed to set hostname: {stderr}"
        
        success, stdout, stderr = self.ssh.execute(f"sed -i 's/^url_port=.*/url_port={server_port}/' {ini_path}")
        if not success:
            return False, f"Failed to set url_port: {stderr}"
        
        print(f"DEBUG: Configured server hostname={server_hostname}, port={server_port}")
        return True, "Server URL configured"
    
    def _install_from_local(self, local_binary: str) -> Tuple[bool, str]:
        print(f"DEBUG: Uploading agent from local: {local_binary}")
        
        success, stdout, stderr = self.ssh.execute("mkdir -p /usr/local/cloud-agent/lib")
        if not success:
            return False, f"Failed to create directory: {stderr}"
        
        remote_path = "/usr/local/cloud-agent/lib/cloud-agent.tar.gz"
        success, msg = self.ssh.upload_file(local_binary, remote_path)
        if not success:
            return False, f"Failed to upload: {msg}"
        
        success, stdout, stderr = self.ssh.execute(f"cd /usr/local/cloud-agent/lib && tar -xzf cloud-agent.tar.gz")
        if not success:
            return False, f"Failed to extract: {stderr}"
        
        success, stdout, stderr = self.ssh.execute("rm -f /usr/local/cloud-agent/lib/cloud-agent.tar.gz")
        
        success, stdout, stderr = self.ssh.execute("mkdir -p /usr/local/cloud-agent/{data,cache,tmp,log,bin,cred,conf}")
        if not success:
            return False, f"Failed to create data directories: {stderr}"
        
        success, stdout, stderr = self.ssh.execute("chmod +x /usr/local/cloud-agent/lib/bin/cloud-agent")
        
        success, stdout, stderr = self.ssh.execute("chmod +x /usr/local/cloud-agent/lib/python/cloud_agent/*.py")
        
        success, stdout, stderr = self.ssh.execute("chmod +x /usr/local/cloud-agent/lib/cloud_commons/*.py")
        
        success, stdout, stderr = self.ssh.execute("ln -sf /usr/local/cloud-agent/lib/bin/cloud-agent /usr/local/cloud-agent/bin/cloud-agent")
        
        success, stdout, stderr = self.ssh.execute("ln -sf /usr/local/cloud-agent/lib/conf/cloud-agent.ini /usr/local/cloud-agent/conf/cloud-agent.ini")
        if not success:
            return False, f"Failed to symlink config: {stderr}"
        
        success, stdout, stderr = self.ssh.execute("ln -sf /usr/local/cloud-agent/lib/conf/cloud-env.sh /usr/local/cloud-agent/cloud-env.sh")
        
        success, stdout, stderr = self.ssh.execute("ln -sf /usr/local/cloud-agent/lib/conf/cloud-sudo.sh /usr/local/cloud-agent/cloud-sudo.sh")
        
        success, stdout, stderr = self.ssh.execute("ln -sf /usr/local/cloud-agent/lib/etc/init.d/cloud-agent /etc/init.d/cloud-agent")
        if success:
            self.ssh.execute("chmod +x /etc/init.d/cloud-agent")
        
        success, stdout, stderr = self.ssh.execute("ln -sf /usr/local/cloud-agent/lib/etc/init/cloud-agent.conf /etc/init/cloud-agent.conf")
        
        print(f"DEBUG: Agent installed and configured successfully")
        return True, "Agent uploaded and extracted"
    
    def _install_from_download(self) -> Tuple[bool, str]:
        return False, "Download not implemented, use local binary"
    
    def _collect_host_info(self) -> Dict[str, Any]:
        host_info = {
            "hostname": "",
            "ip": "",
            "cpuCores": 4,
            "totalMemory": 8,
            "availableMemory": 4,
            "totalDisk": 100,
            "usedDisk": 50,
            "availableDisk": 50,
            "osType": "Linux",
            "osArch": "x86_64",
            "status": "INITIALIZING",
            "agentPort": self.agent_port
        }
        
        success, stdout, stderr = self.ssh.execute("hostname")
        if success:
            host_info["hostname"] = stdout.strip()
        
        success, stdout, stderr = self.ssh.execute("hostname -I | awk '{print $1}'")
        if success:
            host_info["ip"] = stdout.strip()
        
        success, stdout, stderr = self.ssh.execute("nproc")
        if success:
            try:
                host_info["cpuCores"] = int(stdout.strip())
            except:
                pass
        
        success, stdout, stderr = self.ssh.execute("free -m | awk '/Mem:/ {print $2}'")
        if success:
            try:
                host_info["totalMemory"] = int(stdout.strip())
                host_info["availableMemory"] = int(float(host_info["totalMemory"]) * 0.5)
            except:
                pass
        
        success, stdout, stderr = self.ssh.execute("df -BG / | awk 'NR==2 {print $2}' | sed 's/G//'")
        if success:
            try:
                host_info["totalDisk"] = int(stdout.strip())
            except:
                pass
        
        success, stdout, stderr = self.ssh.execute("df -BG / | awk 'NR==2 {print $3}' | sed 's/G//'")
        if success:
            try:
                host_info["usedDisk"] = int(stdout.strip())
                host_info["availableDisk"] = host_info["totalDisk"] - host_info["usedDisk"]
            except:
                pass
        
        return host_info


def main():
    config = None
    
    print(f"DEBUG: sys.stdin.isatty() = {sys.stdin.isatty()}")
    
    if not sys.stdin.isatty():
        try:
            stdin_data = sys.stdin.read()
            print(f"DEBUG: Received stdin data length: {len(stdin_data)}")
            if stdin_data:
                config = json.loads(stdin_data)
                print(f"DEBUG: Received config from stdin")
        except json.JSONDecodeError as e:
            print(f"DEBUG: Failed to parse stdin JSON: {e}")
            config = None
    
    if config is None:
        if len(sys.argv) < 2:
            print(json.dumps({"error": "Usage: python host_installer.py <json_config>"}))
            sys.exit(1)
        try:
            config = json.loads(sys.argv[1])
            print(f"DEBUG: Received config: {config}")
            print(f"DEBUG: ssh_port from config = {config.get('sshPort', 12308)}, type = {type(config.get('sshPort'))}")
        except json.JSONDecodeError:
            config = {
                "hostName": sys.argv[1] if len(sys.argv) > 1 else "",
                "hostIP": sys.argv[2] if len(sys.argv) > 2 else "",
                "sshPort": int(sys.argv[3]) if len(sys.argv) > 3 else 22,
                "sshUser": sys.argv[4] if len(sys.argv) > 4 else "root"
            }
    
    print(f"DEBUG: ssh_port = {config.get('sshPort', 12308)}")
    print(f"DEBUG: Full config keys: {list(config.keys())}")
    
    ssh_password = config.get("sshPassword")
    ssh_private_key = config.get("sshPrivateKey")
    ssh_public_key = config.get("sshPublicKey")
    
    print(f"DEBUG: sshPassword value: {repr(ssh_password[:100]) if ssh_password else None}")
    print(f"DEBUG: sshPrivateKey value: {repr(ssh_private_key[:100]) if ssh_private_key else None}")
    print(f"DEBUG: sshPublicKey value: {repr(ssh_public_key[:100]) if ssh_public_key else None}")
    
    if ssh_password and ssh_password.startswith("-----BEGIN"):
        print(f"DEBUG: sshPassword looks like private key")
        ssh_private_key = ssh_password
        ssh_password = None
    
    if ssh_password and ssh_password.startswith("ssh-"):
        print(f"DEBUG: sshPassword looks like public key")
        ssh_public_key = ssh_password
        ssh_password = None
    
    result = install_host(
        host_name=config.get("hostName", ""),
        host_ip=config.get("hostIP", ""),
        ssh_port=config.get("sshPort", 22),
        ssh_user=config.get("sshUser", "root"),
        ssh_password=ssh_password,
        ssh_private_key=ssh_private_key,
        ssh_public_key=ssh_public_key,
        ssh_key_type=config.get("sshKeyType", "rsa"),
        agent_port=config.get("agentPort", 8123),
        agent_download_url=config.get("agentDownloadURL", "http://repo.cloud.com/packages/cloud-agent.rpm"),
        local_agent_binary=config.get("localAgentBinary"),
        server_url=config.get("serverUrl", "http://172.25.147.213:8080")
    )
    
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
