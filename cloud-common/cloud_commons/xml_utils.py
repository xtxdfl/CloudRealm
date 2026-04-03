#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import inspect
import sys
import html
import re
from typing import (
    Any, 
    Dict, 
    List, 
    Tuple, 
    Callable, 
    Union,
    Iterable,
    Optional,
    TYPE_CHECKING
)
from xml.etree.ElementTree import Element, tostring
from xml.dom import minidom
from functools import lru_cache
import logging

if TYPE_CHECKING:
    from types import ModuleType

__all__ = ['XmlSerializable', 'xml_serializable', 'XmlConversionError']

# 配置日志
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('XmlSerializer')

class XmlConversionError(Exception):
    """XML 转换错误"""
    pass

class XmlMetaOptions:
    """控制 XML 序列化行为的元选项类"""
    __slots__ = (
        'exclude_fields', 
        'include_fields',
        'field_names',
        'field_formatters',
        'xml_namespace',
        'namespace_prefix',
        'xml_version',
        'xml_encoding',
        'pretty_print',
        'skip_none',
        'custom_root',
        'xml_declaration'
    )

    def __init__(self, **kwargs):
        """
        初始化 XML 元选项
        
        参数:
            exclude_fields: 要排除的字段名列表
            include_fields: 要包含的字段名列表 (默认为所有字段)
            field_names: 字段名映射字典 {字段名: XML标签名}
            field_formatters: 字段格式函数映射 {字段名: 格式化函数}
            xml_namespace: XML命名空间URI
            namespace_prefix: 命名空间前缀
            xml_version: XML版本 (默认1.0)
            xml_encoding: XML编码 (默认UTF-8)
            pretty_print: 是否美化输出
            skip_none: 是否跳过空值字段
            custom_root: 自定义根元素名
            xml_declaration: 是否包含XML声明
        """
        # 初始化默认值
        self.exclude_fields = kwargs.get('exclude_fields', [])
        self.include_fields = kwargs.get('include_fields', None)
        self.field_names = kwargs.get('field_names', {})
        self.field_formatters = kwargs.get('field_formatters', {})
        self.xml_namespace = kwargs.get('xml_namespace', None)
        self.namespace_prefix = kwargs.get('namespace_prefix', None)
        self.xml_version = kwargs.get('xml_version', '1.0')
        self.xml_encoding = kwargs.get('xml_encoding', 'UTF-8')
        self.pretty_print = kwargs.get('pretty_print', True)
        self.skip_none = kwargs.get('skip_none', False)
        self.custom_root = kwargs.get('custom_root', None)
        self.xml_declaration = kwargs.get('xml_declaration', True)


def xml_serializable(**options):
    """
    类装饰器，将类标记为可序列化为 XML
    
    参数:
        options: XmlMetaOptions 参数
        
    返回:
        装饰器函数
    """
    def decorator(cls):
        # 将元选项附加到类上
        setattr(cls, '_xml_meta', XmlMetaOptions(**options))
        return cls
    return decorator


