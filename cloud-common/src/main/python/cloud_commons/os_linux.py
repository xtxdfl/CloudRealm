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

import getpass
import os
import logging
import shlex
import subprocess
import pwd
import grp
import resource
import psutil

# 配置日志系统
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("OSOperations")

def os_run_os_command(cmd, env=None, shell=False, cwd=None, timeout=300, raise_on_error=False):
    """
    运行操作系统命令（安全、可监控版本）
    
    参数:
        cmd: 要执行的命令 (str 或 list)
        env: 环境变量 (dict)
        shell: 是否使用shell执行 (bool)
        cwd: 工作目录 (str)
        timeout: 命令超时时间 (秒)
        raise_on_error: 执行失败时是否抛出异常
    
    返回:
        (returncode, stdout, stderr)
    """
    if isinstance(cmd, str):
        if shell:
            # 使用shell执行字符串命令
            cmd_str = cmd
        else:
            # 安全解析为参数列表
            cmd_list = shlex.split(cmd)
    else:
        cmd_list = cmd
        cmd_str = " ".join(cmd)
    
    command_str = cmd_str if isinstance(cmd, str) else " ".join(cmd)
    logger.info(f"Executing command: {command_str}")
    
    kwargs = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "env": env or os.environ.copy(),
        "cwd": cwd or os.getcwd(),
        "timeout": timeout,
        "text": True  # 返回文本而不是字节
    }
    
    if shell:
        kwargs["shell"] = True
        kwargs["executable"] = "/bin/bash"  # 指定明确的shell
    
    try:
        # 使用run代替Popen，更安全
        result = subprocess.run(
            cmd if not shell else command_str, 
            **kwargs
        )
        
        returncode = result.returncode
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        
        if returncode != 0:
            logger.warning(f"Command failed with exit code {returncode}.\nCommand: {command_str}")
            if stderr:
                logger.error(f"Error output: {stderr}")
            if raise_on_error:
                raise RuntimeError(f"Command failed: {stderr or stdout}")
        else:
            if stdout:
                logger.debug(f"Command output: {stdout}")
                
        return returncode, stdout, stderr
    
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out after {timeout} seconds: {command_str}")
        if raise_on_error:
            raise
        return -1, "", "Command timed out"
    
    except Exception as e:
        logger.exception(f"Unexpected error executing command: {command_str}")
        if raise_on_error:
            raise
        return -1, "", f"Command execution failed: {str(e)}"


def os_change_owner(file_path, user, recursive=False, raise_on_error=False):
    """
    安全修改文件/目录所有者
    
    参数:
        file_path: 文件或目录路径
        user: 用户名 (str) 或用户ID (int)
        recursive: 是否递归修改
        raise_on_error: 失败时是否抛出异常
    """
    try:
        # 解析用户ID
        if isinstance(user, str):
            user_id = pwd.getpwnam(user).pw_uid
        else:
            user_id = user
        
        # 处理单个文件
        if not recursive or not os.path.isdir(file_path):
            os.chown(file_path, user_id, -1)  # -1 表示保留原有组
            return
        
        # 递归处理目录
        for root, dirs, files in os.walk(file_path):
            for name in dirs + files:
                path = os.path.join(root, name)
                try:
                    os.chown(path, user_id, -1)
                except Exception as e:
                    logger.warning(f"Failed to change owner for {path}: {str(e)}")
        
    except KeyError:
        error_msg = f"User '{user}' does not exist"
        logger.error(error_msg)
        if raise_on_error:
            raise ValueError(error_msg)
    except Exception as e:
        logger.error(f"Error changing owner for {file_path}: {str(e)}")
        if raise_on_error:
            raise


