#!/usr/bin/env python3
"""
高级钩子前缀管理器 - 用于统一管理钩子生命周期前缀
提供类型安全的钩子阶段标识和生命周期管理功能
"""

from enum import Enum, unique
from typing import Dict, Tuple, List, Optional
from dataclasses import dataclass

class HookLifecycleManager:
    """
    钩子生命周期管理器 - 统一管理钩子执行阶段
    
    功能:
        1. 提供统一的钩子阶段标识 (前/后)
        2. 支持自定义钩子分组
        3. 实现钩子执行顺序控制
        4. 提供类型安全的钩子阶段访问
    """
    
    @unique
    class HookStage(Enum):
        """钩子执行阶段枚举"""
        PRE = "before"  # 操作前阶段
        POST = "after"  # 操作后阶段
        
        def __str__(self):
            return self.value
        
        @classmethod
        def from_value(cls, value):
            """从字符串值创建枚举"""
            return {e.value: e for e in cls}.get(value.lower())
    
    @dataclass(frozen=True)
    class HookType:
        """钩子类型标识类"""
        group: str
        name: str
        stage: 'HookLifecycleManager.HookStage'
        
        def __str__(self):
            return f"{self.group}.{self.stage}.{self.name}"
        
        def event_name(self) -> str:
            """生成事件注册名"""
            return f"{self.stage}_{self.group}_{self.name}"
        
        @classmethod
        def parse(cls, prefix: str) -> Optional['HookLifecycleManager.HookType']:
            """从字符串解析钩子类型"""
            parts = prefix.split('.', 2)
            if len(parts) == 3:
                stage = HookLifecycleManager.HookStage.from_value(parts[1])
                if stage:
                    return cls(group=parts[0], name=parts[2], stage=stage)
            return None
    
    def __init__(self):
        """初始化钩子生命周期管理器"""
        self._prefix_registry = {}
        self._hook_execution_order = {}
    
    def register_prefix(self, group: str, hook_prefix: str, 
                        execution_priority: int = 50) -> bool:
        """
        注册钩子前缀
        
        Args:
            group: 钩子所属组名
            hook_prefix: 钩子前缀标识符
            execution_priority: 执行优先级 (0-100, 值越小执行越早)
        
        Returns:
            注册成功返回 True，名称冲突返回 False
        """
        # 解析钩子类型
        hook_type = self.HookType.parse(f"{group}.{hook_prefix}")
        if not hook_type:
            return False
            
        # 检查是否已注册
        key = hook_type.event_name()
        if key in self._prefix_registry:
            return False
            
        # 注册钩子
        self._prefix_registry[key] = hook_type
        self._hook_execution_order[key] = execution_priority
        return True
    
    def get_hook_type(self, group: str, stage: str, name: str) -> Optional['HookType']:
        """
        获取钩子类型对象
        
        Args:
            group: 钩子所属组名
            stage: 钩子阶段 (before/after)
            name: 钩子名称
        
        Returns:
            对应的 HookType 对象，未注册返回 None
        """
        stage_enum = self.HookStage.from_value(stage)
        if not stage_enum:
            return None
            
        event_key = f"{stage_enum.value}_{group}_{name}"
        return self._prefix_registry.get(event_key)
    
    def get_execution_order(self, group: str, stage: str, name: str) -> int:
        """
        获取钩子执行优先级
        
        Args:
            group: 钩子所属组名
            stage: 钩子阶段 (before/after)
            name: 钩子名称
        
        Returns:
            钩子执行优先级 (默认50)
        """
        hook_type = self.get_hook_type(group, stage, name)
        if not hook_type:
            return 50
            
        return self._hook_execution_order.get(hook_type.event_name(), 50)
    
    def list_hooks_for_group(self, group: str) -> List['HookType']:
        """
        列出指定组的所有钩子
        
        Args:
            group: 钩子组名
        
        Returns:
            该组的所有钩子类型列表
        """
        return [ht for ht in self._prefix_registry.values() if ht.group == group]
    
    def list_hooks_for_stage(self, stage: HookStage) -> List['HookType']:
        """
        列出指定阶段的所有钩子
        
        Args:
            stage: HookStage 枚举值
        
        Returns:
            该阶段的所有钩子类型列表
        """
        return [ht for ht in self._prefix_registry.values() if ht.stage == stage]
    
    def get_sorted_hooks(self, group: str, stage: HookStage) -> List['HookType']:
        """
        获取指定组和阶段的有序钩子列表
        
        Args:
            group: 钩子组名
            stage: HookStage 枚举值
        
        Returns:
            按优先级排序的钩子列表
        """
        hooks = [ht for ht in self.list_hooks_for_group(group) if ht.stage == stage]
        return sorted(
            hooks, 
            key=lambda ht: self.get_execution_order(ht.group, ht.stage.value, ht.name)
        )


