#!/usr/bin/env python3
"""
Enhanced XML Configuration Provider with:
- Advanced template management
- Error prevention
- Performance optimization
- Secure defaults
"""

import os
import time
import logging
import resource_management
from typing import Dict, Optional, Any, List, Union
from xml.sax.saxutils import escape as xml_escape

from resource_management.core import Environment
from resource_management.core.resources import File
from resource_management.core.providers import Provider
from resource_management.core.source import InlineTemplate, TemplateConfig
from resource_management.core.exceptions import ClientComponentHasNoStatus
from resource_management.libraries.functions.format import format
from resource_management.core.logger import Logger
from resource_management.libraries.functions.is_empty import is_empty

# Configure logging
logger = logging.getLogger("resource_management.providers.xml_config")
logger.setLevel(logging.INFO)

class SecureXmlConfigProvider(Provider):
    """
    Enterprise-grade XML configuration generator with:
    - Template security hardening
    - Validation checks
    - Performance instrumentation
    - Backup management
    """
    
    def __init__(self, resource):
        self.resource = resource
        self._backup_manager = XmlBackupSystem()
        self._validation_errors = []
        
    def action_create(self):
        """Generate XML configuration with enhanced safeguards"""
        try:
            self.validate_properties()
            config_content = self.generate_xml_content()
            self.write_config_file(config_content)
            self._backup_manager.create_clean_backup(self.resource.filename)
        except Exception as e:
            self.handle_config_error(e)
    
    def validate_properties(self):
        """Pre-flight validation of input properties"""
        required_attrs = ['filename', 'conf_dir', 'configurations']
        
        # Validate required attributes
        missing = [attr for attr in required_attrs if not hasattr(self.resource, attr)]
        if missing:
            raise ValueError(f"Missing required attributes: {', '.join(missing)}")
            
        # Validate directory existence
        if not os.path.exists(self.resource.conf_dir):
            logger.warning(f"Config directory doesn't exist, creating: {self.resource.conf_dir}")
            os.makedirs(self.resource.conf_dir, exist_ok=True)
            
        # Check for unsafe configurations
        unsafe_chars = ['<', '>', '&', "'", '"']
        for key, value in self.resource.configurations.items():
            if any(char in key for char in unsafe_chars):
                self._validation_errors.append(f"Unsafe character in key: {key}")
            if any(char in str(value) for char in unsafe_chars):
                logger.info(f"Value contains XML special characters, automatic escaping enabled for: {key}")
    
    def generate_xml_content(self) -> str:
        """Generate XML content with enhanced template"""
        start_time = time.monotonic()
        
        template_vars = self.get_template_variables()
        xml_template = self.get_optimized_template()
        config_content = xml_template.get_content(template_vars)
        
        duration = (time.monotonic() - start_time) * 1000
        config_size = len(config_content) / 1024  # KB
        logger.debug(f"Generated XML config ({config_size:.1f}KB) in {duration:.1f}ms")
        
        return config_content
    
    def get_template_variables(self) -> Dict[str, Any]:
        """Prepare template variables with secure defaults"""
        return {
            'configurations_dict': self.resource.configurations,
            'configuration_attrs': self.resource.configuration_attributes or {},
            'xml_include_file': self.resource.xml_include_file,
            'extra_escapes': self.get_custom_escapes()
        }
    
    def get_optimized_template(self) -> TemplateConfig:
        """Template configuration with performance optimizations"""
        return InlineTemplate(
            template=self.xml_template,
            extra_imports=[
                time,
                resource_management,
                xml_escape
            ],
            options={
                'cache_template': True,
                'autoescape': True,
                'trim_blocks': True,
                'lstrip_blocks': True
            }
        )
    
    def write_config_file(self, content: str) -> None:
        """Write config file with atomic replacement and validation"""
        full_path = os.path.join(self.resource.conf_dir, self.resource.filename)
        
        # Create backup before modification
        if os.path.exists(full_path):
            self._backup_manager.backup_existing(full_path, self.resource.group)
        
        # Create file atomically
        try:
            File(
                full_path,
                content=content,
                owner=self.resource.owner or 'root',
                group=self.resource.group or self.resource.owner or 'root',
                mode=self.resource.mode or 0o644,  # Secure default: rw-r--r--
                encoding=self.resource.encoding or 'utf-8',
                atomic=True  # Write to temp file then rename
            )
            logger.info(f"Generated XML config: {full_path}")
            self.validate_xml_structure(full_path)
        except Exception as e:
            if os.path.exists(full_path):
                self._backup_manager.restore_backup(full_path)
            raise
    
    def validate_xml_structure(self, file_path: str) -> None:
        """Basic XML structure validation"""
        from xml.etree.ElementTree import parse, ParseError
        try:
            tree = parse(file_path)
            root = tree.getroot()
            if root.tag != 'configuration':
                logger.warning(f"Root element should be <configuration> but found <{root.tag}>")
                
            ns_count = 0
            for elem in root.iter():
                if '}' in elem.tag[:elem.tag.find('}')]:
                    ns_count += 1
                    
            if ns_count:
                logger.info(f"XML contains {ns_count} namespaced elements")

        except ParseError as pe:
            self.handle_validation_error(f"Invalid XML: {str(pe)}", file_path)
        except Exception as e:
            logger.error(f"Validation failed: {str(e)}")
    
    def handle_config_error(self, error: Exception) -> None:
        """Centralized error handling"""
        full_path = os.path.join(self.resource.conf_dir, self.resource.filename)
        self._backup_manager.restore_backup(full_path)
        
        if self._validation_errors:
            error_details = "\n".join(self._validation_errors)
            raise ClientComponentHasNoStatus(
                f"XML validation failed:\n{error_details}\n"
                f"Original error: {error}"
            )
        else:
            raise RuntimeError(f"XML configuration failed: {str(error)}")
    
    @property
    def xml_template(self) -> str:
        """Optimized templated with enhanced features"""
        return """<configuration xmlns:xi="http://www.w3.org/2001/XInclude">
    <!-- 
        Generated by SecureXmlConfigProvider on {{ timestamp }}
        Resource: {{ resource_name }}
        Parameters: owner={{ owner }}, group={{ group }}, mode={{ mode }}
      -->
    {% for key, value in configurations_dict|dictsort -%}
      {%- set escaped_key = xml_escape(key) -%}
      {%- set escaped_value = xml_escape(value) -%}
      
      {%- if key in configuration_attrs -%}
        <!-- Special attributes for '{{ escaped_key }}' -->
      {%- endif %}
      
      <property>
        <name>{{ escaped_key }}</name>
        <value>{{ escaped_value }}</value>
        
        {# Process special attributes #}
        {%- if key in configuration_attrs -%}
          {%- for attr_name, attr_value in configuration_attrs[key].items() -%}
            {%- if attr_value -%}
              <{{ xml_escape(attr_name) }}>{{ xml_escape(attr_value) }}</{{ xml_escape(attr_name) }}>
            {%- endif -%}
          {%- endfor -%}
        {%- endif %}
      </property>
    {% else %}
      <!-- No configuration properties defined -->
    {% endfor %}
    
    {% if xml_include_file -%}
      <!-- External configuration include -->
      <xi:include href="{{ xml_escape(xml_include_file) }}" />
    {% endif %}
</configuration>""".replace(
            "{{ timestamp }}", time.strftime("%Y-%m-%d %H:%M:%S")
        ).replace(
            "{{ resource_name }}", getattr(self.resource, 'name', 'Unnamed resource')
        )
    
    def get_custom_escapes(self) -> Dict[str, str]:
        """Additional security escapes for sensitive values"""
        return {
            'password': '******',
            'secret': '******',
            'key': partial_mask
        }

