#!/usr/bin/env python3
"""
高级仓库信息处理器

功能概述：
本脚本用于自动化处理仓库元数据，主要功能包括：
1. 从本地或远程URL加载仓库版本信息
2. 智能匹配仓库版本与对应的仓库配置文件
3. 按操作系统家族分类处理仓库URL
4. 安全更新XML格式的仓库配置文件

主要优点：
- 支持本地和远程仓库元数据
- 智能处理操作系统家族映射
- 完整的XML处理
- 详细的日志跟踪
- 强大的命令行参数处理

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

import argparse
import sys
import os
import json
import logging
import urllib.request
import urllib.error
import urllib.parse
import re
from pathlib import Path
from xml.etree import ElementTree as ET
from typing import Dict, Tuple, List, Optional, Any

# 配置高级日志系统
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)8s | %(module)15s:%(lineno)3d | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('repo-processor')

# 预编译正则表达式提高性能
STACK_VERSION_REGEX = re.compile(r"(\S*)-((\d\.*)+)")

# 操作系统家族映射（处理不同发行版的兼容性）
OS_FAMILY_MAP = {
    "redhat6": "centos6",
    "redhat7": "centos7",
    "rhel6": "centos6",
    "rhel7": "centos7",
    "amazon": "centos7"
}

# XML头部模板
XML_HEADER = """<?xml version="1.0"?>
<!--
   Licensed to the Apache Software Foundation (ASF) under one or more
   contributor license agreements.  See the NOTICE file distributed with
   this work for additional information regarding copyright ownership.
   The ASF licenses this file to You under the Apache License, Version 2.0
   (the "License"); you may not use this file except in compliance with
   the License.  You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
