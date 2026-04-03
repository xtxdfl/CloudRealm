#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
import logging
from enum import Enum
from typing import Dict, Generator, List, NamedTuple, Optional, Tuple

from models.commands import AgentCommand
from models.hooks import HookPrefix

# Public API exports
__all__ = ["ResolvedHooks", "HooksOrchestrator"]

# Define hook file paths
HOOK_SCRIPT_NAME = "hook.py"
SCRIPT_FOLDER = "scripts"

# Hook path template constants
SERVICE_TEMPLATE = "{service}"
ROLE_TEMPLATE = "{role}"


class HookEntry(NamedTuple):
    """Represents a resolved hook with path and context"""
    script_path: str
    base_dir: str
    hook_name: str


class ResolvedHooks:
    """
    Enterprise-grade hook management container providing:
        - Dynamic hook sequencing
        - Context-aware execution ordering
        - Lazy hook resolution
        - Execution lifecycle tracking
    
    Attributes:
        pre_hooks (Tuple[HookEntry]): Executes before main operation
        post_hooks (Tuple[HookEntry]): Executes after main operation
    """
    
    def __init__(self, pre_hooks: Optional[List[HookEntry]] = None, 
                 post_hooks: Optional[List[HookEntry]] = None):
        """
        Initialize hook sequences
        :param pre_hooks: Sequence of pre-execution hooks
        :param post_hooks: Sequence of post-execution hooks
        """
        # Initialize hooks as immutable tuples
        self._pre_hooks = tuple(pre_hooks) if pre_hooks else ()
        self._post_hooks = tuple(post_hooks) if post_hooks else ()
        
        # Execution tracking
        self.executed_pre = set()
        self.executed_post = set()
    
    @property
    def pre_hooks(self) -> Tuple[HookEntry, ...]:
        """Get immutable pre-execution hooks sequence"""
        return self._pre_hooks
    
    @property
    def post_hooks(self) -> Tuple[HookEntry, ...]:
        """Get immutable post-execution hooks sequence"""
        return self._post_hooks
    
    def has_pre_hooks(self) -> bool:
        """Check if any pre-execution hooks exist"""
        return bool(self._pre_hooks)
    
    def has_post_hooks(self) -> bool:
        """Check if any post-execution hooks exist"""
        return bool(self._post_hooks)
    
    def next_pre_hook(self) -> Optional[HookEntry]:
        """Get next unexecuted pre-execution hook (FIFO)"""
        for hook in self.pre_hooks:
            if hook not in self.executed_pre:
                return hook
        return None
    
    def next_post_hook(self) -> Optional[HookEntry]:
        """Get next unexecuted post-execution hook (LIFO)"""
        # Post-hooks should execute in reverse order
        for hook in reversed(self.post_hooks):
            if hook not in self.executed_post:
                return hook
        return None
    
    def mark_pre_completed(self, hook: HookEntry) -> None:
        """Mark a pre-hook as completed"""
        if hook not in self.pre_hooks:
            raise ValueError(f"Invalid pre-hook: {hook.hook_name}")
        self.executed_pre.add(hook)
    
    def mark_post_completed(self, hook: HookEntry) -> None:
        """Mark a post-hook as completed"""
        if hook not in self.post_hooks:
            raise ValueError(f"Invalid post-hook: {hook.hook_name}")
        self.executed_post.add(hook)
    
    def get_execution_summary(self) -> dict:
        """Generate hooks execution report"""
        return {
            "pre_hooks": {
                "total": len(self.pre_hooks),
                "executed": len(self.executed_pre),
                "pending": len(self.pre_hooks) - len(self.executed_pre)
            },
            "post_hooks": {
                "total": len(self.post_hooks),
                "executed": len(self.executed_post),
                "pending": len(self.post_hooks) - len(self.executed_post)
            }
        }