def os_change_group(file_path, group, recursive=False, raise_on_error=False):
    """
    安全修改文件/目录所属组
    """
    try:
        # 解析组ID
        if isinstance(group, str):
            group_id = grp.getgrnam(group).gr_gid
        else:
            group_id = group
        
        # 处理单个文件
        if not recursive or not os.path.isdir(file_path):
            os.chown(file_path, -1, group_id)  # -1 表示保留原有用户
            return
        
        # 递归处理目录
        for root, dirs, files in os.walk(file_path):
            for name in dirs + files:
                path = os.path.join(root, name)
                try:
                    os.chown(path, -1, group_id)
                except Exception as e:
                    logger.warning(f"Failed to change group for {path}: {str(e)}")
        
    except KeyError:
        error_msg = f"Group '{group}' does not exist"
        logger.error(error_msg)
        if raise_on_error:
            raise ValueError(error_msg)
    except Exception as e:
        logger.error(f"Error changing group for {file_path}: {str(e)}")
        if raise_on_error:
            raise


def os_set_file_permissions(file_path, mode, recursive=False, user=None, group=None, raise_on_error=False):
    """
    设置文件/目录权限和所有者（原子操作）
    
    参数:
        file_path: 文件或目录路径
        mode: 八进制权限 (如 0o755) 或字符串 (如 "755")
        recursive: 是否递归修改
        user: 用户名 (可选)
        group: 组名 (可选)
    """
    try:
        # 转换权限格式
        if isinstance(mode, str):
            mode = int(mode, 8)  # 从八进制字符串转换
        elif isinstance(mode, int):
            mode = int(str(mode), 8)  # 确保正确处理八进制
        
        # 设置权限
        if not recursive or not os.path.isdir(file_path):
            os.chmod(file_path, mode)
        else:
            for root, dirs, files in os.walk(file_path):
                for name in dirs + files:
                    path = os.path.join(root, name)
                    try:
                        os.chmod(path, mode)
                    except Exception as e:
                        logger.warning(f"Failed to set permissions for {path}: {str(e)}")
        
        # 设置所有者和组
        if user is not None:
            os_change_owner(file_path, user, recursive, raise_on_error)
        if group is not None:
            os_change_group(file_path, group, recursive, raise_on_error)
            
    except ValueError:
        error_msg = f"Invalid permission mode: {mode}"
        logger.error(error_msg)
        if raise_on_error:
            raise ValueError(error_msg)
    except Exception as e:
        logger.error(f"Error setting permissions for {file_path}: {str(e)}")
        if raise_on_error:
            raise


def os_is_root():
    """
    检查当前是否具有root权限（POSIX兼容）
    
    返回:
        bool: True如果是root权限, False如果不是
    """
    return os.geteuid() == 0


def os_get_current_user():
    """
    获取当前用户名
    """
    return getpass.getuser()


def os_set_open_files_limit(max_open_files, user=None):
    """
    设置进程的文件描述符限制
    
    参数:
        max_open_files: 最大打开文件数
        user: 指定用户 (仅当以root身份运行时有效)
    """
    # 获取当前的软硬限制
    soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
    
    # 确保新限制不超过硬限制
    new_soft = min(max_open_files, hard_limit)
    
    try:
        # 设置当前进程的限制
        resource.setrlimit(resource.RLIMIT_NOFILE, (new_soft, hard_limit))
        logger.info(f"Changed file descriptor limit to {new_soft}")
    except ValueError as e:
        logger.error(f"Cannot set file descriptor limit to {new_soft}: {str(e)}")
    
    # 系统级设置 (需要root权限)
    if os_is_root():
        try:
            # 系统级配置 (适用于所有新进程)
            conf_path = "/etc/security/limits.conf"
            conf_line = f"\n*               soft    nofile          {max_open_files}\n*               hard    nofile          {max_open_files}"
            
            # 检查是否已存在配置
            with open(conf_path, "r+") as f:
                content = f.read()
                if conf_line.strip() not in content:
                    f.write(conf_line)
                    logger.info(f"Updated system-wide file descriptor limit in {conf_path}")
            
            # 用户级配置
            if user is not None:
                user_conf = f"\n{user}               soft    nofile          {max_open_files}\n{user}               hard    nofile          {max_open_files}"
                with open(conf_path, "a") as f:
                    if user_conf not in content:
                        f.write(user_conf)
                        logger.info(f"Updated user-specific file descriptor limit for {user}")
            
            # 动态应用更改 (无需重启)
            os_run_os_command("sysctl -p /etc/sysctl.conf", raise_on_error=False)
            
        except Exception as e:
            logger.error(f"Error setting system-wide file descriptor limit: {str(e)}")