class XmlSerializable:
    """
    强大的 XML 序列化基类
    
    特征:
      - 自动检测公共属性
      - 支持嵌套对象序列化
      - 自定义字段名和格式化
      - XML 命名空间支持
      - 多种输出格式
      - 元数据配置
      - 安全值转义
    
    用法:
      class Person(XmlSerializable):
          def __init__(self, name, age):
              self.name = name
              self.age = age
              
      person = Person("Alice", 30)
      print(person.to_xml())
    """
    
    XML_META_OPTIONS = '_xml_meta'
    
    @lru_cache(maxsize=128)
    def get_xml_fields(self) -> List[str]:
        """
        获取应包含在 XML 中的字段列表
        (带缓存优化)
        
        返回:
            应序列化的字段名列表
        """
        # 获取元选项
        meta = getattr(self, self.XML_META_OPTIONS, None)
        
        # 获取实例属性
        instance_members = list(vars(self).keys())
        
        # 使用反射获取类的公共属性
        members = [
            name for name, obj in inspect.getmembers(self)
            if not name.startswith('__') and not inspect.isroutine(obj) 
            and name in instance_members  # 确保是实例属性
        ]
        
        # 应用包含/排除规则
        if meta:
            if meta.include_fields is not None:
                # 过滤包含列表
                members = [name for name in members if name in meta.include_fields]
            
            if meta.exclude_fields:
                # 过滤排除列表
                members = [name for name in members if name not in meta.exclude_fields]
        
        return members

    def to_xml(self, root_tag: Optional[str] = None, meta: Optional[XmlMetaOptions] = None) -> str:
        """
        将对象序列化为 XML 字符串
        
        参数:
            root_tag: 自定义根标签
            meta: 自定义元选项
            
        返回:
            XML 字符串
        """
        # 创建 XML 元素
        element = self._to_xml_element(meta=meta, root_tag=root_tag)
        
        # 获取元选项
        use_meta = meta or getattr(self, self.XML_META_OPTIONS, None)
        
        # 生成 XML 字符串
        xml_string = tostring(element, 
                             encoding=use_meta.xml_encoding if use_meta else 'UTF-8',
                             method='xml' if (use_meta and use_meta.xml_declaration) else 'xml')
        
        # 美化输出
        if self._should_pretty_print(meta):
            xml_string = self._pretty_print_xml(xml_string)
        
        return xml_string
    
    def to_element(self, meta: Optional[XmlMetaOptions] = None) -> Element:
        """
        将对象转换为 XML 元素
        
        参数:
            meta: 自定义元选项
            
        返回:
            Element 对象
        """
        return self._to_xml_element(meta=meta)

    def to_dom(self, meta: Optional[XmlMetaOptions] = None) -> minidom.Document:
        """
        将对象转换为 minidom Document
        
        参数:
            meta: 自定义元选项
            
        返回:
            minidom 文档对象
        """
        element = self._to_xml_element(meta=meta)
        doc = minidom.Document()
        doc.appendChild(doc.importNode(element, deep=True))
        return doc

    def to_dict(self, meta: Optional[XmlMetaOptions] = None) -> Dict[str, Any]:
        """
        将对象转换为字典 (包含原始值)
        
        参数:
            meta: 自定义元选项
            
        返回:
            包含属性值的字典
        """
        fields = self.get_xml_fields()
        return {field: getattr(self, field) for field in fields}

    def _to_xml_element(self, meta: Optional[XmlMetaOptions] = None, root_tag: Optional[str] = None) -> Element:
        """
        内部方法: 创建 XML 元素
        
        参数:
            meta: 自定义元选项
            root_tag: 自定义根标签名
            
        返回:
            Element 对象
        """
        # 获取元选项 (优先使用传入的)
        use_meta = meta or getattr(self, self.XML_META_OPTIONS, None)
        
        # 创建根元素
        root_name = root_tag or use_meta.custom_root if use_meta and use_meta.custom_root else self._get_default_root_tag()
        
        # 处理命名空间
        namespaces = {}
        namespace_prefix = None
        
        if use_meta and use_meta.xml_namespace:
            if use_meta.namespace_prefix:
                namespace_prefix = use_meta.namespace_prefix
                root_name = f"{namespace_prefix}:{root_name}"
                namespaces = {namespace_prefix: use_meta.xml_namespace}
            else:
                namespaces = {'': use_meta.xml_namespace}
        
        root = Element(root_name, **namespaces) if namespaces else Element(root_name)
        
        # 处理命名空间属性
        if use_meta and use_meta.xml_namespace and not use_meta.namespace_prefix:
            root.set('xmlns', use_meta.xml_namespace)
        
        # 添加子元素
        fields = self.get_xml_fields()
        
        for field in fields:
            value = getattr(self, field)
            
            # 检查是否跳过空值
            if use_meta and use_meta.skip_none and value is None:
                continue
                
            # 获取字段标签名
            key = self._get_xml_field_name(field, use_meta)
            
            # 自定义格式化
            formatter = self._get_field_formatter(field, use_meta)
            if formatter:
                value = formatter(value)
            
            # 特殊处理嵌套的 XmlSerializable
            if isinstance(value, XmlSerializable):
                root.append(value.to_element(meta))
            # 处理字典
            elif isinstance(value, dict):
                dict_elem = self._create_element_for_dict(key, value)
                root.append(dict_elem)
            # 处理列表
            elif isinstance(value, list) or isinstance(value, tuple) or isinstance(value, set):
                list_elem = self._create_element_for_list(key, value)
                root.append(list_elem)
            else:
                # 转义值并设置文本
                elem = Element(key)
                if value is not None:
                    elem.text = self._escape_value(value)
                root.append(elem)
                
        return root

    def _create_element_for_dict(self, key: str, data: Dict) -> Element:
        """
        为字典创建 XML 元素
        
        参数:
            key: 元素键名
            data: 字典数据
            
        返回:
            Element 对象
        """
        elem = Element(key)
        for k, v in data.items():
            # 键名需要是合法的 XML 标签名
            sanitized_key = self._sanitize_xml_key(k)
            
            if isinstance(v, dict):
                child = self._create_element_for_dict(sanitized_key, v)
                elem.append(child)
            elif isinstance(v, list):
                child = self._create_element_for_list(sanitized_key, v)
                elem.append(child)
            else:
                child = Element(sanitized_key)
                if v is not None:
                    child.text = self._escape_value(v)
                elem.append(child)
        return elem

    def _create_element_for_list(self, key: str, items: Iterable) -> Element:
        """
        为列表创建 XML 元素
        
        参数:
            key: 元素名称 (用于包装)
            items: 可迭代对象
            
        返回:
            Element 对象
        """
        # 包装元素
        wrapper = Element(key)
        
        # 为每个子项创建元素
        for index, item in enumerate(items):
            if isinstance(item, dict):
                child = self._create_element_for_dict(f"{self._sanitize_xml_key(key)}_item", item)
                wrapper.append(child)
            elif isinstance(item, (list, tuple, set)):
                # 嵌套列表处理
                child = self._create_element_for_list(f"{self._sanitize_xml_key(key)}_list", item)
                wrapper.append(child)
            elif isinstance(item, XmlSerializable):
                # 嵌套的可序列化对象
                wrapper.append(item.to_element())
            else:
                # 创建简单项元素 (使用基于索引的名称)
                elem = Element(f"{self._sanitize_xml_key(key)}_item_{index}")
                if item is not None:
                    elem.text = self._escape_value(item)
                wrapper.append(elem)
                
        return wrapper

    def _escape_value(self, value: Any) -> str:
        """
        安全转义 XML 值
        
        参数:
            value: 要转义的值
            
        返回:
            转义后的字符串
        """
        if not isinstance(value, str):
            value = str(value)
        
        # 避免二次转义
        if self._is_escaped(value):
            return value
            
        return html.escape(value, quote=True)

    @staticmethod
    def _is_escaped(text: str) -> bool:
        """检查文本是否已经被转义"""
        return any(entity in text for entity in ['&amp;', '&lt;', '&gt;', '&quot;', '&#39;'])

    @staticmethod
    def _sanitize_xml_key(key: str) -> str:
        """清理 XML 键名，确保有效字符集"""
        if not key:
            return "empty"
        
        # 清理无效字符
        sanitized = re.sub(r'[^\w\s-]', '', key)
        
        # XML 元素必须以字母或下划线开头
        if not sanitized or not sanitized[0].isalpha():
            sanitized = f"field_{sanitized}"
            
        # 替换空格
        sanitized = re.sub(r'\s+', '_', sanitized)
        
        # Python关键字保留字过滤
        if sanitized in dir(__builtins__) or keyword.iskeyword(sanitized):
            return f"{sanitized}_value"
            
        return sanitized

    def _get_xml_field_name(self, field: str, meta: XmlMetaOptions = None) -> str:
        """
        获取字段的 XML 标签名
        
        参数:
            field: 原始字段名
            meta: 元选项
            
        返回:
            XML 标签名
        """
        # 检查字段名映射
        if meta and field in meta.field_names:
            return meta.field_names[field]
            
        # 默认为清理版字段名
        return self._sanitize_xml_key(field)

    def _get_field_formatter(self, field: str, meta: XmlMetaOptions = None) -> Optional[Callable]:
        """
        获取字段的格式化函数
        
        参数:
            field: 字段名
            meta: 元选项
            
        返回:
            格式化函数 或 None
        """
        if meta and field in meta.field_formatters:
            return meta.field_formatters[field]
        return None

    def _get_default_root_tag(self) -> str:
        """
        获取默认根元素标签
        
        返回:
            XML 根元素名称
        """
        # 默认使用类名
        class_name = self.__class__.__name__
        
        # 移除不必要的后缀
        if class_name.endswith('Config'):
            class_name = class_name[:-6]
        elif class_name.endswith('Settings'):
            class_name = class_name[:-8]
            
        # 转换为蛇形命名
        words = re.findall(r'[A-Z][a-z0-9]*', class_name)
        if words:
            root_name = '_'.join(words).lower()
            # 移除可能的重复后缀
            if root_name.endswith('_xml') or root_name.endswith('_serializable'):
                root_name = root_name.rsplit('_', 1)[0]
            return root_name
        
        return 'root'

    def _should_pretty_print(self, meta: Optional[XmlMetaOptions]) -> bool:
        """是否应该美化打印 XML"""
        return (meta and meta.pretty_print) or (getattr(meta, 'pretty_print', False))

    @staticmethod
    def _pretty_print_xml(xml_string: bytes) -> str:
        """美化 XML 格式输出"""
        try:
            # 使用 minidom 美化输出
            parsed = minidom.parseString(xml_string)
            return parsed.toprettyxml(encoding='utf-8').decode('utf-8')
        except Exception as e:
            logger.warning(f"美化 XML 失败: {str(e)}")
            # 尝试简单缩进
            try:
                from xml.sax.saxutils import escape
                dom = minidom.parseString(xml_string)
                return ''.join(dom.toprettyxml(indent='  ').splitlines(keepends=True))
            except:
                return xml_string.decode('utf-8')