class HookSequenceTemplateType(Enum):
    """Defines hook sequence template resolution strategy"""
    STATIC = 1       # Fixed string sequences
    DYNAMIC = 2      # Generated via format template
    EXTERNAL = 3     # Loaded from config files


class HookSequenceBuilder:
    """
    Advanced hook sequencing engine with:
        - Multi-strategy template resolution
        - Conditional path inclusion
        - Custom sequence optimization
    
    Templates follow pattern:
        "{prefix}-{command}[{-service}][{-role}]"
    """
    
    # Hook sequence definitions with priority ordering
    DEFAULT_SEQUENCES = {
        HookPrefix.pre: [
            "{prefix}-{command}",
            "{prefix}-{command}-{service}",
            "{prefix}-{command}-{service}-{role}"
        ],
        HookPrefix.post: [
            "{prefix}-{command}-{service}-{role}",
            "{prefix}-{command}-{service}",
            "{prefix}-{command}"
        ]
    }
    
    def __init__(self, sequence_template: Optional[Dict[HookPrefix, List[str]]] = None,
                 template_type: HookSequenceTemplateType = HookSequenceTemplateType.DYNAMIC):
        """
        Initialize hook sequence builder
        :param sequence_template: Custom sequence definitions
        :param template_type: Sequence generation strategy
        """
        self.sequence_template = sequence_template or self.DEFAULT_SEQUENCES
        self.template_type = template_type
    
    def build(self, prefix: HookPrefix, command: str, service: Optional[str], role: Optional[str]) -> Generator[str, None, None]:
        """
        Generate hook sequence according to defined templates
        :param prefix: Hook category (pre/post)
        :param command: Command being executed
        :param service: Service context (optional)
        :param role: Component/role context (optional)
        :return: Generator of hook names
        """
        if prefix not in self.sequence_template:
            raise ValueError(f"Unsupported hook prefix: {prefix}")
        
        # Pre-validate context requirements
        if service is None:
            if any(SERVICE_TEMPLATE in t for t in self.sequence_template[prefix]):
                logging.debug("Skipping service-dependent hooks for command: %s", command)
        
        # Generate hook names
        for template in self.sequence_template[prefix]:
            # Skip service-dependent patterns if service not provided
            if SERVICE_TEMPLATE in template and service is None:
                continue
                
            # Skip role-dependent patterns if role not provided
            if ROLE_TEMPLATE in template and role is None:
                continue
                
            # Generate hook name based on template type
            if self.template_type == HookSequenceTemplateType.DYNAMIC:
                hook_name = template.format(prefix=prefix.value, command=command, service=service, role=role)
            else:
                hook_name = template  # For static templates
                
            yield hook_name

    def add_template(self, prefix: HookPrefix, template: str, position: int = None) -> None:
        """
        Add a custom template to the sequence
        :param prefix: Hook category
        :param template: Template string
        :param position: Insertion index (default at end)
        """
        if prefix not in self.sequence_template:
            self.sequence_template[prefix] = []
            
        if position is None:
            self.sequence_template[prefix].append(template)
        else:
            self.sequence_template[prefix].insert(position, template)
    
    def remove_template(self, prefix: HookPrefix, template: str) -> bool:
        """Remove template from sequence definition"""
        if prefix in self.sequence_template and template in self.sequence_template[prefix]:
            self.sequence_template[prefix].remove(template)
            return True
        return False