# 钩子管理器初始化工具
def setup_standard_hooks() -> HookLifecycleManager:
    """创建具有标准钩子配置的生命周期管理器"""
    manager = HookLifecycleManager()
    
    # 定义标准钩子组
    standard_groups = {
        "system": {
            "hook_prefixes": [
                ("init", HookLifecycleManager.HookStage.PRE, 0),
                ("start", HookLifecycleManager.HookStage.PRE, 10),
                ("shutdown", HookLifecycleManager.HookStage.PRE, 90),
                ("stop", HookLifecycleManager.HookStage.PRE, 100),
                
                ("init", HookLifecycleManager.HookStage.POST, 100),
                ("start", HookLifecycleManager.HookStage.POST, 90),
                ("shutdown", HookLifecycleManager.HookStage.POST, 10),
                ("stop", HookLifecycleManager.HookStage.POST, 0)
            ],
            "priority_offset": 50
        },
        "service": {
            "hook_prefixes": [
                ("process", HookLifecycleManager.HookStage.PRE, 40),
                ("process", HookLifecycleManager.HookStage.POST, 60),
                ("monitor", HookLifecycleManager.HookStage.PRE, 30),
                ("monitor", HookLifecycleManager.HookStage.POST, 70),
                ("deploy", HookLifecycleManager.HookStage.PRE, 20),
                ("deploy", HookLifecycleManager.HookStage.POST, 80)
            ]
        },
        "action": {
            "hook_prefixes": [
                ("execute", HookLifecycleManager.HookStage.PRE, 10),
                ("validate", HookLifecycleManager.HookStage.PRE, 5),
                ("validate", HookLifecycleManager.HookStage.POST, 95),
                ("execute", HookLifecycleManager.HookStage.POST, 90)
            ]
        }
    }
    
    # 注册钩子配置
    for group, config in standard_groups.items():
        for prefix, stage, priority in config["hook_prefixes"]:
            priority += config.get("priority_offset", 0)
            manager.register_prefix(
                group=group,
                hook_prefix=stage.value,
                execution_priority=priority
            )
            # 注册名称时添加stage.value
            # 实际注册的钩子类型为 group + stage.value + prefix
    
    return manager


# 钩子框架接口
class HookContext:
    """钩子执行的上下文类"""
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self._errors = []
        
    def add_error(self, error_message: str) -> None:
        """添加执行错误"""
        self._errors.append(error_message)
        
    def has_errors(self) -> bool:
        """检查是否有错误"""
        return len(self._errors) > 0
        
    def get_errors(self) -> List[str]:
        """获取所有错误信息"""
        return self._errors.copy()


class Hook:
    """钩子基类"""
    def __init__(self, hook_type: HookLifecycleManager.HookType):
        self.type = hook_type
        
    def execute(self, context: HookContext) -> None:
        """抽象执行方法"""
        raise NotImplementedError("所有钩子必须实现execute方法")


class HookRegistry:
    """钩子注册表"""
    def __init__(self):
        self._hooks = {}
        
    def register_hook(self, hook: Hook) -> None:
        """注册钩子"""
        key = hook.type.event_name()
        if key not in self._hooks:
            self._hooks[key] = []
        self._hooks[key].append(hook)
        
    def execute_hooks(self, hook_type: HookLifecycleManager.HookType, context: HookContext) -> None:
        """执行特定类型的所有钩子"""
        key = hook_type.event_name()
        for hook in self._hooks.get(key, []):
            hook.execute(context)


# 示例钩子实现
class LogInitializationHook(Hook):
    """系统初始化日志钩子"""
    def __init__(self):
        hook_type = HookLifecycleManager.HookType(group="system", name="log", 
                                                 stage=HookLifecycleManager.HookStage.PRE)
        super().__init__(hook_type)
        
    def execute(self, context: HookContext) -> None:
        print(f"[PRE-SYSTEM-INIT] 正在初始化: {context.module_name}")


class ValidationPostHook(Hook):
    """动作后验证钩子"""
    def __init__(self):
        hook_type = HookLifecycleManager.HookType(group="action", name="validate", 
                                                 stage=HookLifecycleManager.HookStage.POST)
        super().__init__(hook_type)
        
    def execute(self, context: HookContext) -> None:
        if not context.action_result.get("success", False):
            context.add_error("操作执行失败")