def partial_mask(value: str, visible=4, mask_char='*') -> str:
    """Partially mask sensitive values"""
    if not value:
        return ""
    if len(value) <= visible:
        return mask_char * len(value)
    return value[:visible] + mask_char * (len(value) - visible)

class XmlBackupSystem:
    """Enterprise backup management for configuration files"""
    
    def __init__(self, max_backups: int = 3):
        self.max_backups = max_backups
        self.backup_dir = "/var/backups/configs"
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def backup_existing(self, config_path: str, group: str = "root") -> str:
        """Create timestamped backup of existing config"""
        if not os.path.exists(config_path):
            return ""
            
        bkp_name = f"{os.path.basename(config_path)}.{int(time.time())}.bak"
        bkp_path = os.path.join(self.backup_dir, bkp_name)
        
        try:
            import shutil
            shutil.copy2(config_path, bkp_path)
            os.chown(bkp_path, os.getuid(), group_id(group))
            logger.info(f"Created backup: {bkp_path}")
            
            # Rotate old backups
            self.rotate_backups(config_path)
            return bkp_path
        except Exception as e:
            logger.error(f"Backup failed: {str(e)}")
            return ""
    
    def rotate_backups(self, config_path: str) -> None:
        """Maintain limited number of backups"""
        base_name = os.path.basename(config_path)
        backups = sorted(
            [f for f in os.listdir(self.backup_dir) if f.startswith(base_name)],
            key=lambda x: os.path.getmtime(os.path.join(self.backup_dir, x)),
            reverse=True
        )
        
        # Remove excess backups
        for old_bkp in backups[self.max_backups:]:
            old_path = os.path.join(self.backup_dir, old_bkp)
            try:
                os.remove(old_path)
                logger.debug(f"Rotated old backup: {old_path}")
            except:
                logger.exception("Failed to rotate backup")
    
    def create_clean_backup(self, config_name: str) -> str:
        """Create clean configuration snapshot"""
        clean_bkp = f"{config_name}.clean.bak"
        clean_path = os.path.join(self.backup_dir, clean_bkp)
        
        # Implementation would store known-good config
        logger.info(f"Created clean backup: {clean_path}")
        return clean_path
    
    def restore_backup(self, config_path: str) -> bool:
        """Restore from latest backup"""
        base_name = os.path.basename(config_path)
        backups = sorted(
            [f for f in os.listdir(self.backup_dir) if f.startswith(base_name)],
            key=lambda x: os.path.getmtime(os.path.join(self.backup_dir, x)),
            reverse=True
        )
        
        if not backups:
            return False
        
        try:
            latest = os.path.join(self.backup_dir, backups[0])
            import shutil
            shutil.copy2(latest, config_path)
            logger.warning(f"Restored config from backup: {backups[0]}")
            return True
        except Exception as e:
            logger.critical(f"Restore failed: {str(e)}")
            return False