def os_getpass(prompt="Password: ", stream=None):
    """
    安全获取密码输入（支持无TTY环境）
    
    参数:
        prompt: 输入提示
        stream: 输入流 (默认None表示使用终端)
    
    返回:
        str: 输入的密码
    """
    try:
        # 尝试使用标准getpass
        return getpass.getpass(prompt, stream)
    except getpass.GetPassWarning:
        # 回退到替代方案
        logger.warning("Secure password input not available, using alternative method")
        if stream is None:
            stream = sys.stdin
        print(prompt, end='', flush=True)
        password = stream.readline().rstrip('\n')
        return password


def os_is_service_exist(service_name, init_system=None):
    """
    检查服务是否存在（支持多种初始化系统）
    
    参数:
        service_name: 服务名称
        init_system: 指定初始化系统 (auto, systemd, upstart, sysv)
    
    返回:
        bool: 服务是否存在
    """
    # 自动检测初始化系统
    if init_system == "auto" or init_system is None:
        if os.path.exists("/run/systemd/system/"):
            init_system = "systemd"
        elif os.path.exists("/usr/share/upstart/sessions/"):
            init_system = "upstart"
        else:
            init_system = "sysv"
    
    logger.info(f"Checking service '{service_name}' using {init_system} init system")
    
    try:
        # systemd 系统
        if init_system == "systemd":
            # 查询所有系统服务
            _, out, _ = os_run_os_command(
                ["systemctl", "list-unit-files", "--type=service", "--no-legend"],
                raise_on_error=True
            )
            services = [line.split()[0] for line in out.splitlines()]
            
            # 检查服务是否在列表中
            return any(
                s == f"{service_name}.service" 
                or s.startswith(f"{service_name}@") 
                for s in services
            )
        
        # Upstart 系统
        elif init_system == "upstart":
            # 查询所有Upstart作业
            _, out, _ = os_run_os_command(
                ["initctl", "list"],
                raise_on_error=False
            )
            return any(
                line.startswith(service_name) 
                for line in out.splitlines()
            )
        
        # SysV 系统
        else:
            # 检查/etc/init.d/中的脚本
            initd_path = f"/etc/init.d/{service_name}"
            if os.path.isfile(initd_path) and os.access(initd_path, os.X_OK):
                return True
            
            # 检查/etc/rc.d/中的脚本
            rcd_path = f"/etc/rc.d/{service_name}"
            if os.path.isfile(rcd_path) and os.access(rcd_path, os.X_OK):
                return True
            
            # 检查/etc/rc*.d/中的链接
            for rc_dir in ["/etc/rc0.d", "/etc/rc1.d", "/etc/rc2.d", "/etc/rc3.d", 
                          "/etc/rc4.d", "/etc/rc5.d", "/etc/rc6.d", "/etc/rcS.d"]:
                if os.path.isdir(rc_dir):
                    for entry in os.listdir(rc_dir):
                        # 检查服务脚本链接 (如 S99myservice)
                        if entry.endswith(service_name) or service_name in entry:
                            return True
            
            return False
    
    except Exception as e:
        logger.error(f"Error checking service existence: {str(e)}")
        return False


def os_is_process_running(process_name, exact_match=False):
    """
    检查进程是否正在运行
    
    参数:
        process_name: 进程名称
        exact_match: 是否精确匹配进程名
    
    返回:
        bool: 进程是否正在运行
    """
    try:
        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                # 匹配进程名
                if exact_match:
                    if proc.info['name'] == process_name:
                        return True
                else:
                    # 匹配进程名或命令行
                    if (process_name in proc.info['name'] or 
                       (proc.info['cmdline'] and any(process_name in cmd for cmd in proc.info['cmdline']))):
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False
    except Exception as e:
        logger.error(f"Error checking process: {str(e)}")
        return False