-->
"""


class RepositoryManager:
    """
    仓库信息管理器，提供处理仓库配置的核心功能
    
    功能:
      - 加载JSON配置（支持本地和远程）
      - 解析仓库版本信息
      - 查找并更新XML仓库配置文件
      - 处理操作系统家族映射
    """
    
    def __init__(self, urlinfo_path: str, stack_folder: str, dry_run: bool = False):
        """
        初始化仓库管理器
        
        参数:
            urlinfo_path: 存储仓库URL信息的JSON路径
            stack_folder: 包含仓库配置文件的根文件夹
            dry_run: 是否执行模拟运行
        """
        self.urlinfo_path = urlinfo_path
        self.stack_folder = Path(stack_folder)
        self.dry_run = dry_run
        self.repo_info_cache: Dict[Tuple, Any] = {}
        
        # 验证路径
        if not self.stack_folder.exists() or not self.stack_folder.is_dir():
            raise ValueError(f"堆栈文件夹无效: {stack_folder}")
        
        logger.info(f"使用仓库配置源: {self.urlinfo_path}")
        logger.info(f"目标堆栈文件夹: {self.stack_folder.resolve()}")
        
    def safe_get_json_content(self) -> Dict:
        """
        安全获取JSON内容，支持本地路径和URL
        
        返回:
            JSON解析后的字典内容
            
        异常:
            ValueError: 当无法获取或解析内容时
        """
        try:
            # 尝试作为URL处理
            if self.urlinfo_path.startswith(('http://', 'https://')):
                logger.info(f"从远程URL提取仓库信息: {self.urlinfo_path}")
                with urllib.request.urlopen(self.urlinfo_path) as response:
                    return json.load(response)
            
            # 作为本地文件处理
            file_path = Path(self.urlinfo_path)
            if file_path.exists() and file_path.is_file():
                logger.info(f"从本地文件加载仓库信息: {file_path.resolve()}")
                with file_path.open('r', encoding='utf-8') as f:
                    return json.load(f)
        
        except urllib.error.URLError as e:
            logger.error(f"无法访问仓库URL: {self.urlinfo_path} | 错误: {str(e)}")
            raise ValueError(f"无效URL或无法连接: {self.urlinfo_path}") from e
        
        except FileNotFoundError:
            logger.error(f"仓库文件不存在: {self.urlinfo_path}")
            raise ValueError(f"文件不存在: {self.urlinfo_path}")
        
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            raise ValueError("无效的JSON格式") from e
        
        except Exception as e:
            logger.exception("加载仓库信息时发生意外错误")
            raise
        
        logger.error(f"无法识别仓库配置源类型: {self.urlinfo_path}")
        raise ValueError("不支持的仓库配置源类型")
    
    def process_repo_mappings(self) -> None:
        """
        处理仓库配置的主要入口点
        """
        try:
            # 获取仓库信息
            repo_data = self.safe_get_json_content()
            logger.info(f"成功加载仓库信息，包含 {len(repo_data)} 个仓库")
            
            # 解析仓库映射
            repo_mappings = self.parse_repo_data(repo_data)
            logger.info(f"解析了 {len(repo_mappings)} 个仓库映射")
            
            # 根据版本处理仓库
            for (stack_version, repo_id), repo_info in repo_mappings.items():
                self.process_repo_with_version(stack_version, repo_id, repo_info)
            
            logger.success("仓库处理完成")
            
        except Exception as e:
            logger.error(f"处理失败: {str(e)}")
            if self.dry_run:
                logger.info(f"模拟运行信息: {e}")
            else:
                sys.exit(1)
    
    def parse_repo_data(self, repo_data: Dict) -> Dict[Tuple, Any]:
        """
        解析原始仓库数据为结构化格式
        
        参数:
            repo_data: 原始仓库数据字典
            
        返回:
            格式化的仓库信息字典
        """
        mappings = {}
        
        for repo_id, config in repo_data.items():
            try:
                # 解析仓库ID中的版本信息
                version_match = STACK_VERSION_REGEX.match(repo_id)
                if not version_match:
                    logger.warning(f"无法解析仓库ID格式: {repo_id}")
                    continue
                
                stack_name, stack_version = version_match.group(1), version_match.group(2)
                latest_urls = config.get("latest", {})
                
                # 应用操作系统家族映射
                normalized_urls = {}
                for os_family, url in latest_urls.items():
                    # 映射家族名称
                    mapped_family = OS_FAMILY_MAP.get(os_family, os_family)
                    normalized_urls[mapped_family] = url
                    logger.debug(f"映射: {os_family} -> {mapped_family}")
                
                key = (stack_version, repo_id)
                mappings[key] = normalized_urls
                
                logger.info(f"仓库映射: {repo_id} -> 版本: {stack_version} | OS数量: {len(normalized_urls)}")
                
            except Exception as e:
                logger.error(f"处理仓库ID {repo_id} 时出错: {str(e)}")
        
        return mappings
    
    def process_repo_with_version(self, stack_version: str, repo_id: str, repo_info: Dict) -> None:
        """
        处理特定版本的仓库
        
        参数:
            stack_version: 堆栈版本
            repo_id: 仓库ID
            repo_info: 仓库URL信息字典
        """
        # 构建目标XML路径
        repo_xml_path = self.stack_folder / stack_version / "repos" / "repoinfo.xml"
        
        if not repo_xml_path.exists():
            logger.warning(f"仓库XML文件不存在: {repo_xml_path}")
            return
        
        logger.info(f"处理: {stack_version}/repos/repoinfo.xml | 仓库: {repo_id}")
        
        try:
            self.update_repo_xml(repo_xml_path, repo_id, repo_info)
        except Exception as e:
            logger.error(f"修改仓库 {repo_id} 失败: {str(e)}")
    
    def update_repo_xml(self, xml_path: Path, repo_id: str, repo_info: Dict) -> None:
        """
        更新XML仓库配置
        
        参数:
            xml_path: XML文件路径
            repo_id: 目标仓库ID
            repo_info: 要更新的仓库信息
        """
        try:
            # 解析XML
            logger.debug(f"解析XML文件: {xml_path}")
            tree = ET.parse(xml_path)
            root = tree.getroot()
            ns = {"repo": ""}  # 无命名空间
        except ET.ParseError as e:
            logger.error(f"XML解析失败: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"加载XML文件失败: {str(e)}")
            raise
        
        # 统计更新数量
        update_count = 0
        processed_families = set()
        
        # 处理每个操作系统家族
        for os_tag in root.findall("repo:os", ns):
            family = os_tag.get("family", "")
            original_family = family
            logger.debug(f"处理操作系统家族: {family}")
            
            # 应用家族映射
            if family in OS_FAMILY_MAP:
                family = OS_FAMILY_MAP[family]
                logger.debug(f"映射家族: {original_family} -> {family}")
            
            # 如果这个家族有更新
            if family in repo_info:
                new_url = repo_info[family]
                self.process_repo_tags(os_tag, ns, repo_id, family, new_url)
                update_count += 1
                processed_families.add(family)
        
        # 记录未处理的家族
        unprocessed = set(repo_info.keys()) - processed_families
        if unprocessed:
            logger.warning(f"未处理的家族: {', '.join(unprocessed)} | 仓库: {repo_id}")
        
        # 保存更改
        if update_count > 0 and not self.dry_run:
            self.write_updated_xml(xml_path, tree)
            logger.success(f"更新了 {update_count} 个仓库URL | 文件: {xml_path}")
        elif self.dry_run and update_count > 0:
            logger.info(f"模拟运行: 检测到 {update_count} 个需要更新的仓库URL | 仓库: {repo_id}")
    
    def process_repo_tags(self, os_tag: ET.Element, ns: Dict, repo_id: str, family: str, new_url: str) -> None:
        """
        处理特定操作系统标签中的仓库标签
        
        参数:
            os_tag: 操作系统标签元素
            ns: XML命名空间
            repo_id: 目标仓库ID
            family: 操作系统家族
            new_url: 新的仓库URL
        """
        for repo_tag in os_tag.findall("repo:repo", ns):
            # 在repo标签内查找repoid标签
            repo_id_tag = repo_tag.find("repo:repoid", ns)
            
            if repo_id_tag is not None and repo_id_tag.text == repo_id:
                # 检查baseurl标签
                if baseurl_tag := repo_tag.find("repo:baseurl", ns):
                    # 如果URL未改变，则跳过
                    if baseurl_tag.text == new_url:
                        logger.info(f"URL未改变 | 仓库: {repo_id} | 家族: {family}")
                        continue
                    
                    # 更新URL
                    if self.dry_run:
                        logger.info(f"模拟更新: {baseurl_tag.text} -> {new_url} | 仓库: {repo_id} | 家族: {family}")
                    else:
                        logger.info(f"更新URL: {baseurl_tag.text} -> {new_url} | 仓库: {repo_id} | 家族: {family}")
                        baseurl_tag.text = new_url
    
    def write_updated_xml(self, xml_path: Path, tree: ET.ElementTree):
        """
        安全写入更新的XML文件
        
        参数:
            xml_path: 目标文件路径
            tree: XML元素树
        """
        try:
            # 创建临时文件名
            tmp_path = xml_path.with_suffix(".tmp")
            
            # 写入更新内容
            with tmp_path.open("wb") as f:
                f.write(XML_HEADER.encode("utf-8"))
                f.write(b"\n")
                tree.write(f, encoding="utf-8", xml_declaration=False)
            
            # 替换原始文件
            tmp_path.replace(xml_path)
            logger.debug(f"文件安全更新: {xml_path}")
            
        except OSError as e:
            logger.error(f"写入XML文件失败: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"文件处理发生错误: {str(e)}")
            raise


def setup_logger(verbose: bool = False):
    """配置详细日志输出"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.getLogger().setLevel(level)
    logger.debug("启用详细日志模式")