class HooksOrchestrator:
    """
    Enterprise hook resolution and management system providing:
        - Context-aware hook selection
        - Filesystem-based hook discovery
        - Execution order optimization
        - Dependency resolution
    
    Workflow:
        1. Resolve command context
        2. Generate hook sequence
        3. Validate hook existence
        4. Prepare execution environment
    """
    
    def __init__(self, file_cache, logger=None):
        """
        Initialize hook orchestrator
        :param file_cache: File caching infrastructure
        :param logger: Logging component
        """
        self.file_cache = file_cache
        self.logger = logger or logging.getLogger(__name__)
        self.hook_builder = HookSequenceBuilder()
        self._hook_cache = {}  # Cache discovered hooks
    
    def resolve_hooks(self, command_context: dict, command_name: str) -> Optional[ResolvedHooks]:
        """
        Resolve applicable hooks for the given command context
        :param command_context: Dictionary with command metadata
        :param command_name: Name of the command being executed
        :return: ResolvedHooks instance or None if not applicable
        """
        # Skip hook resolution for status commands
        if command_context.get("commandType") == AgentCommand.status:
            self.logger.debug("Skipping hooks for status command")
            return None
            
        # Skip if no command name provided
        if not command_name:
            return None
            
        # Obtain hook base directory
        hook_dir = self.file_cache.get_hook_base_dir(command_context)
        if not hook_dir or not os.path.isdir(hook_dir):
            self.logger.debug("Hook directory not found: %s", hook_dir)
            return ResolvedHooks()
            
        # Extract command context
        service = command_context.get("serviceName")
        role = command_context.get("role")
        
        # Generate hook sequences
        pre_hook_names = self.hook_builder.build(
            HookPrefix.pre, command_name, service, role
        )
        post_hook_names = self.hook_builder.build(
            HookPrefix.post, command_name, service, role
        )
        
        # Build populated hook entries
        pre_entries = list(self._resolve_hook_paths(hook_dir, pre_hook_names))
        post_entries = list(self._resolve_hook_paths(hook_dir, post_hook_names))
        
        return ResolvedHooks(pre_entries, post_entries)
    
    def _resolve_hook_paths(self, stack_hooks_dir: str, hooks_sequence: Generator[str, None, None]) -> Generator[HookEntry, None, None]:
        """
        Resolve hook paths from names, checking filesystem existence
        :param stack_hooks_dir: Base directory for hooks
        :param hooks_sequence: Generator of hook names
        :return: Generator of HookEntry tuples (script_path, base_dir, hook_name)
        """
        for hook_name in hooks_sequence:
            # Create cache key for fast existence check
            cache_key = f"{stack_hooks_dir}:{hook_name}"
            
            # Check cache first
            if cache_key in self._hook_cache:
                if entry := self._hook_cache[cache_key]:
                    yield entry
                continue
            
            # Validate hook directory exists
            hook_base_dir = os.path.join(stack_hooks_dir, hook_name)
            if not os.path.isdir(hook_base_dir):
                self.logger.debug("Hook directory not found: %s", hook_base_dir)
                self._hook_cache[cache_key] = None  # Cache negative result
                continue
                
            # Validate hook script exists
            hook_script_path = os.path.join(hook_base_dir, SCRIPT_FOLDER, HOOK_SCRIPT_NAME)
            if not os.path.isfile(hook_script_path):
                self.logger.debug("Hook script not found: %s", hook_script_path)
                self._hook_cache[cache_key] = None
                continue
            
            # Create hook entry for valid hook
            entry = HookEntry(
                script_path=hook_script_path,
                base_dir=hook_base_dir,
                hook_name=hook_name
            )
            self._hook_cache[cache_key] = entry
            yield entry
    
    def invalidate_cache(self, hook_path: Optional[str] = None) -> None:
        """Clear hook cache or specific entry"""
        if hook_path:
            if hook_path in self._hook_cache:
                del self._hook_cache[hook_path]
        else:
            self._hook_cache.clear()
    
    def add_custom_template(self, prefix: HookPrefix, pattern: str) -> None:
        """Add custom hook sequencing pattern"""
        self.hook_builder.add_template(prefix, pattern)
        self.logger.info("Added custom hook template: %s for %s", pattern, prefix)
    
    def reset_to_default_templates(self) -> None:
        """Revert to built-in sequence templates"""
        self.hook_builder = HookSequenceBuilder()
        self.logger.info("Reset hook templates to system defaults")
