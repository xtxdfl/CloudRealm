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

import os
import sys
import errno
import stat
from pathlib import Path, PurePath
from typing import (
    Generator,
    Tuple,
    List,
    Callable,
    Optional,
    Union,
    Text,
    NamedTuple,
    Type
)
from contextlib import contextmanager

class DirectoryEntry(NamedTuple):
    """目录条目元数据"""
    name: str
    path: Path
    is_dir: bool
    is_file: bool
    is_symlink: bool
    stat: Optional[os.stat_result] = None

class TreeWalkOptions:
    """目录遍历配置选项"""
    __slots__ = (
        'topdown', 
        'onerror', 
        'followlinks', 
        'include_stats',
        'unicode_error_handler',
        'max_depth',
        'path_callback'
    )
    
    def __init__(
        self, 
        topdown: bool = True,
        onerror: Optional[Callable] = None,
        followlinks: bool = False,
        include_stats: bool = False,
        unicode_error_handler: str = 'surrogateescape',
        max_depth: Optional[int] = None,
        path_callback: Optional[Callable] = None
    ):
        """
        初始化目录树遍历参数
        
        参数:
            topdown: 是否使用自上而下遍历 (默认True)
            onerror: 错误处理回调函数 (默认None)
            followlinks: 是否追踪符号链接 (默认False)
            include_stats: 是否包含文件统计信息 (默认False)
            unicode_error_handler: Unicode错误处理策略
            max_depth: 最大递归深度 (默认无限制)
            path_callback: 路径规范化回调函数
        """
        self.topdown = topdown
        self.onerror = onerror
        self.followlinks = followlinks
        self.include_stats = include_stats
        self.unicode_error_handler = unicode_error_handler
        self.max_depth = max_depth
        self.path_callback = path_callback

def robust_unicode_walk(
    top: Union[str, Path],
    options: Optional[TreeWalkOptions] = None
) -> Generator[Tuple[Path, List[DirectoryEntry], List[DirectoryEntry]], None, None]:
    """
    增强的Unicode目录遍历函数，处理各种编码和文件系统问题
    
    参数:
        top: 根目录路径
        options: 遍历配置选项
        
    返回:
        生成器: (dirpath, dir_entries, file_entries)
    """
    # 设置默认选项
    if options is None:
        options = TreeWalkOptions()
    
    # 标准化路径并确保为Path对象
    top_path = Path(top).resolve()
    
    # 使用堆栈避免递归深度限制
    stack = [(top_path, 0 if options.max_depth is None else options.max_depth)]
    while stack:
        current_path, depth = stack.pop()
        
        try:
            # 读取目录内容
            entries = []
            for name in current_path.iterdir():
                # 尝试处理Unicode错误并规范化路径
                try:
                    normalized_name = name.name.encode(
                        sys.getfilesystemencoding(), 
                        errors=options.unicode_error_handler
                    ).decode(sys.getfilesystemencoding())
                except Exception:
                    normalized_name = name.name
                
                # 应用路径回调进行自定义处理
                if options.path_callback:
                    normalized_name = options.path_callback(normalized_name)
                
                # 获取完整路径
                item_path = current_path / name
                
                # 安全检查: 避免无限循环的符号链接
                try:
                    if not options.followlinks and item_path.is_symlink():
                        entries.append(DirectoryEntry(
                            name=normalized_name,
                            path=item_path,
                            is_dir=False,
                            is_file=False,
                            is_symlink=True,
                            stat=item_path.stat() if options.include_stats else None
                        ))
                        continue
                except OSError as e:
                    if options.onerror:
                        options.onerror(e)
                    continue
                
                # 获取文件状态信息
                item_stat = None
                if options.include_stats:
                    try:
                        item_stat = item_path.stat()
                    except OSError as e:
                        if options.onerror:
                            options.onerror(e)
                        # 即使无法获取状态也继续
                
                # 分类目录和文件
                try:
                    is_dir = item_path.is_dir()
                    entries.append(DirectoryEntry(
                        name=normalized_name,
                        path=item_path,
                        is_dir=is_dir,
                        is_file=item_path.is_file(),
                        is_symlink=False,
                        stat=item_stat
                    ))
                except OSError as e:
                    if options.onerror:
                        options.onerror(e)
        
        except OSError as e:
            if options.onerror:
                options.onerror(e)
            # 如果无法读取目录，跳过处理
            continue
        
        # 分离目录和文件
        dirs = [entry for entry in entries if entry.is_dir]
        files = [entry for entry in entries if entry.is_file or entry.is_symlink]
        
        # 自顶向下模式: 先返回当前目录
        if options.topdown:
            yield current_path, dirs, files
        
        # 添加子目录到处理栈
        if depth > 0 or options.max_depth is None:
            # 使用深度优先搜索
            for entry in reversed(dirs):
                stack.append((
                    entry.path, 
                    depth - 1 if options.max_depth is not None else None
                ))
        
        # 自底向上模式: 后返回当前目录
        if not options.topdown:
            yield current_path, dirs, files