def main():
    """命令行应用入口点"""
    parser = argparse.ArgumentParser(
        description="高级仓库配置处理器",
        epilog="自动化处理仓库URL更新到仓库配置文件中",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # 命令行参数
    parser =_argumentParser.add_argument(
        "-u", "--urlinfo", 
        required=True,
        help="仓库URL信息文件路径或URL"
    )
    parser.add_argument(
        "-s", "--stack-folder",
        required=True,
        help="版本化仓库配置文件夹的根目录"
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true",
        help="模拟运行，不进行实际修改"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="启用详细输出"
    )
    parser.add_argument(
        "--log-file",
        help="可选的日志文件路径"
    )
    
    # 解析参数
    args = parser.parse_args()
    
    # 配置日志
    if args.log_file:
        log_handler = logging.FileHandler(args.log_file, encoding="utf-8")
        log_format = "[%(asctime)s] %(levelname)s: %(message)s"
        log_handler.setFormatter(logging.Formatter(log_format))
        logging.getLogger().addHandler(log_handler)
    
    setup_logger(args.verbose)
    logger.info(f"启动仓库处理器 | 模式: {'模拟运行' if args.dry_run else '实际执行'}")
    
    try:
        # 初始化并执行处理器
        manager = RepositoryManager(
            urlinfo_path=args.urlinfo,
            stack_folder=args.stack_folder,
            dry_run=args.dry_run
        )
        manager.process_repo_mappings()
        
        logger.info("仓库处理成功完成")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"处理失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