def autogenerate_xml_classes(base_class: XmlSerializable, data_dict: Dict) -> Union[XmlSerializable, Type[XmlSerializable]]:
    """
    动态生成 XML 序列化类
    
    参数:
        base_class: 基类 (通常为 XmlSerializable)
        data_dict: 包含初始数据的字典
        
    返回:
        配置好的 XmlSerializable 实例或新类
    """
    fields = {key: type(value) for key, value in data_dict.items()}
    
    # 动态创建类
    class_name = "DynamicallyGeneratedXmlClass"
    if 'class' in data_dict and isinstance(data_dict['class'], str):
        class_name = data_dict['class']
        
    cls = type(class_name, (base_class,), {'__init__': _dynamic_init, '_fields': fields})
    
    # 创建实例
    return cls(**data_dict)

def _dynamic_init(self, **kwargs):
    """动态初始化函数"""
    for key, value in kwargs.items():
        setattr(self, key, value)


# =============== XML 序列化示例用例 ===============

@xml_serializable(
    exclude_fields=['sensitive_info'],
    field_names={'name': 'full_name', 'age': 'years'},
    field_formatters={'join_date': lambda d: d.strftime('%Y-%m-%d')},
    skip_none=True
)
class Employee(XmlSerializable):
    """员工信息类，展示 XML 序列化能力"""
    
    def __init__(self, name: str, position: str, department: str, salary: int, 
                 skills: list, projects: dict, join_date: Any, age: int = None):
        self.name = name
        self.position = position
        self.department = department
        self.salary = salary
        self.skills = skills
        self.projects = projects
        self.join_date = join_date
        self.age = age
        self.sensitive_info = "DO NOT SHARE: 123-45-6789"  # 敏感信息，应被排除