@contextmanager
def safe_directory_walk(
    top: Union[str, Path],
    options: Optional[TreeWalkOptions] = None
) -> Generator:
    """
    安全的目录遍历上下文管理器
    
    用法:
        with safe_directory_walk('/path/to/dir') as walker:
            for root, dirs, files in walker:
                # 处理文件和目录
    """
    try:
        yield robust_unicode_walk(top, options)
    except Exception as e:
        if options and options.onerror:
            options.onerror(e)
        else:
            print(f"遍历目录时发生错误: {str(e)}")
        return

def default_error_handler(error: Exception) -> None:
    """
    默认错误处理函数
    
    参数:
        error: 遇到的错误对象
    """
    if hasattr(error, 'errno') and error.errno == errno.EACCES:
        # 权限错误，记录但继续
        print(f"警告: 权限不足 - {error.filename}", file=sys.stderr)
    elif hasattr(error, 'errno') and error.errno == errno.ENOENT:
        # 文件不存在错误
        print(f"警告: 文件不存在 - {error.filename}", file=sys.stderr)
    else:
        # 其他错误
        print(f"错误: 处理文件时出错 [{type(error).__name__}]: {str(error)}", file=sys.stderr)

def unicode_path_normalizer(name: str) -> str:
    """
    Unicode路径规范化函数
    
    参数:
        name: 原始文件名
        
    返回:
        规范化的文件名字符串
    """
    from unicodedata import normalize
    # 标准化Unicode字符组合
    normalized = normalize('NFC', name)
    
    # Windows下处理保留字符
    if os.name == 'nt':
        reserved_chars = r'<>:"/\\|?*'
        for char in reserved_chars:
            normalized = normalized.replace(char, '_')
    
    return normalized

def calculate_directory_size(root_path: Union[str, Path]) -> Tuple[int, int]:
    """
    计算目录的总文件数和总大小
    
    参数:
        root_path: 根目录路径
        
    返回:
        (文件数量, 总字节大小)
    """
    file_count = 0
    total_size = 0
    
    options = TreeWalkOptions(
        followlinks=False,
        path_callback=unicode_path_normalizer,
        include_stats=True
    )
    
    with safe_directory_walk(root_path, options) as walker:
        for dirpath, _, files in walker:
            for file in files:
                if file.stat:
                    file_count += 1
                    total_size += file.stat.st_size
    
    return file_count, total_size

def find_files_by_pattern(
    root: Union[str, Path], 
    pattern: str
) -> Generator[Path, None, None]:
    """
    在目录树中查找匹配指定模式的文件
    
    参数:
        root: 根目录
        pattern: 匹配模式 (支持通配符)
        
    返回:
        匹配文件路径的生成器
    """
    import fnmatch
    options = TreeWalkOptions(path_callback=unicode_path_normalizer)
    
    with safe_directory_walk(root, options) as walker:
        for dirpath, _, files in walker:
            for file in files:
                if fnmatch.fnmatch(file.name, pattern):
                    yield file.path

