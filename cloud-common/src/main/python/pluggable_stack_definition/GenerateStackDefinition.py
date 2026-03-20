#!/usr/bin/env python3
"""
cloud堆栈生成�?- 企业级部署工�?
提供自动化堆栈定义生成能力，支持�?1. 多版本堆栈管�?2. 服务配置动态生�?3. XML/J2配置处理
4. 资源文件智能拷贝
5. 版本兼容性转�?
优化点：
- 代码结构重构
- 增强类型提示
- 添加详细日志
- 异常处理增强
- 性能优化
- 配置文件验证
"""

import sys
import getopt
import json
import os
import shutil
import re
import logging
import xml.etree.ElementTree as ET
from xml.dom import minidom
import random
import string
from typing import Dict, List, Tuple, Union, Any, Optional, Callable
from os.path import join, abspath, exists, dirname, basename, isdir

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 增强缓存
FILE_PROCESS_CACHE: Dict[str, str] = {}


class ConfigError(Exception):
    """配置相关异常"""
    pass


def generate_random_string(size: int = 7, 
                          chars: str = string.ascii_uppercase + string.digits) -> str:
    """生成随机字符�?""
    return "".join(random.choice(chars) for _ in range(size))


def validate_config(config: Dict) -> None:
    """验证配置完整�?""
    required_keys = {'baseStackName', 'stackName', 'versions'}
    if missing := required_keys - set(config.keys()):
        raise ConfigError(f'缺少必要配置�? {", ".join(missing)}')
    
    for idx, version in enumerate(config['versions']):
        if 'baseVersion' not in version:
            raise ConfigError(f'版本 {idx+1} 缺少 baseVersion 属�?)
        if 'version' not in version:
            raise ConfigError(f'版本 {idx+1} 缺少 version 属�?)
        
        for service in version.get('services', []):
            if 'name' not in service:
                raise ConfigError(f'服务定义缺少 name 属�?)


def copy_tree(src: str, 
              dest: str, 
              exclude: Optional[List] = None, 
              file_processor: Optional[Callable] = None) -> None:
    """
    增强型文件树复制
    
    :param src: 源目�?    :param dest: 目标目录
    :param exclude: 排除文件类型列表
    :param file_processor: 文件处理回调函数
    """
    if not exists(src):
        logger.warning("源目录不存在: %s", src)
        return

    exclude = exclude or []
    os.makedirs(dest, exist_ok=True)
    
    for root, dirs, files in os.walk(src):
        rel_path = os.path.relpath(root, src)
        target_dir = os.path.join(dest, rel_path)
        os.makedirs(target_dir, exist_ok=True)
        
        for file_name in files:
            if any(file_name.endswith(ext) for ext in exclude):
                continue
                
            src_path = os.path.join(root, file_name)
            dest_path = os.path.join(target_dir, file_name)
            
            try:
                shutil.copy2(src_path, dest_path)
                logger.debug("复制文件: %s �?%s", src_path, dest_path)
                
                if file_processor:
                    file_processor(dest_path)
            except Exception as e:
                logger.error("文件处理失败 [%s �?%s]: %s", 
                            src_path, dest_path, str(e))


def process_text_file(file_path: str, 
                     replacements: Dict, 
                     preserve: Optional[List] = None,
                     stack_version_changes: Optional[Dict] = None) -> bool:
    """处理文本文件替换"""
    try:
        # 使用缓存避免重复处理
        if file_path in FILE_PROCESS_CACHE:
            logger.debug("文件已处�?(使用缓存): %s", file_path)
            return True

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        preserve_map = {}
        for marker in preserve or []:
            rnd = generate_random_string()
            content = content.replace(marker, rnd)
            preserve_map[rnd] = marker

        # 自定义替�?        for pattern, repl in replacements.items():
            content = content.replace(pattern, repl)

        # 恢复保留文本
        for placehold, original in preserve_map.items():
            content = content.replace(placehold, original)

        # 重新写入文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        FILE_PROCESS_CACHE[file_path] = 'processed'
        logger.debug("文件处理成功: %s", file_path)
        return True
        
    except Exception as e:
        logger.error("处理文本文件失败 [%s]: %s", file_path, str(e))
        return False


def process_version_changes(text: str, 
                           base_version: str, 
                           target_version: str) -> str:
    """处理版本号格式变�?""
    # 普通格式替�?    result = text.replace(base_version, target_version)
    
    # 短横线格�?(x.y.z -> x-y-z)
    dash_base = base_version.replace(".", "-")
    dash_target = target_version.replace(".", "-")
    result = result.replace(dash_base, dash_target)
    
    # 下划线格�?(x.y.z -> x_y_z)
    underscore_base = base_version.replace(".", "_")
    underscore_target = target_version.replace(".", "_")
    result = result.replace(underscore_base, underscore_target)
    
    return result


def process_metainfo_xml(file_path: str, 
                        config_data: Dict, 
                        stack_version_changes: Dict,
                        common_services: List) -> bool:
    """处理metainfo.xml文件"""
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        # Stack metainfo处理
        if root.find('versions') or not root.find('services'):
            # 处理extends标签
            extends_tag = root.find('extends')
            if extends_tag and extends_tag.text in stack_version_changes:
                extends_tag.text = stack_version_changes[extends_tag.text]
            
            # 处理active标签
            current_version = os.sep.join(file_path.split(os.sep)[-3:-2])
            for stack in config_data.get('versions', []):
                if stack['version'] == current_version and 'active' in stack:
                    versions_tag = root.find('versions') or ET.SubElement(root, 'versions')
                    active_tag = versions_tag.find('active') or ET.SubElement(versions_tag, 'active')
                    active_tag.text = stack['active']
        else:
            # Service metainfo处理
            for service in root.findall('services/service'):
                name = service.find('name').text
                path_components = file_path.split(os.sep)
                path_version = path_components[-4] if len(path_components) >= 4 else ""
                
                # 更新服务版本
                version_tag = service.find('version')
                for stack in config_data.get('versions', []):
                    if stack['version'] == path_version:
                        for svc in stack.get('services', []):
                            if svc['name'] == name and 'version' in svc:
                                version_tag.text = svc['version'] if version_tag else ""
                
                # 更新包版�?                for packages_tag in service.findall('.//packages'):
                    for package_tag in packages_tag.findall('package'):
                        name_tag = package_tag.find('name')
                        if name_tag:
                            name_tag.text = process_version_changes(
                                name_tag.text, 
                                config_data['baseStackName'], 
                                config_data['stackName']
                            )
        
        tree.write(file_path)
        return True
    except Exception as e:
        logger.error("处理 metainfo.xml 失败 [%s]: %s", file_path, str(e))
        return False


class StackGenerator:
    """cloud堆栈生成�?""

    def __init__(self, config_file: str, resources_dir: str, output_dir: str):
        self.config_file = config_file
        self.resources_dir = resources_dir
        self.output_dir = output_dir
        self.config_data = self._load_config()
        self.stack_version_changes = self._build_version_map()
        self.common_services = []

    def _load_config(self) -> Dict:
        """加载并验证配置文�?""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            validate_config(config)
            logger.info("配置文件验证成功")
            return config
        except Exception as e:
            logger.exception("配置文件加载失败")
            raise

    def _build_version_map(self) -> Dict[str, str]:
        """构建版本号映射字�?""
        return {
            stack['baseVersion']: stack['version']
            for stack in self.config_data['versions']
            if stack['version'] != stack['baseVersion']
        }

    def generate(self) -> None:
        """生成堆栈定义"""
        try:
            self._copy_stacks()
            self._copy_common_services()
            self._copy_remaining_common_services()
            self._copy_resource_management()
            self._copy_cloud_properties()
            self._copy_custom_actions()
            logger.info("堆栈生成完成: %s", self.output_dir)
        except Exception as e:
            logger.exception("堆栈生成失败")
            raise

    def _get_file_processor(self, file_type: str = None) -> Callable:
        """获取文件处理器工�?""
        processors = {
            'metainfo.xml': lambda path: process_metainfo_xml(
                path, self.config_data, self.stack_version_changes, self.common_services
            ),
            '.xml': lambda path: process_text_file(
                path,
                replacements=self.config_data.get('textReplacements', {}),
                preserve=self.config_data.get('preservedText', []),
                stack_version_changes=self.stack_version_changes
            ),
            '.py': lambda path: process_text_file(
                path,
                replacements={
                    **self.config_data.get('textReplacements', {}),
                    self.config_data['baseStackName'].lower(): 
                        self.config_data['stackName'].lower(),
                    self.config_data['baseStackName']: 
                        self.config_data['stackName']
                },
                preserve=self.config_data.get('preservedText', []),
                stack_version_changes=self.stack_version_changes
            ),
            'default': lambda path: process_text_file(
                path,
                replacements=self.config_data.get('textReplacements', {}),
                preserve=self.config_data.get('preservedText', []),
                stack_version_changes=self.stack_version_changes
            )
        }
        
        def processor(file_path: str) -> None:
            """智能文件处理�?""
            # 特殊文件处理
            if basename(file_path) == 'metainfo.xml':
                processors['metainfo.xml'](file_path)
                return
                
            # 按文件类型处�?            for ext in ['.xml', '.py', '.j2', '.sh', '.properties']:
                if file_path.endswith(ext):
                    if ext == '.xml' and 'configuration' in file_path:
                        self._process_config_xml(file_path)
                    elif ext == '.py' and 'stack_advisor.py' in file_path:
                        self._process_stack_advisor(file_path)
                    else:
                        processors.get(ext, processors['default'])(file_path)
                    return
                    
            # 默认处理�?            processors['default'](file_path)
        
        return processor

    def _process_config_xml(self, file_path: str) -> None:
        """处理配置XML文件"""
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()

            # 解析文件路径获取上下文信�?            path_components = file_path.split(os.sep)
            
            # 在堆栈目�? stacks/<stack_name>/<stack_version>/configuration/
            if 'stacks' in path_components and 'configuration' in path_components:
                stack_idx = path_components.index('stacks') + 1
                config_idx = path_components.index('configuration')
                
                stack_name = path_components[stack_idx]
                stack_version = path_components[stack_idx + 1]
                config_name = basename(file_path).split('.')[0]
                
                # 应用堆栈级别配置
                self._apply_stack_level_config(root, stack_version, config_name)
            
            # 在服务目�? stacks/<stack_name>/<stack_version>/services/<service_name>/configuration/
            elif 'services' in path_components and 'configuration' in path_components:
                service_idx = path_components.index('services') + 1
                stack_idx = path_components.index('stacks') + 1
                config_idx = path_components.index('configuration')
                
                stack_name = path_components[stack_idx]
                stack_version = path_components[stack_idx + 1]
                service_name = path_components[service_idx]
                config_name = basename(file_path).split('.')[0]
                
                # 应用服务级别配置
                self._apply_service_level_config(root, stack_version, service_name, config_name)

            tree.write(file_path)
        except Exception as e:
            logger.error("处理配置XML失败 [%s]: %s", file_path, str(e))

    def _apply_stack_level_config(self, root: ET.Element, 
                                stack_version: str, config_name: str) -> None:
        """应用堆栈级别配置"""
        stack_config = next((
            stack for stack in self.config_data.get('versions', []) 
            if stack['version'] == stack_version
        ), None)
        
        if not stack_config:
            return
            
        config_def = next((
            conf for conf in stack_config.get('configurations', [])
            if conf['name'] == config_name
        ), None)
        
        if not config_def:
            return
            
        for prop in root.findall('property'):
            name = prop.find('name').text
            value = prop.find('value')
            if name in config_def.get('properties', {}):
                value.text = config_def['properties'][name]

    def _apply_service_level_config(self, root: ET.Element, 
                                   stack_version: str, 
                                   service_name: str, 
                                   config_name: str) -> None:
        """应用服务级别配置"""
        stack_config = next((
            stack for stack in self.config_data.get('versions', []) 
            if stack['version'] == stack_version
        ), None)
        
        if not stack_config:
            return
            
        service_def = next((
            svc for svc in stack_config.get('services', [])
            if svc['name'] == service_name
        ), None)
        
        if not service_def:
            return
            
        config_def = next((
            conf for conf in service_def.get('configurations', [])
            if conf['name'] == config_name
        ), None)
        
        if not config_def:
            return
            
        for prop in root.findall('property'):
            name = prop.find('name').text
            value = prop.find('value')
            if name in config_def.get('properties', {}):
                value.text = config_def['properties'][name]

    def _copy_stacks(self) -> None:
        """复制和转换堆栈定�?""
        base_stack_dir = join(self.resources_dir, 'stacks', self.config_data['baseStackName'])
        target_stack_base = join(self.output_dir, 'stacks', self.config_data['stackName'])
        
        for stack in self.config_data.get('versions', []):
            base_version_dir = join(base_stack_dir, stack['baseVersion'])
            target_version_dir = join(target_stack_base, stack['version'])
            
            # 确定需要排除的服务
            desired_services = {svc['name'] for svc in stack.get('services', [])}
            existing_services = os.listdir(join(base_version_dir, 'services')) if exists(base_version_dir) else []
            services_to_exclude = set(existing_services) - desired_services
            exclude_patterns = ['.pyc'] + [f"services/{svc}" for svc in services_to_exclude]
            
            # 复制文件�?            copy_tree(
                src=base_version_dir,
                dest=target_version_dir,
                exclude=exclude_patterns,
                file_processor=self._get_file_processor()
            )
            
            # 处理目标版本特定覆盖
            version_override_dir = join(self.resources_dir, 'stacks', 
                                      self.config_data['stackName'], stack['version'])
            
            if exists(version_override_dir):
                logger.info("应用版本覆盖: %s", version_override_dir)
                copy_tree(
                    src=version_override_dir,
                    dest=target_version_dir,
                    exclude=['.pyc'],
                    file_processor=self._get_file_processor()
                )
                
            # 复制stack_advisor.py
            stack_advisor_src = join(self.resources_dir, 'stacks', 'stack_advisor.py')
            stack_advisor_dest = join(dirname(target_stack_base), 'stack_advisor.py')
            
            if exists(stack_advisor_src):
                shutil.copy2(stack_advisor_src, stack_advisor_dest)
                logger.debug("复制stack_advisor: %s �?%s", stack_advisor_src, stack_advisor_dest)
                self._get_file_processor()(stack_advisor_dest)

    def _copy_common_services(self) -> None:
        """复制通用服务定义"""
        if not self.common_services:
            logger.info("没有通用服务需要复�?)
            return
            
        for svc_path in set(self.common_services):  # 去重
            source_dir = join(self.resources_dir, svc_path)
            target_dir = join(self.output_dir, svc_path)
            
            if exists(source_dir):
                logger.info("复制通用服务: %s", svc_path)
                copy_tree(
                    src=source_dir,
                    dest=target_dir,
                    exclude=['.pyc'],
                    file_processor=self._get_file_processor()
                )
            else:
                logger.warning("通用服务路径不存�? %s", source_dir)

    def _copy_remaining_common_services(self) -> None:
        """复制剩余通用服务"""
        source_base = join(self.resources_dir, 'common-services')
        dest_base = join(self.output_dir, 'common-services')
        
        if not exists(source_base):
            return
            
        processed_services = {basename(svc) for svc in self.common_services}
        
        for service_name in os.listdir(source_base):
            if service_name in processed_services:
                continue
                
            source_dir = join(source_base, service_name)
            dest_dir = join(dest_base, service_name)
            
            if exists(source_dir):
                logger.info("复制剩余通用服务: %s", service_name)
                copy_tree(
                    src=source_dir,
                    dest=dest_dir,
                    exclude=['.pyc'],
                    file_processor=self._get_file_processor()
                )

    def _copy_resource_management(self) -> None:
        """复制资源管理代码"""
        try:
            # 计算source目录
            source_dir = abspath(join(
                self.resources_dir, '..', '..', '..', '..',
                'cloud-common', 'src', 'main', 'python', 'resource_management'
            ))
            
            # 计算target目录
            target_dir = join(self.output_dir, 'python', 'resource_management')
            
            if exists(source_dir):
                logger.info("复制资源管理模块")
                copy_tree(
                    src=source_dir,
                    dest=target_dir,
                    exclude=['.pyc'],
                    file_processor=self._get_file_processor()
                )
            else:
                logger.warning("资源管理模块目录不存�? %s", source_dir)
        except Exception as e:
            logger.error("复制资源管理模块失败: %s", str(e))

    def _copy_cloud_properties(self) -> None:
        """生成cloud.properties文件"""
        try:
            source_path = abspath(join(
                self.resources_dir, '..', '..', '..', '..',
                'cloud-server', 'conf', 'unix', 'cloud.properties'
            ))
            
            target_dir = join(self.output_dir, 'conf', 'unix')
            target_path = join(target_dir, 'cloud.properties')
            
            if not exists(source_path):
                logger.warning("cloud.properties源文件不存在: %s", source_path)
                return
                
            os.makedirs(target_dir, exist_ok=True)
            
            prop_map = self.config_data.get('cloudProperties', {})
            processed_props = []
            
            with open(source_path, 'r', encoding='utf-8') as src,  \
                 open(target_path, 'w', encoding='utf-8') as dest:
                
                for line in src:
                    stripped = line.strip()
                    if not stripped or stripped.startswith('#'):
                        dest.write(line)
                        continue
                    
                    if '=' in stripped:
                        key, orig_value = map(str.strip, stripped.split('=', 1))
                        
                        # 应用配置覆盖
                        if key in prop_map:
                            new_value = prop_map[key]
                            processed_props.append(key)
                            dest.write(f"{key} = {new_value}\n")
                        else:
                            dest.write(line)
                    else:
                        dest.write(line)
                
                # 添加新配置项
                for key, value in prop_map.items():
                    if key not in processed_props:
                        dest.write(f"\n{key} = {value}\n")
            
            logger.info("生成cloud.properties文件: %s", target_path)
        
        except Exception as e:
            logger.error("处理cloud.properties失败: %s", str(e))

    def _copy_custom_actions(self) -> None:
        """复制自定义操�?""
        source_dir = join(self.resources_dir, 'custom_actions')
        target_dir = join(self.output_dir, 'custom_actions')
        
        if exists(source_dir):
            logger.info("复制自定义操�?)
            copy_tree(
                src=source_dir,
                dest=target_dir,
                exclude=['.pyc'],
                file_processor=self._get_file_processor()
            )
        else:
            logger.warning("自定义操作目录不存在: %s", source_dir)

    def _process_stack_advisor(self, file_path: str) -> None:
        """特殊处理stack_advisor.py"""
        pattern = r"([A-Za-z]+)(\d+)StackAdvisor"
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            replacements = []
            for match in re.finditer(pattern, content):
                class_base, class_version = match.groups()
                version_dotted = ".".join(class_version)
                
                if version_dotted in self.stack_version_changes:
                    new_version = self.stack_version_changes[version_dotted].replace('.', '')
                    new_class = f"{self.config_data['stackName']}{new_version}StackAdvisor"
                    replacements.append((match.group(), new_class))
            
            # 执行全部替换
            for old, new in replacements:
                content = content.replace(old, new)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.debug("处理stack_advisor: %s", file_path)
        
        except Exception as e:
            logger.error("处理stack_advisor失败 [%s]: %s", file_path, str(e))


def main(argv: List[str]) -> None:
    """主程序入�?""
    help_msg = "用法: generate_stack_definition.py -c <config.json> -r <resources_dir> -o <output_dir>"
    
    config_file = ""
    resources_dir = ""
    output_dir = ""
    
    try:
        opts, args = getopt.getopt(argv, "hc:r:o:", ["config=", "resources=", "output="])
    except getopt.GetoptError:
        print(help_msg)
        sys.exit(2)
    
    for opt, arg in opts:
        if opt == '-h':
            print(help_msg)
            sys.exit(0)
        elif opt in ("-c", "--config"):
            config_file = arg
        elif opt in ("-r", "--resources"):
            resources_dir = arg
        elif opt in ("-o", "--output"):
            output_dir = arg
    
    if not all([config_file, resources_dir, output_dir]):
        print("错误: 必须提供所有参�?)
        print(help_msg)
        sys.exit(2)
    
    try:
        logger.info("启动堆栈生成")
        logger.info("配置: %s", config_file)
        logger.info("资源: %s", resources_dir)
        logger.info("输出: %s", output_dir)
        
        generator = StackGenerator(config_file, resources_dir, output_dir)
        generator.generate()
        
        logger.info("堆栈生成成功完成")
    except Exception as e:
        logger.critical("堆栈生成失败: %s", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
