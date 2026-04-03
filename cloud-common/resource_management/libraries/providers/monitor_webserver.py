#!/usr/bin/env python3
"""
Enterprise-Grade Web Server Management with:
- Multi-platform support
- Security hardening
- Health monitoring
- Idempotent operations
- Cloud integration
"""

import os
import re
import time
import logging
import platform
import subprocess
from datetime import datetime

from resource_management import *
from resource_management.core.sudo import is_sudo
from resource_management.core import shell
from cloud_commons.os_check import OSCheck
from cloud_commons.security import SecurityContext

# Configure logging
logger = logging.getLogger("resource_management.monitor.webserver")
logger.setLevel(logging.INFO)

class EnterpriseWebserverProvider(Provider):
    """
    Production-Grade Web Server Management with:
    - Cross-platform configuration
    - Security compliance scanning
    - Performance tuning
    - Graceful failure recovery
    - Audit logging
    """
    
    SYSLOG_TAGS = ("apache", "httpd", "nginx")
    CONFIG_FILE_INTEGRITY_CHECKSUM = {}
    
    def __init__(self, resource):
        super().__init__(resource)
        self.service_context = self.get_service_params()
        self.security_context = SecurityContext.for_service("webserver")
        self.lock_file = f"/var/lock/websrv_{resource.name}.lock"
        
    def action_start(self):
        """Start web server with enterprise safeguards"""
        try:
            # Prepare environment
            self.ensure_operational_requirements()
            self.enable_keep_alive()
            self.apply_security_hardening()
            
            # Execute start command
            return self.execute_service_control("start")
        except Exception as e:
            self.handle_failure("start", e)
    
    def action_stop(self):
        """Stop web server gracefully"""
        try:
            # Pre-stop operations
            self.disable_maintenance_mode()
            
            # Execute stop command
            return self.execute_service_control("stop")
        except Exception as e:
            self.handle_failure("stop", e)
    
    def action_restart(self):
        """Restart web server with zero-downtime"""
        try:
            # Verify if service is running before restart
            if not self.is_service_running():
                logger.warning("Service not running - performing start instead of restart")
                return self.action_start()
            
            # Enterprise restart strategy
            return self.execute_rolling_restart()
        except Exception as e:
            self.handle_failure("restart", e)
    
    def action_force_reload(self):
        """Reload configuration without interruption"""
        try:
            self.verify_config_integrity()
            self.backup_configuration()
            return self.execute_service_control("reload")
        except Exception as e:
            self.recover_from_config_error(e)
    
    def execute_service_control(self, action):
        """Centralized service control with enhanced features"""
        command = (self.service_context["control_path"], action)
        
        # Execute with monitoring wrapper
        result = Execute(
            command,
            sudo=True,
            logoutput=True,
            environment=self.get_execution_environment(),
            timeout=300,
            on_timeout=self.handle_timeout,
            on_fail=self.handle_command_failure
        )
        
        # Verify successful action
        if action in ("start", "restart"):
            self.verify_service_running(30)
        
        logger.info(f"Service {action} completed successfully")
        return result
    
    def get_service_params(self):
        """Detect service environment with cloud awareness"""
        os_type = OSCheck.get_os_type()
        os_version = OSCheck.get_os_version()
        
        # Cloud container adjustments
        if OSCheck.is_container_env():
            return self.get_container_service_params()
        
        # Platform-specific settings
        service_map = {
            "suse": self.get_suse_params,
            "ubuntu": self.get_ubuntu_params,
            "debian": self.get_ubuntu_params,
            "redhat": self.get_redhat_params,
            "centos": self.get_redhat_params,
            "amazon": self.get_amazon_params,
            "alpine": self.get_alpine_params
        }
        
        return service_map.get(os_type, self.get_default_params)()
    
    def get_suse_params(self):
        """SLES/openSUSE configuration"""
        return {
            "service_name": "apache2",
            "control_path": "/usr/sbin/rcapache2",
            "config_dir": "/etc/apache2",
            "log_dir": "/var/log/apache2",
            "binary_path": "/usr/sbin/apache2",
            "init_d_path": "/etc/init.d/apache2"
        }
    
    def get_ubuntu_params(self):
        """Ubuntu/Debian configuration"""
        return {
            "service_name": "apache2",
            "control_path": "/usr/sbin/service apache2",
            "config_dir": "/etc/apache2",
            "log_dir": "/var/log/apache2",
            "binary_path": "/usr/sbin/apache2",
            "init_d_path": "/etc/init.d/apache2"
        }
    
    def get_redhat_params(self):
        """RHEL/CentOS configuration"""
        return {
            "service_name": "httpd",
            "control_path": "/usr/sbin/apachectl",
            "config_dir": "/etc/httpd/conf",
            "log_dir": "/var/log/httpd",
            "binary_path": "/usr/sbin/httpd",
            "init_d_path": "/etc/init.d/httpd"
        }
    
    def get_amazon_params(self):
        """Amazon Linux configuration"""
        params = self.get_redhat_params()
        params["config_dir"] = "/etc/apache2"
        return params
    
    def get_alpine_params(self):
        """Alpine Linux configuration"""
        return {
            "service_name": "apache2",
            "control_path": "/usr/sbin/apachectl",
            "config_dir": "/etc/apache2",
            "log_dir": "/var/log/apache2",
            "binary_path": "/usr/sbin/apache2",
            "init_d_path": "/etc/init.d/apache2"
        }
    
    def get_default_params(self):
        """Fallback configuration for unknown platforms"""
        return {
            "service_name": "httpd",
            "control_path": "/usr/local/sbin/apachectl",
            "config_dir": "/usr/local/etc/apache2",
            "log_dir": "/var/log",
            "binary_path": "/usr/local/sbin/httpd",
            "init_d_path": "/etc/init.d/httpd"
        }
    
    def get_container_service_params(self):
        """Container-optimized configuration"""
        # Auto-detection for container environments
        if os.path.exists("/usr/sbin/nginx"):
            return {
                "service_name": "nginx",
                "control_path": "/usr/sbin/nginx",
                "config_dir": "/etc/nginx",
                "log_dir": "/var/log/nginx",
                "binary_path": "/usr/sbin/nginx",
                "init_d_path": None
            }
        else:
            return self.get_default_params()
    
    def enable_keep_alive(self):
        """Idempotent configuration for KeepAlive with security validation"""
        config_file = os.path.join(self.service_context["config_dir"], "httpd.conf")
        keep_alive_key = "KeepAlive"
        target_value = "On"
        
        # Check if already configured
        if self.config_value_set(config_file, keep_alive_key, target_value):
            logger.debug("KeepAlive already enabled")
            return
            
        # Backup before modification
        self.backup_config_file(config_file)
        
        # Update or add configuration
        sed_command = [
            "sed",
            "-i",
            f'/^{keep_alive_key} /d; $ a\{keep_alive_key} {target_value}',
            config_file
        ]
        
        Execute(
            sed_command,
            sudo=True,
            logoutput=False,
            tries=3,
            try_sleep=2
        )
        
        logger.info(f"Configured {keep_alive_key} in {config_file}")
        self.validate_config_syntax()
    
    def config_value_set(self, file_path, key, value):
        """Check if configuration key is set to specific value"""
        if not os.path.exists(file_path):
            return False
            
        cmd = f"grep -E '^\\s*{key}\\s+{value}\\s*$' {file_path}"
        return shell.call(cmd, sudo=True)[0] == 0
    
    def apply_security_hardening(self):
        """Apply CIS security benchmarks to web server"""
        if not getattr(self.resource, "security_hardening", True):
            logger.info("Security hardening disabled")
            return
            
        config_file = os.path.join(self.service_context["config_dir"], "httpd.conf")
        
        # Apply security settings (CIS benchmarks)
        security_settings = [
            ("ServerTokens", "Prod"),
            ("ServerSignature", "Off"),
            ("TraceEnable", "Off"),
            ("Header always append X-Frame-Options", "SAMEORIGIN"),
            ("Header set X-Content-Type-Options", "nosniff"),
            ("Header set X-XSS-Protection", '"1; mode=block"')
        ]
        
        for setting, value in security_settings:
            self.set_config_value(config_file, setting, value)
        
        # Disable unneeded modules
        if self.service_context["service_name"] == "apache2":
            self.disable_modules(["autoindex", "status", "userdir"])
        
        logger.debug("Security hardening applied")
        self.security_context.audit_configuration(config_file)
    
    def set_config_value(self, config_file, key, value):
        """Safely set configuration value"""
        if self.config_value_set(config_file, key, value):
            return
            
        self.backup_config_file(config_file)
        
        # Add or update configuration line
        Execute(
            f"echo '{key} {value}' | sudo tee -a {config_file} >/dev/null && "
            f"sed -i '/^{key}\\s/{{h;s|=.*|={value}|}};$ {{x;/^$/{{s//{key}={value}/;H}};x}}' {config_file}",
            tries=2,
            sudo=True
        )
        logger.debug(f"Configured {key} = {value}")
    
    def disable_modules(self, modules):
        """Disable given modules in Apache"""
        if self.service_context["service_name"] not in ["apache2", "httpd"]:
            return
            
        control_path = self.service_context["control_path"]
        
        for module in modules:
            status = shell.call(f"{control_path} -M | grep {module}", sudo=True)
            if status[0] == 0:
                Execute(
                    f"{control_path} -d {module}",
                    sudo=True,
                    logoutput=True,
                    ignore_failures=True
                )
                logger.info(f"Module {module} disabled")
    
    def execute_rolling_restart(self):
        """Enterprise restart with zero downtime"""
        # Graceful restart capability
        if "graceful" in self.supported_service_controls():
            logger.info("Initiating graceful restart")
            return self.execute_service_control("graceful")
        
        # Graceful stop strategy
        worker_pids = self.get_worker_pids()
        self.start_new_worker_process()
        self.gracefully_terminate_old_workers(worker_pids)
        self.cleanup_orphaned_workers()
        logger.info("Rolling restart completed")
    
    def get_worker_pids(self):
        """Get current worker process IDs"""
        bin_path = self.service_context["binary_path"]
        command = f"pgrep -P $(pgrep -f '{bin_path}' | head -1)"
        _, out, _ = shell.checked_call(command, sudo=True)
        return out.strip().split()
    
    def start_new_worker_process(self):
        """Start new worker instances"""
        Execute(
            f"{self.service_context['binary_path']} -k start",
            sudo=True,
            logoutput=False
        )
    
    def gracefully_terminate_old_workers(self, pids):
        """Send SIGTERM to old workers"""
        for pid in pids:
            try:
                Execute(f"kill -TERM {pid}", sudo=True, timeout=30)
                wait_for(f"PID {pid} to terminate", timeout=60)
            except:
                logger.warning(f"Failed to terminate worker {pid}")
                Execute(f"kill -9 {pid}", sudo=True)
    
    def supported_service_controls(self):
        """Detect available service controls"""
        control_path = self.service_context["control_path"]
        result = shell.call(f"{control_path} -h", sudo=True, quiet=True)
        
        return [
            action for action in ["start", "stop", "restart", "graceful", "reload"]
            if action in result[1]
        ]
    
    def is_service_running(self):
        """Check service status using multiple methods"""
        # Check PID file
        pid_files = self.find_pid_files()
        if any(os.path.exists(pf) for pf in pid_files):
            return True
            
        # Check running processes
        service_name = self.service_context["service_name"]
        _, out, _ = shell.call(f"pgrep -f '{service_name}'", sudo=True, quiet=True)
        if out.strip():
            return True
            
        # Check socket binding
        port_status = shell.call("netstat -tuln | grep ':80\\|:443'", sudo=True)
        return port_status[0] == 0
    
    def find_pid_files(self):
        """Locate possible PID files"""
        possible_locations = [
            "/var/run",
            "/run",
            self.service_context["log_dir"],
            os.path.dirname(self.service_context["binary_path"])
        ]
        
        pid_files = []
        for location in possible_locations:
            if os.path.exists(location):
                pid_files.extend([
                    os.path.join(location, f"{self.service_context['service_name']}.pid"),
                    os.path.join(location, f"{self.service_context['service_name']}.httpd.pid")
                ])
        
        return pid_files
    
    def verify_service_running(self, timeout=30):
        """Ensure service is operational after start"""
        start = time.time()
        while time.time() - start < timeout:
            if self.is_service_running():
                logger.info("Service verified as running")
                return
            time.sleep(2)
        
        # Diagnostics on failure
        self.collect_diagnostics()
        raise Fail("Service failed to start")
    
    def collect_diagnostics(self):
        """Gather troubleshooting data"""
        logs = [
            os.path.join(self.service_context["log_dir"], "error_log"),
            "/var/log/syslog",
            "/var/log/messages",
            "/var/log/dmesg"
        ]
        
        diag_dir = getattr(self.resource, "diag_dir", "/tmp/service-diag")
        os.makedirs(diag_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for log in logs:
            if os.path.exists(log):
                Execute(
                    f"tail -n 1000 {log} > {diag_dir}/service_{timestamp}.log",
                    sudo=True
                )
        
        # Capture configuration state
        self.backup_configuration(diag_dir)
    
    def backup_configuration(self, output_dir=None):
        """Backup all configuration files"""
        if output_dir is None:
            backup_base = getattr(self.resource, "backup_dir", "/etc/config-backups")
            backup_dir = os.path.join(backup_base, time.strftime("%Y%m%d-%H%M%S"))
        else:
            backup_dir = output_dir
        
        os.makedirs(backup_dir, exist_ok=True, mode=0o755)
        
        config_dir = self.service_context["config_dir"]
        Execute(
            f"cp -a {config_dir} {backup_dir}",
            sudo=True
        )
        logger.info(f"Configuration backed up to {backup_dir}")
        self.CONFIG_FILE_INTEGRITY_CHECKSUM = self.calculate_config_checksums(config_dir)
    
    def calculate_config_checksums(self, config_dir):
        """Create checksums for configuration verification"""
        result = {}
        for root, _, files in os.walk(config_dir):
            for file in files:
                path = os.path.join(root, file)
                result[path] = self.file_checksum(path)
        return result
    
    def file_checksum(self, path):
        """Calculate file SHA256 checksum"""
        try:
            import hashlib
            sha256_hash = hashlib.sha256()
            with open(path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except:
            return "checksum_failed"
    
    def verify_config_integrity(self):
        """Verify configuration integrity after modification"""
        config_dir = self.service_context["config_dir"]
        current_checksums = self.calculate_config_checksums(config_dir)
        
        for path, expected_checksum in self.CONFIG_FILE_INTEGRITY_CHECKSUM.items():
            new_checksum = current_checksums.get(path, "file_not_found")
            if new_checksum != expected_checksum:
                logger.warning(f"Configuration checksum changed for {path}")
                self.security_context.alert(
                    "CONFIG_INTEGRITY",
                    f"File modified: {path}",
                    severity="medium"
                )
    
    def ensure_operational_requirements(self):
        """Ensure all prerequisites are met before service start"""
        # Port availability check
        if not self.ports_available([80, 443]):
            raise Fail("HTTP/HTTPS ports already in use")
        
        # Disk space verification
        if self.get_disk_usage("/") > 90:
            raise Fail("Root filesystem full, cannot start service")
        
        # Required kernel parameters
        self.verify_kernel_settings()
    
    def ports_available(self, ports):
        """Check if ports are available to bind"""
        for port in ports:
            if is_port_listening("0.0.0.0", port) or is_port_listening("::", port):
                logger.error(f"Port {port} is already in use")
                return False
        return True
    
    def verify_kernel_settings(self):
        """Validate required kernel settings for web server"""
        required_settings = {
            "net.core.somaxconn": 4096,
            "net.ipv4.tcp_tw_reuse": 1,
            "net.ipv4.ip_local_port_range": "1024 65000"
        }
        
        for setting, required_value in required_settings.items():
            current = shell.get_kernel_param(setting)
            if str(current) != str(required_value):
                logger.warning(f"Require kernel param {setting}={required_value} (current: {current})")
    
    def get_disk_usage(self, path):
        """Get disk usage percentage for filesystem"""
        st = os.statvfs(path)
        used = (st.f_blocks - st.f_bavail) * st.f_frsize
        total = st.f_blocks * st.f_frsize
        return (used / total) * 100
    
    def handle_failure(self, action, exception):
        """Comprehensive failure handling"""
        logger.critical(f"Failed to {action} service: {exception}")
        self.collect_diagnostics()
        self.notify_monitoring_system(action, str(exception))
        
        if is_sudo():
            self.enable_maintenance_mode()
        
        raise Fail(f"Service {action} failed: {str(exception)}")
    
    def notify_monitoring_system(self, event, details):
        """Send alert to monitoring infrastructure"""
        # Normally integrate with Nagios, Zabbix, Datadog, etc.
        logger.error(f"MONITORING_ALERT: service_{event}_failed - {details}")
    
    def recover_from_config_error(self, exception):
        """Recovery procedure for configuration errors"""
        logger.error("Configuration error detected, attempting recovery")
        self.restore_configuration()
        
        if self.is_service_running():
            Execute(
                f"{self.service_context['control_path']} reload",
                sudo=True
            )
        else:
            self.action_start()
        
        self.security_context.alert(
            "CONFIG_ERROR",
            f"Recovered from configuration error: {exception}",
            severity="high"
        )
    
    def restore_configuration(self):
        """Restore from last known good configuration"""
        backups = sorted(os.listdir(backup_base))
        for backup in reversed(backups):
            backup_dir = os.path.join(backup_base, backup)
            if os.path.isdir(backup_dir):
                Execute(
                    f"cp -a {backup_dir}/* {self.service_context['config_dir']}",
                    sudo=True
                )
                logger.info(f"Restored configuration from {backup}")
                return
        logger.critical("No valid configurations to restore")
    
    def enable_maintenance_mode(self):
        """Place server in maintenance mode"""
        index_path = "/var/www/html/maintenance.html"
        Execute(
            f"echo '<html><body>Maintenance in progress</body></html>' > {index_path}",
            sudo=True
        )
        self.notify_load_balancer("drain")
    
    def disable_maintenance_mode(self):
        """Disable maintenance mode"""
        index_path = "/path/to/original/index.html"
        Execute(
            f"if [ -d {index_path} ]; then mv {index_path} /var/www/html/index.html; fi",
            sudo=True
        )
        self.notify_load_balancer("enable")
    
    def notify_load_balancer(self, action):
        """Notify load balancer of state changes"""
        if hasattr(self.resource, "lb_endpoints"):
            for endpoint in self.resource.lb_endpoints:
                logger.info(f"Notifying LB {endpoint}: {action}")
                # Call LB API in real implementation
    
    def get_execution_environment(self):
        """Prepare secure execution environment"""
        env = os.environ.copy()
        env.update({
            "LANG": "C",
            "LC_ALL": "C",
            "PATH": "/sbin:/bin:/usr/sbin:/usr/bin",
        })
        return self.security_context.sanitize_environment(env)
    
    def handle_command_failure(self, result):
        """Custom command failure handling"""
        if result.retcode == 1 and "already running" in result.stderr:
            logger.info("Service already running - ignoring start request")
            return True  # Mark as handled to avoid exception
        return False
    
    def handle_timeout(self):
        """Handle service control timeouts"""
        self.collect_diagnostics()
        self.notify_monitoring_system("timeout", "Service control operation timed out")
        return True  # Continue execution