def create_directory_index(
    root: Union[str, Path],
    output_file: Union[str, Path]
) -> None:
    """
    创建目录树的HTML索引文件
    
    参数:
        root: 根目录
        output_file: 输出HTML文件路径
    """
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    html_content = [
        '<!DOCTYPE html>',
        '<html lang="en">',
        '<head>',
        '<meta charset="UTF-8">',
        '<title>Directory Index</title>',
        '<style>',
        'body { font-family: Arial, sans-serif; }',
        'ul, li { margin: 0; padding: 0; list-style: none; }',
        '.directory { margin-left: 15px; }',
        '.file { margin-left: 15px; color: #0366d6; }',
        '.symlink { color: #6a737d; }',
        '</style>',
        '</head>',
        '<body>',
        f'<h1>Directory Index for {root}</h1>',
        '<ul>'
    ]
    
    def generate_tree(path: Path, level: int = 0) -> List[str]:
        content = []
        items = []
        
        options = TreeWalkOptions(
            topdown=False,
            path_callback=unicode_path_normalizer,
            include_stats=True
        )
        
        with safe_directory_walk(path, options) as walker:
            for dirpath, dirs, files in walker:
                # 深度指示符
                indent = '&nbsp;' * (level * 4)
                dir_content = []
                
                # 处理目录
                for d in dirs:
                    dir_content.extend(generate_tree(d.path, level + 1))
                    dir_items = '\n'.join(dir_content)
                    dir_class = 'directory'
                    items.append(
                        f'<li>{indent}📂 {d.name}\n<ul>{dir_items}</ul></li>'
                    )
                
                # 处理文件
                for f in files:
                    file_class = 'symlink' if f.is_symlink else 'file'
                    size = f"{f.stat.st_size:,}" if f.stat else ''
                    items.append(
                        f'<li class="{file_class}">'
                        f'{indent}📄 {f.name}{" (" + size + " bytes)" if size else ""}'
                        f'</li>'
                    )
                
                return items if level > 0 else [f'<li>📂 {os.path.basename(path)}\n<ul>', *items, '</ul></li>']
    
    try:
        html_content.extend(generate_tree(Path(root)))
        html_content.extend(['</ul>', '</body>', '</html>'])
        
        # 写入HTML文件
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(html_content))
            
        print(f"目录索引已创建: {output_file}")
    except Exception as e:
        print(f"创建目录索引失败: {str(e)}")

# 高级用法示例
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="文件系统遍历工具")
    parser.add_argument('directory', help="要遍历的目录")
    parser.add_argument('--size', action='store_true', help="计算目录大小")
    parser.add_argument('--index', metavar='FILENAME', help="生成HTML目录索引")
    parser.add_argument('--find', metavar='PATTERN', help="查找匹配模式的文件")
    
    args = parser.parse_args()
    
    # 配置遍历选项
    options = TreeWalkOptions(
        onerror=default_error_handler,
        path_callback=unicode_path_normalizer,
        include_stats=True
    )
    
    # 处理计算目录大小请求
    if args.size:
        file_count, total_size = calculate_directory_size(args.directory)
        print(f"目录 '{args.directory}':")
        print(f"  文件总数: {file_count}")
        print(f"  总大小: {total_size} 字节 ({total_size/1024/1024:.2f} MB)")
    
    # 处理目录索引生成请求
    elif args.index:
        create_directory_index(args.directory, args.index)
    
    # 处理文件查找请求
    elif args.find:
        print(f"在 '{args.directory}'中查找匹配 '{args.find}' 的文件:")
        found = False
        for path in find_files_by_pattern(args.directory, args.find):
            print(f"  - {path}")
            found = True
        
        if not found:
            print("  没有找到匹配的文件")
    
    # 默认行为: 遍历并显示目录结构
    else:
        print(f"目录树遍历 '{args.directory}':")
        with safe_directory_walk(args.directory, options) as walker:
            for root, dirs, files in walker:
                print(f"[{root}]")
                for d in dirs:
                    print(f"  📂 {d.name}")
                for f in files:
                    symlink_indicator = "@" if f.is_symlink else ""
                    print(f"  📄 {f.name}{symlink_indicator}")
