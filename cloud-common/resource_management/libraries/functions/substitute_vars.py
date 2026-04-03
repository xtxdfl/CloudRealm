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

Advanced Variable Substitution Engine
"""

import re
from typing import Dict, Union, Callable, Optional, Tuple, Any
import logging

# 安全日志记录配置
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("var_substitute")

# 默认最大替换深度
MAX_SUBSTITUTION_DEPTH = 50
DEFAULT_SUBSTITUTION_PATTERN = r"\$\{([A-Za-z0-9_\-\.]+)\}"
SAFE_SUBSTITUTION_PATTERN = r"\$\{([A-Za-z0-9_\-\. ]+?)\}"

class VariableEngine:
    """可扩展的变量替换引擎"""
    
    def __init__(self, config: Dict[str, Any], 
                 max_depth: int = MAX_SUBSTITUTION_DEPTH,
                 pattern: str = DEFAULT_SUBSTITUTION_PATTERN):
        """
        :param config: 变量配置字典
        :param max_depth: 最大替换深度
        :param pattern: 变量匹配正则模式
        """
        self.config = config
        self.max_depth = max_depth
        self.compiled_pattern = re.compile(pattern)
        self.resolved_cache = {}
        self.unresolved = set()
        
    def safe_substitute(self, template: str, 
                       fallback: Union[str, Callable] = None,
                       context_params: Optional[Dict] = None) -> str:
        """
        安全的变量替换方法
        :param template: 输入模板字符串
        :param fallback: 未找到变量时的回退值或处理函数
        :param context_params: 临时上下文变量
        :return: 替换后的字符串
        """
        if not template:
            return ""
            
        # 创建临时上下文
        temp_config = {**self.config, **(context_params or {})}
        output = template
        
        # 检查缓存
        cache_key = (template, tuple(sorted(context_params.items()) if context_params else None)
        if cache_key in self.resolved_cache:
            return self.resolved_cache[cache_key]
        
        # 变量替换跟踪
        visited = set()
        
        # 深度控制循环
        for depth in range(self.max_depth):
            changes = False
            matches = list(self.compiled_pattern.finditer(output))
            
            if not matches:
                break
                
            # 反向替换避免位置偏移
            for match in reversed(matches):
                full_match = match.group(0)
                var_name = match.group(1)
                
                # 避免递归引用
                if full_match in visited:
                    logger.warning(f"循环引用检测: '{full_match}'，已跳过")
                    continue
                    
                # 在配置中查找变量
                if var_name in temp_config:
                    var_value = temp_config[var_name]
                    
                    # 值为None特殊处理
                    if var_value is None:
                        var_value = ""
                    # 非字符串类型转换
                    elif not isinstance(var_value, str):
                        var_value = str(var_value)
                        
                    # 检查嵌套变量
                    if self.compiled_pattern.search(var_value):
                        visited.add(full_match)
                        output = output[:match.start()] + var_value + output[match.end():]
                        changes = True
                    else:
                        # 直接替换无嵌套
                        output = output.replace(full_match, var_value, 1)
                        changes = True
                else:
                    # 处理未定义变量
                    resolved = self._handle_undefined(full_match, var_name, fallback)
                    output = output.replace(full_match, resolved, 1)
                    
                    # 记录未解析变量
                    if resolved == full_match:
                        self.unresolved.add(var_name)
            
            # 如果没有变化，退出循环
            if not changes:
                break
        
        # 缓存结果
        self.resolved_cache[cache_key] = output
        
        # 清理访问记录
        visited.clear()
        
        return output

    def _handle_undefined(self, full_match: str, var_name: str, 
                         fallback: Union[str, Callable]) -> str:
        """处理未定义的变量"""
        # 自定义回调处理
        if callable(fallback):
            try:
                return fallback(var_name)
            except Exception as e:
                logger.error(f"回调函数处理失败 '{var_name}': {str(e)}")
                return full_match
                
        # 静态回退值
        if fallback is not None:
            return str(fallback)
            
        # 默认保留原始格式
        return full_match

def substitute_vars(
    template: str, 
    config: Dict[str, Any], 
    max_depth: int = MAX_SUBSTITUTION_DEPTH,
    safe: bool = True,
    fallback: Union[str, Callable] = None
) -> str:
    """
    高级变量替换函数
    :param template: 包含变量的模板字符串
    :param config: 变量名-值映射字典
    :param max_depth: 最大嵌套替换深度
    :param safe: 安全模式（允许空格及特殊字符）
    :param fallback: 未定义变量的默认值或处理函数
    :return: 已解析的字符串
    """
    pattern = SAFE_SUBSTITUTION_PATTERN if safe else DEFAULT_SUBSTITUTION_PATTERN
    engine = VariableEngine(config, max_depth, pattern)
    return engine.safe_substitute(template, fallback)

def substitute_vars_recursive(
    data: Union[Dict, List, str], 
    config: Dict[str, Any], 
    **kwargs
) -> Any:
    """
    递归替换数据结构中的所有字符串值
    :param data: 输入数据（字典、列表或字符串）
    :param config: 变量名-值映射字典
    :return: 已解析的数据结构
    """
    engine = VariableEngine(config, **kwargs)
    
    # 字符串处理
    if isinstance(data, str):
        return engine.safe_substitute(data)
        
    # 列表递归处理
    if isinstance(data, list):
        return [substitute_vars_recursive(item, config, **kwargs) for item in data]
    
    # 字典递归处理
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            processed_key = substitute_vars_recursive(key, config, **kwargs)
            processed_value = substitute_vars_recursive(value, config, **kwargs)
            result[processed_key] = processed_value
        return result
        
    # 其他类型直接返回
    return data

def extract_variables(template: str, pattern: str = DEFAULT_SUBSTITUTION_PATTERN) -> set:
    """
    从模板中提取所有变量名
    :param template: 输入模板字符串
    :return: 提取的变量名集合
    """
    return {match.group(1) for match in re.finditer(pattern, template)}

def create_substitution_map(
    config: Dict[str, Any],
    extra_vars: Optional[Dict] = None,
    resolve_nested: bool = True
) -> Dict[str, str]:
    """
    创建变量值映射字典
    :param config: 原始配置字典
    :param extra_vars: 额外变量
    :param resolve_nested: 是否解析嵌套变量
    :return: 已解析的变量映射
    """
    combined = {**config, **(extra_vars or {})}
    
    # 递归解析嵌套变量
    if resolve_nested:
        engine = VariableEngine(combined)
        return {
            key: engine.safe_substitute(str(value)) 
            for key, value in combined.items()
        }
    
    return {key: str(value) for key, value in combined.items()}

def parse_value_with_types(expression: str, config: Dict) -> Any:
    """
    解释带类型声明的值表达式
    :param expression: 表达式字符串（如 "int:${port}"）
    :param config: 变量配置字典
    :return: 解析后的值
    """
    if not expression:
        return expression
        
    # 类型解析器映射
    type_parsers = {
        "int": lambda v: int(float(v)),
        "float": float,
        "bool": lambda v: v.lower() in ("true", "1", "yes", "t", "y"),
        "str": str,
        "json": lambda v: json.loads(substitute_vars(v, config))
    }
    
    # 检查类型声明
    type_prefix, value = self._split_type_declaration(expression)
    
    # 替换变量
    parsed_value = substitute_vars(value, config)
    
    # 应用类型解析
    return type_parsers.get(type_prefix, str)(parsed_value) if type_prefix else parsed_value

@staticmethod
def _split_type_declaration(expression: str) -> Tuple[Optional[str], str]:
    """
    分离类型声明和实际值
    :return:（类型前缀，实际值）
    """
    if ":" not in expression or len(expression) < 3:
        return None, expression
        
    parts = expression.split(":", 1)
    return parts[0].strip().lower(), parts[1].strip()

# 性能优化的批量替换
def batch_substitute(
    templates: List[str],
    config: Dict[str, Any],
    max_depth: int = MAX_SUBSTITUTION_DEPTH
) -> List[str]:
    """
    批量替换模板列表
    :param templates: 模板字符串列表
    :return: 替换结果列表
    """
    engine = VariableEngine(config, max_depth)
    return [engine.safe_substitute(template) for template in templates]

def validate_template(
    template: str, 
    config: Dict[str, Any],
    pattern: str = DEFAULT_SUBSTITUTION_PATTERN
) -> Tuple[bool, list]:
    """
    验证模板中的变量是否全部定义
    :return: (是否验证通过, 未定义变量列表)
    """
    variables = extract_variables(template, pattern)
    undefined = [var for var in variables if var not in config]
    
    if not undefined:
        # 验证嵌套变量
        try:
            substituted = substitute_vars(template, config)
            # 确保没有未解析的变量
            unresolved_vars = extract_variables(substituted, pattern)
            return not bool(unresolved_vars), unresolved_vars
        except RuntimeError:
            return False, ["NESTED_ERROR"]
    
    return not bool(undefined), undefined

# 环境变量扩展支持
def expand_env_vars(template: str, include_system: bool = True) -> str:
    """
    扩展环境变量标记
    :param include_system: 是否包含系统环境变量
    :return: 已扩展的字符串
    """
    import os
    from string import Template
    
    result = template
    
    # 扩展类环境变量语法 %VARIABLE%
    result = re.sub(r"%([A-Za-z0-9_]+)%", 
                  lambda m: os.getenv(m.group(1), "") if include_system else "", 
                  result)
    
    # 扩展${VARIABLE}语法
    env_vars = os.environ.copy() if include_system else {}
    return Template(result).substitute(env_vars)

# 安全渲染器（防止错误泄露）
def secure_render(
    template: str, 
    config: Dict[str, Any], 
    sensitive_keywords: Tuple[str] = ("password", "secret", "token", "key")
) -> str:
    """
    安全渲染模板（过滤敏感信息）
    :return: 已渲染的安全字符串
    """
    # 创建安全配置副本
    safe_config = {}
    for key, value in config.items():
        if any(kw in key.lower() for kw in sensitive_keywords):
            safe_config[key] = "***REDACTED***"
        else:
            safe_config[key] = value
            
    return substitute_vars(template, safe_config, fallback="***UNDEFINED***")