@xml_serializable(
    field_names={'title': 'project_name', 'duration': 'timeline'},
    pretty_print=True
)
class Project(XmlSerializable):
    """项目信息类，展示嵌套序列化能力"""
    
    def __init__(self, title: str, status: str, duration: int):
        self.title = title
        self.status = status
        self.duration = duration


def generate_example_employee() -> Employee:
    """创建示例员工数据"""
    import datetime
    
    # 创建嵌套项目
    alpha_project = Project("Alpha Launch", "Completed", 6)
    beta_project = Project("Beta Development", "In Progress", 3)
    
    # 员工技能
    skills = ["Python", "Data Analysis", "Team Leadership"]
    
    # 项目贡献
    projects = {
        "Alpha": alpha_project,
        "Beta": beta_project
    }
    
    return Employee(
        name="Jane Smith",
        position="Senior Developer",
        department="Engineering",
        salary=120000,
        skills=skills,
        projects=projects,
        age=35,
        join_date=datetime.date(2018, 5, 15)
    )


def dynamic_example():
    """动态创建可序列化类示例"""
    # 示例数据结构
    profile_data = {
        'username': 'johndoe',
        'email': 'john@example.com',
        'preferences': {
            'theme': 'dark',
            'notifications': True,
            'language': 'en-US'
        },
        'subscriptions': ['newsletter', 'promotions', 'updates'],
        'last_login': '2023-06-15T08:45:22Z'
    }
    
    # 动态创建 XML 序列化类
    UserProfile = autogenerate_xml_classes(XmlSerializable, profile_data)
    
    # 创建序列化实例
    xml_output = UserProfile().to_xml()
    
    print("\n动态生成的 XML:")
    print(xml_output)


if __name__ == "__main__":
    # 创建员工实例
    employee = generate_example_employee()
    
    # 输出原始 XML
    print("员工 XML 表示:")
    print(employee.to_xml())
    
    # 输出为 DOM 对象
    print("\n员工 XML DOM:")
    doc = employee.to_dom()
    print(doc.toprettyxml())
    
    # 输出为字典
    print("\n员工数据字典:")
    print(employee.to_dict())
    
    # 动态类示例
    dynamic_example()