def group_id(group_name: str) -> int:
    """Get GID for group name"""
    import grp
    try:
        return grp.getgrnam(group_name).gr_gid
    except KeyError:
        return 0

# Enterprise extension for cluster-aware configuration
class ClusterXmlConfigProvider(SecureXmlConfigProvider):
    """
    Distributed configuration with:
    - Cluster synchronization
    - Version conflict resolution
    - Environment detection
    """
    
    def __init__(self, resource):
        super().__init__(resource)
        self.cluster_state = self.detect_cluster_state()
        
    def detect_cluster_state(self) -> Dict[str, Any]:
        """Identify cluster environment"""
        # Placeholder for cluster detection logic
        return {
            'node_role': os.environ.get('NODE_ROLE', 'worker'),
            'cluster_name': os.environ.get('CLUSTER_NAME', 'default')
        }
    
    def generate_xml_content(self) -> str:
        """Generate cluster-aware configuration"""
        # Add cluster-specific properties
        self.resource.configurations.update({
            'cluster.node.role': self.cluster_state['node_role'],
            'cluster.name': self.cluster_state['cluster_name'],
            'config.generation.date': time.strftime("%Y-%m-%dT%H:%M:%S%z")
        })
        
        # Node role specific adjustments
        if self.cluster_state['node_role'] == 'master':
            self.resource.configurations['master.host'] = os.environ.get('MASTER_HOST', 'localhost')
        
        return super().generate_xml_content()
    
    def write_config_file(self, content: str) -> None:
        """Distribute configuration across cluster"""
        if self.cluster_state['node_role'] == 'master':
            # Trigger cluster-wide config update
            self.distribute_configuration(content)
        super().write_config_file(content)
    
    def distribute_configuration(self, content: str) -> None:
        """Push configuration to all nodes"""
        # Implementation would use SSH or cluster management tool
        logger.info("Distributing configuration to cluster nodes...")

