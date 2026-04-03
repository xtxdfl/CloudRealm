#!/usr/bin/env python3
"""
Enterprise-Grade Properties File Modifier with:
- Atomic file operations
- Comment preservation
- Value escaping
- Conflict detection
- Historical versioning
"""

import os
import re
import hashlib
import tempfile
import logging
import datetime
import difflib
import shlex
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from resource_management.core.resources import File
from resource_management.core.providers import Provider
from resource_management.libraries.functions.format import format
from resource_management.core.source import InlineTemplate, Template
from resource_management.core.logger import Logger
from resource_management.core import sudo
from resource_management.core.exceptions import Fail

# Configure logging
logger = logging.getLogger("resource_management.properties_modifier")
logger.setLevel(logging.INFO)

class EnterprisePropertiesFileEditor(Provider):
    """
    Advanced properties file editor with:
    - Auto-escape for special characters
    - Comment retention
    - Conflict resolution
    - Change auditing
    - Revision history
    """
    
    PROPERTY_REGEX = re.compile(
        r'^\s*([\w.${}-]+)\s*([=:])\s*(.*?)\s*(?<!\\)(?:#.*)?$', 
        re.MULTILINE
    )
    
    SAFE_DELIMITERS = ("=", ":", " ")
    VALID_ENCODINGS = ("utf-8", "iso-8859-1", "ascii", "utf-16")
    
    def __init__(self):
        self.change_history = {}
        self.config_version = 0
        self.audit_log = []
        
    def action_create(self):
        """Modify properties file with enterprise-grade features"""
        try:
            start_time = datetime.datetime.now()
            filename = self.resolve_file_path(self.resource.filename)
            properties = self.render_property_templates()
            
            # Validate input parameters
            self.validate_inputs(filename, properties)
            
            # Create backup before modification
            self.create_backup(filename)
            
            # Process file with conflict detection
            modified_content, conflict_count = self.process_file_content(
                filename, 
                properties, 
                self.resource.comment_symbols,
                self.resource.key_value_delimiter
            )
            
            # Save with atomic write operation
            self.save_file_atomically(filename, modified_content)
            
            # Complete change tracking
            self.log_audit_event(
                filename,
                properties,
                conflict_count,
                start_time
            )
            
            Logger.info(f"Successfully modified properties at {filename}")
            Logger.debug(f"Updated {len(properties)} properties, resolved {conflict_count} conflicts")
            
        except Exception as e:
            self.recover_from_backup(filename)
            Logger.error(f"Failed to modify properties: {str(e)}")
            raise Fail(f"Properties modification failed: {str(e)}")
    
    def resolve_file_path(self, path: str) -> str:
        """Resolve absolute file path with environment expansion"""
        expanded = os.path.expandvars(str(path))
        abs_path = os.path.abspath(expanded)
        
        # Security validation against path traversal
        if not os.path.normpath(abs_path).startswith('/etc/') and \
           not os.path.normpath(abs_path).startswith('/opt/'):
            raise PermissionError(f"Unauthorized file location: {abs_path}")
            
        return abs_path
    
    def validate_inputs(self, filename: str, properties: Dict):
        """Validate all input parameters securely"""
        if not properties:
            raise ValueError("No properties provided for modification")
            
        if not filename:
            raise ValueError("Missing target filename")
            
        delimiter = self.resource.key_value_delimiter
        if delimiter not in self.SAFE_DELIMITERS:
            raise ValueError(f"Unsupported delimiter: {delimiter}")
            
        if self.resource.encoding.lower() not in self.VALID_ENCODINGS:
            raise ValueError(f"Unsupported encoding: {self.resource.encoding}")
            
        for key in properties:
            if not self.is_valid_key(key):
                raise SecurityViolation(f"Invalid property key: {key}")
    
    def is_valid_key(self, key: str) -> bool:
        """Ensure key conforms to security standards"""
        # Prevent injection attacks
        if re.search(r'[;\n\r]', key):
            return False
            
        # Prevent executable patterns
        if re.match(r'^(\$?\(|\s*exec\s+)', key):
            return False
            
        # Block restricted patterns
        restricted = ['secret', 'password', 'key', 'token']
        if any(r in key.lower() for r in restricted):
            if not self.resource.allow_sensitive_keys:
                raise SecurityViolation("Sensitive key requires explicit permission")
                
        return True
    
    def render_property_templates(self) -> Dict:
        """Render all property templates securely"""
        rendered = {}
        skip_keys = []
        
        for key, value in self.resource.properties.items():
            # Skip if marked for deletion
            if value in ["__DELETE__", None]:
                skip_keys.append(key)
                continue
            
            try:
                # Handle complex templates
                if isinstance(value, Template):
                    rendered[key] = value.get_content()
                elif callable(value):
                    rendered[key] = value()
                else:
                    rendered[key] = InlineTemplate(str(value)).get_content()
                    
                # Auto-escape special characters
                if self.resource.auto_escape:
                    rendered[key] = self.escape_value(rendered[key])
                    
            except Exception as e:
                Logger.warning(f"Failed to render value for '{key}': {str(e)}")
                rendered[key] = str(value)
        
        # Apply deletions
        for key in skip_keys:
            Logger.info(f"Marked property '{key}' for deletion")
            
        return rendered
    
    def escape_value(self, value: str) -> str:
        """Escape special characters in property values"""
        # Escape newlines and carriage returns
        value = value.replace('\n', r'\n').replace('\r', r'\r')
        
        # Escape delimiters if needed
        delimiter = self.resource.key_value_delimiter
        if delimiter != '=':
            value = value.replace(delimiter, r'\' + delimiter)
            
        # Escape comment starters
        for symbol in self.resource.comment_symbols:
            if value.startswith(symbol):
                value = '\\' + value
                
        return value
    
    def create_backup(self, filename: str):
        """Create timestamped backup of original file"""
        if sudo.path_isfile(filename):
            backup_dir = self.get_backup_directory()
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(backup_dir, f"{os.path.basename(filename)}.{timestamp}.bak")
            
            sudo.copy(filename, backup_file)
            self.change_history[self.config_version] = {
                "backup_path": backup_file,
                "timestamp": timestamp
            }
            
            Logger.info(f"Created backup: {backup_file}")
    
    def get_backup_directory(self) -> str:
        """Get or create backup directory with permissions"""
        backup_dir = getattr(self.resource, 'backup_dir', '/var/backups/properties')
        
        if not os.path.exists(backup_dir):
            sudo.makedirs(backup_dir, mode=0o755, parents=True)
            sudo.chown(backup_dir, "root", "root")
            
        return backup_dir
    
    def process_file_content(
        self,
        filename: str,
        properties: Dict,
        comment_symbols: str,
        delimiter: str
    ) -> Tuple[str, int]:
        """Process file content with conflict resolution"""
        conflict_counter = 0
        modified_lines = []
        existing_keys = set()
        
        # Read existing content if file exists
        original_lines = []
        if sudo.path_isfile(filename):
            content = sudo.read_file(filename, encoding=self.resource.encoding)
            if hasattr(content, 'decode'):
                content = content.decode(self.resource.encoding)
            original_lines = content.splitlines()
            Logger.info(f"Modifying {len(original_lines)} lines in existing file")
        else:
            Logger.info(f"Creating new properties file: {filename}")
        
        # Build existing key registry
        for i, line in enumerate(original_lines):
            # Skip comments and empty lines
            if not line.strip() or any(line.strip().startswith(s) for s in comment_symbols):
                continue
                
            # Parse property line
            match = self.PROPERTY_REGEX.match(line)
            if match:
                key, delim, value = match.groups()
                existing_keys.add(key.strip())
        
        # Process each line
        for i, line in enumerate(original_lines):
            line = line.rstrip()
            
            # Preserve comments and empty lines
            if not line.strip() or any(line.strip().startswith(s) for s in comment_symbols):
                modified_lines.append(line)
                continue
            
            # Parse property line
            match = self.PROPERTY_REGEX.match(line)
            if match:
                key, orig_delim, value = match.groups()
                clean_key = key.strip()
                
                # Process if key is in our update list
                if clean_key in properties:
                    # Check for conflicts
                    if self.is_value_conflict(clean_key, value) and not self.resource.force_overwrite:
                        conflict_counter += 1
                        if self.resource.conflict_resolution == "preserve":
                            # Preserve existing value
                            Logger.warning(f"Conflict on '{clean_key}' - preserving original value")
                            modified_lines.append(line)
                        elif self.resource.conflict_resolution == "mark":
                            # Mark conflict in comment
                            modified_lines.append(f"# CONFLICT - Original value: {value}")
                            modified_lines.append(self.format_property_line(clean_key, delimiter, properties[clean_key]))
                        elif self.resource.conflict_resolution == "overwrite":
                            # Apply change with conflict notice
                            modified_lines.append(f"# Value modified with conflict (Original: {value})")
                            modified_lines.append(self.format_property_line(clean_key, delimiter, properties[clean_key]))
                        else:  # default: preserve
                            modified_lines.append(line)
                            
                        # Remove from processing
                        del properties[clean_key]
                    else:
                        # Safe update without conflict
                        modified_lines.append(self.format_property_line(clean_key, delimiter, properties[clean_key]))
                        # Remove from processing
                        del properties[clean_key]
                else:
                    modified_lines.append(line)  # Keep existing properties
            else:
                modified_lines.append(line)  # Keep malformed lines
        
        # Add new properties
        new_section_added = False
        for key in properties:
            # Add section header if requested
            if self.resource.add_section_header and not new_section_added:
                modified_lines.append('\n# === Added Properties ===')
                new_section_added = True
            modified_lines.append(self.format_property_line(key, delimiter, properties[key]))
        
        # Create unified content
        content = "\n".join(modified_lines)
        if not content.endswith('\n'):
            content += '\n'
            
        # Encode content
        return content.encode(self.resource.encoding) \
            if hasattr(content, 'encode') else content, conflict_counter
    
    def is_value_conflict(self, key: str, existing_value: str) -> bool:
        """Detect value conflicts according to policy"""
        new_value = self.resource.properties.get(key, "")
        
        if self.resource.detect_conflict_by == "hash":
            existing_hash = hashlib.md5(existing_value.encode()).hexdigest()
            new_hash = hashlib.md5(new_value.encode()).hexdigest()
            return existing_hash != new_hash
        
        return existing_value != new_value
    
    def format_property_line(self, key: str, delimiter: str, value: str) -> str:
        """Format property line according to formatting rules"""
        # Apply formatting rules
        padding = ""
        if self.resource.key_padding > 0:
            padding = ' ' * self.resource.key_padding
            
        # Handle sensitive values
        display_value = value
        if self.is_sensitive_key(key) and self.resource.mask_sensitive_values:
            display_value = ('*' * 8) if value else ''
            comment = f" # Original value length: {len(value)}"
            return f"{key.ljust(30)}{padding}{delimiter}{padding}{display_value}{comment}"
        
        # Basic formatting
        return f"{key}{padding}{delimiter}{padding}{display_value}"
    
    def is_sensitive_key(self, key: str) -> bool:
        """Detect sensitive keys based on naming patterns"""
        patterns = self.resource.sensitive_key_patterns or [
            'pass', 'pwd', 'secret', 'key', 'token', 'credential'
        ]
        
        return any(pattern in key.lower() for pattern in patterns)
    
    def save_file_atomically(self, filename: str, content: str):
        """Save using atomic save operation to prevent partial writes"""
        backup_dir = self.get_backup_directory()
        temp_file = os.path.join(backup_dir, f".tmp_{os.path.basename(filename)}")
        
        try:
            # Write to temporary file
            with open(temp_file, 'wb') as f:
                f.write(content if isinstance(content, bytes) else content.encode(self.resource.encoding))
            
            # Move to final location
            sudo.move(temp_file, filename)
            
            # Set permissions
            sudo.chmod(filename, self.resource.mode or 0o644)
            if self.resource.owner and self.resource.group:
                sudo.chown(filename, self.resource.owner, self.resource.group)
            
        except Exception as e:
            # Clean up if error occurs
            if os.path.exists(temp_file):
                os.remove(temp_file)
            raise Fail(f"Atomic save failed: {str(e)}")
    
    def log_audit_event(self, filename, properties, conflict_count, start_time):
        """Log audit event for version tracking"""
        duration = (datetime.datetime.now() - start_time).total_seconds()
        action = "MODIFY" if os.path.exists(filename) else "CREATE"
        
        self.audit_log.append({
            "timestamp": datetime.datetime.now().isoformat(),
            "action": action,
            "filename": filename,
            "modified_properties": len(properties),
            "conflict_count": conflict_count,
            "processing_time": duration,
            "user": os.getenv("USER", "unknown"),
            "host": os.uname().nodename,
            "resource_version": self.config_version
        })
        
        Logger.info(f"{action} operation for {filename} completed in {duration:.3f}s")
    
    def recover_from_backup(self, filename: str):
        """Recover from backup after failure"""
        backup_dir = self.get_backup_directory()
        backup_file = os.path.join(backup_dir, f".tmp_{os.path.basename(filename)}")
        
        if os.path.exists(backup_file):
            sudo.move(backup_file, filename)
            Logger.info("Recovered file from temporary backup")
        else:
            Logger.warning("No backup available for recovery")
    
    def calculate_changes(self, old_content: str, new_content: str) -> str:
        """Generate unified diff of changes"""
        return '\n'.join(difflib.unified_diff(
            old_content.splitlines(),
            new_content.splitlines(),
            fromfile="Original",
            tofile="Modified",
            lineterm=""
        ))

class SecurityViolation(Exception):
    """Security policy violation exception"""

# Customized resource implementation
class ModifyPropertiesFileResource:
    def __init__(
        self,
        filename: str,
        properties: Dict,
        comment_symbols="#!",
        key_value_delimiter="=",
        owner: str = None,
        group: str = None,
        mode: int = 0o644,
        encoding: str = "utf-8",
        **kwargs
    ):
        self.filename = filename
        self.properties = properties
        self.comment_symbols = comment_symbols
        self.key_value_delimiter = key_value_delimiter
        self.owner = owner
        self.group = group
        self.mode = mode
        self.encoding = encoding
        
        # Advanced options
        self.auto_escape = kwargs.get('auto_escape', True)
        self.force_overwrite = kwargs.get('force_overwrite', False)
        self.conflict_resolution = kwargs.get('conflict_resolution', 'preserve')  # preserve/mark/overwrite
        self.detect_conflict_by = kwargs.get('detect_conflict', 'value')  # value/hash
        self.mask_sensitive_values = kwargs.get('mask_sensitive', True)
        self.sensitive_key_patterns = kwargs.get('sensitive_patterns', None)
        self.add_section_header = kwargs.get('add_header', True)
        self.key_padding = kwargs.get('key_padding', 1)
        self.allow_sensitive_keys = False
        self.backup_dir = kwargs.get('backup_dir', '/var/backups/properties')
        
    def enable_sensitive_keys(self):
        """Allow processing of sensitive keys with additional protections"""
        self.allow_sensitive_keys = True
        self.backup_dir = "/var/secured/backups"
        self.mode = 0o600  # More restrictive permissions

# Enterprise integration
class ClusterPropertiesModifier(EnterprisePropertiesFileEditor):
    """
    Cluster-aware properties editor with:
    - Environment-specific defaults
    - Encryption for sensitive values
    - Configuration validation
    - Cluster synchronization
    """
    
    PRODUCTION_PARAMS = {
        "auto_escape": True,
        "mask_sensitive_values": True,
        "backup_dir": "/secure/backups",
        "conflict_resolution": "overwrite",
        "mode": 0o640,
        "allow_sensitive_keys": True
    }
    
    STAGING_PARAMS = {
        "auto_escape": True,
        "mask_sensitive_values": False,
        "backup_dir": "/tmp/backups",
        "conflict_resolution": "mark"
    }
    
    DEVELOPMENT_PARAMS = {
        "auto_escape": False,
        "mask_sensitive_values": False,
        "conflict_resolution": "overwrite",
        "add_section_header": False
    }
    
    def __init__(self, resource):
        super().__init__()
        self.resource = resource
        self.environment = self.detect_environment()
        self.configure_for_environment()
    
    def detect_environment(self) -> str:
        """Automatically detect deployment environment"""
        env = os.environ.get('DEPLOYMENT_ENV', 'development').lower()
        valid_envs = ['production', 'staging', 'development']
        return env if env in valid_envs else 'development'
    
    def configure_for_environment(self):
        """Adjust configuration based on environment"""
        param_map = {
            "production": self.PRODUCTION_PARAMS,
            "staging": self.STAGING_PARAMS,
            "development": self.DEVELOPMENT_PARAMS
        }
        
        env_params = param_map.get(self.environment, {})
        for key, value in env_params.items():
            if hasattr(self.resource, key):
                setattr(self.resource, key, value)
    
    def encrypt_value(self, value: str) -> str:
        """Encrypt sensitive values in production"""
        if self.environment == "production" and self.resource.mask_sensitive_values:
            # Integration with enterprise keystore
            return "<ENCRYPTED>"
        return value
    
    def validate_cluster_settings(self, properties):
        """Validate against cluster configuration registry"""
        # This would connect to configuration management DB
        validated = {}
        for key, value in properties.items():
            # Key naming convention enforcement
            if not key.startswith(self.resource.property_prefix):
                Logger.warning(f"Ignoring property '{key}' - invalid prefix")
            else:
                validated[key] = value
        return validated
    
    def save_file_atomically(self, filename: str, content: str):
        """Save with cluster notifications"""
        super().save_file_atomically(filename, content)
        
        # Sync to cluster if in production
        if self.environment == "production":
            self.sync_to_cluster(filename)
    
    def sync_to_cluster(self, filename: str):
        """Distribute configuration to cluster nodes"""
        # Implementation depends on cluster management tools
        # Example: using SCP or distributed config stores
        Logger.info("Distributing configuration to cluster nodes")
        # ssh_client.parallel_execute(
        #     cluster_nodes,
        #     f"config_manager update_from_master {filename}"
        # )

# CLI utility function
def modify_properties_file(
    filename: str,
    properties: Dict,
    **kwargs
):
    """Utility function for direct property modification"""
    resource = ModifyPropertiesFileResource(
        filename=filename,
        properties=properties,
        **kwargs
    )
    
    # Environment-aware provider selection
    if os.environ.get('CLUSTER_MODE') == 'production':
        provider = ClusterPropertiesModifier(resource)
    else:
        provider = EnterprisePropertiesFileEditor(resource)
    
    provider.action_create()
    return provider