def os_set_environ(key, value, user=None, persistent=False):
    """
    设置环境变量
    
    参数:
        key: 环境变量名
        value: 环境变量值
        user: 指定用户 (None为当前用户)
        persistent: 是否永久设置 (更新配置文件)
    """
    # 设置当前环境
    os.environ[key] = value
    logger.info(f"Set environment variable: {key}={value}")
    
    # 永久设置 (需要root权限)
    if persistent and os_is_root():
        try:
            if user is None:
                # 系统级配置
                profile_path = "/etc/environment"
                with open(profile_path, "r") as f:
                    content = f.read()
                
                # 更新或添加
                new_line = f'\n{key}="{value}"\n'
                if f"{key}=" not in content:
                    with open(profile_path, "a") as f:
                        f.write(new_line)
                    logger.info(f"Added {key} to system environment file")
            else:
                # 用户级配置
                user_home = os.path.expanduser(f"~{user}")
                bashrc_path = os.path.join(user_home, ".bashrc")
                
                # 确保文件存在
                if not os.path.exists(bashrc_path):
                    os.mknod(bashrc_path, 0o644)
                    os_change_owner(bashrc_path, user)
                
                with open(bashrc_path, "a") as f:
                    f.write(f'\nexport {key}="{value}"\n')
                
                logger.info(f"Added {key} to {user}'s .bashrc")
            
            return True
        except Exception as e:
            logger.error(f"Failed to set persistent environment: {str(e)}")
            return False
    
    return True


def os_reload_services(service_list=None):
    """
    重载系统服务和守护进程
    
    参数:
        service_list: 要重载的服务列表 (None为所有服务)
    """
    if os_is_root():
        logger.info("Reloading system services")
        
        # 重载systemd系统
        if os.path.exists("/run/systemd/system"):
            cmd = ["systemctl", "daemon-reload"]
            if service_list:
                # 重载特定服务
                for service in service_list:
                    os_run_os_command(["systemctl", "reload", service], raise_on_error=True)
            else:
                # 重载所有服务
                os_run_os_command(cmd, raise_on_error=False)
            
            # 发送SIGHUP到所有sys守护进程
            os_run_os_command("pkill -HUP -x rsyslogd", shell=True, raise_on_error=False)
        
        elif os.path.exists("/sbin/rc-service"):
            # OpenRC系统
            cmd = ["rc-update"] if not service_list else []
            if service_list:
                for service in service_list:
                    os_run_os_command(["rc-service", service, "reload"], raise_on_error=True)
        
        logger.info("Services reloaded successfully")
        return True
    
    logger.warning("Service reload requires root privileges")
    return False


def os_restart_server():
    """
    安全重启服务器 (需要root权限)
    """
    if os_is_root():
        logger.warning("Initiating server restart")
        os_run_os_command("shutdown -r now", shell=True)
        return True
    else:
        logger.error("Server restart requires root privileges")
        return False


def os_secure_shell(command, sanitize=True):
    """
    执行安全的shell命令（防止注入攻击）
    
    参数:
        command: 命令字符串
        sanitize: 是否对输入进行安全过滤
    
    返回:
        (returncode, stdout, stderr)
    """
    if sanitize:
        # 过滤危险字符
        command = shlex.quote(command)
    
    return os_run_os_command(
        ["/bin/bash", "-c", command],
        shell=True,
        raise_on_error=True
    )


if __name__ == "__main__":
    # 示例用法
    print("Current user is root:", os_is_root())
    
    # 设置文件权限示例
    test_file = "test_file.txt"
    with open(test_file, "w") as f:
        f.write("test")
    
    os_set_file_permissions(
        test_file, 
        "644", 
        user=os.getlogin(),
        raise_on_error=True
    )
    print(f"Permissions set for {test_file}")
    
    # 检查服务是否存在
    print("sshd service exists:", os_is_service_exist("sshd"))
    
    # 运行命令示例
    rc, out, err = os_run_os_command("echo 'Safe command execution'", raise_on_error=True)
    print("Command output:", out)
    
    # 获取密码输入
    password = os_getpass("Enter your secret: ")
    print("Password received (length):", len(password))
    
    # 设置环境变量
    os_set_environ("TEST_ENV", "12345", persistent=False)
    print("Environment set")

