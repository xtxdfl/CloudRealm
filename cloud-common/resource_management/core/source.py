#!/usr/bin/env python3
import os
import time
from typing import Optional, Dict, Any, List, Union, Type
from enum import IntEnum, auto

from resource_management.core.environment import Environment
from resource_management.core.logger import Logger
from resource_management.core.exceptions import Fail
from resource_management.core.utils import checked_unite
from resource_management.core import sudo
from cloud_commons.os_family_impl import OsFamilyFuncImpl, OsFamilyImpl
from cloud_commons import OSConst

__all__ = ["Source", "Template", "InlineTemplate", "StaticFile", "DownloadSource"]


class SourceType(IntEnum):
    """源类型枚�?""
    STATIC = auto()
    TEMPLATE = auto()
    INLINE_TEMPLATE = auto()
    DOWNLOAD = auto()


class Source:
    """
    文件源抽象基�?    
    核心职责�?    1. 定义统一的文件源接口
    2. 提供内容读取和校验机�?    3. 支持可调用协议（__call__�?    4. 实现内容相等性比�?    
    子类必须实现�?    - get_content(): 返回文件内容（bytes/str�?    - get_checksum(): 返回校验和（可选）
    """
    
    def __init__(self, name: str):
        """
        Args:
            name: 源标识符（文件路径、模板路径或 URL�?        """
        self.env = Environment.get_instance()
        self.name = name
    
    def get_content(self) -> Union[str, bytes]:
        """
        获取源内�?        
        Returns:
            Union[str, bytes]: 文件内容
            
        Raises:
            NotImplementedError: 必须由子类实�?        """
        raise NotImplementedError(f"子类 {self.__class__.__name__} 必须实现 get_content()")
    
    def get_checksum(self) -> Optional[str]:
        """
        获取内容校验和（可选）
        
        Returns:
            Optional[str]: 校验和字符串�?None
        """
        return None
    
    def __call__(self) -> Union[str, bytes]:
        """可调用协议适配"""
        return self.get_content()
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}('{self.name}')"
    
    def __eq__(self, other: object) -> bool:
        """
        内容相等性比�?        
        规则�?        - 必须是相同类型的实例
        - 绝对路径直接比较路径
        - 否则比较内容
        """
        if not isinstance(other, self.__class__):
            return False
        
        # 绝对路径直接比较
        if self.name.startswith(os.sep):
            return self.name == other.name
        
        # 内容比较
        return self.get_content() == other.get_content()


class StaticFile(Source):
    """静态文件源：直接读取文件系统文�?""
    
    def __init__(self, name: str):
        """
        Args:
            name: 文件路径（绝对或相对 basedir/files�?        """
        super().__init__(name)
    
    def get_content(self) -> bytes:
        """
        读取静态文件内�?        
        Returns:
            bytes: 文件原始内容
            
        Raises:
            Fail: 文件不存在时抛出详细错误
        """
        # 绝对路径直接使用
        if self.name.startswith(os.sep):
            file_path = self.name
        else:
            # 相对路径基于 basedir/files
            basedir = self.env.config.basedir
            file_path = os.path.join(basedir, "files", self.name)
        
        if not sudo.path_isfile(file_path):
            raise Fail(f"静态文件源 {self!r} 未找�? {file_path}")
        
        Logger.debug(f"读取静态文�? {file_path}")
        return self._read_file(file_path)
    
    @OsFamilyFuncImpl(os_family=OsFamilyImpl.DEFAULT)
    def _read_file(self, path: str) -> bytes:
        """Linux 平台文件读取"""
        return sudo.read_file(path)
    
    @OsFamilyFuncImpl(os_family=OSConst.WINSRV_FAMILY)
    def _read_file(self, path: str) -> bytes:
        """Windows 平台文件读取"""
        Logger.debug(f"Windows 平台直接读取: {path}")
        with open(path, "rb") as fp:
            return fp.read()


# Jinja2 模板支持（可选）
try:
    from cloud_jinja2 import (
        Environment as JinjaEnvironment,
        BaseLoader,
        TemplateNotFound,
        FunctionLoader,
        StrictUndefined,
    )
except ImportError:
    # 未安�?Jinja2 时抛出异�?    class Template(Source):
        def __init__(self, name: str, **kwargs: Any):
            raise Exception("使用 Template/InlineTemplate 需要安�?Jinja2")
    
    class InlineTemplate(Source):
        def __init__(self, name: str, **kwargs: Any):
            raise Exception("使用 Template/InlineTemplate 需要安�?Jinja2")
else:
    
    class TemplateLoader(BaseLoader):
        """自定�?Jinja2 模板加载�?""
        
        def __init__(self, env: Optional[Environment] = None):
            self.env = env or Environment.get_instance()
        
        def get_source(self, environment: Any, template_name: str) -> tuple:
            """
            获取模板源码
            
            Returns:
                tuple: (源码, 路径, 重载检查函�?
                
            Raises:
                TemplateNotFound: 模板文件不存�?            """
            # 绝对路径直接使用
            if template_name.startswith(os.sep):
                path = template_name
            else:
                # 相对路径基于 basedir/templates
                basedir = self.env.config.basedir
                path = os.path.join(basedir, "templates", template_name)
            
            if not os.path.exists(path):
                Logger.error(f"模板文件不存�? {path}")
                raise TemplateNotFound(f"{template_name} at {path}")
            
            mtime = os.path.getmtime(path)
            
            with open(path, "rt", encoding="utf-8") as fp:
                source = fp.read()
            
            Logger.debug(f"加载模板: {path} (mtime: {mtime})")
            
            # 重载检查函�?            def uptodate() -> bool:
                return mtime == os.path.getmtime(path)
            
            return source, path, uptodate
    
    
    class Template(Source):
        """模板文件源：使用 Jinja2 渲染模板"""
        
        def __init__(self, name: str, extra_imports: Optional[List[Any]] = None, **kwargs: Any):
            """
            Args:
                name: 模板文件路径
                extra_imports: 额外导入的模块列�?                **kwargs: 渲染上下文变�?            """
            super().__init__(name)
            
            params = self.env.config.params
            variables = checked_unite(params, kwargs)
            
            # 构建导入字典
            imports = extra_imports or []
            self.imports_dict = {module.__name__: module for module in imports}
            
            # 渲染上下�?            self.context = variables.copy() if variables else {}
            
            # 初始�?Jinja2 环境
            self.template_env = JinjaEnvironment(
                loader=TemplateLoader(self.env),
                autoescape=False,
                undefined=StrictUndefined,
                trim_blocks=True,
            )
            
            self.template = self.template_env.get_template(self.name)
        
        def get_content(self) -> str:
            """
            渲染模板并返回内�?            
            Returns:
                str: 渲染后的文本内容
            """
            # 内置默认变量
            default_vars = {
                "env": self.env,
                "repr": repr,
                "str": str,
                "bool": bool,
                "unicode": str,
            }
            
            # 合并上下�?            variables = checked_unite(default_vars, self.imports_dict)
            self.context.update(variables)
            
            Logger.info(f"渲染模板: {self.name}")
            rendered = self.template.render(self.context)
            
            # 记录渲染后大�?            size = len(rendered.encode("utf-8"))
            Logger.debug(f"模板渲染完成: {self.name} ({size} bytes)")
            
            return rendered
    
    
    class InlineTemplate(Template):
        """内联模板源：直接在代码中定义模板内容"""
        
        def __init__(self, name: str, extra_imports: Optional[List[Any]] = None, **kwargs: Any):
            """
            Args:
                name: 模板字符串内�?                extra_imports: 额外导入的模块列�?                **kwargs: 渲染上下文变�?            """
            # 使用 FunctionLoader 从内存加载模�?            self.template_env = JinjaEnvironment(
                loader=FunctionLoader(lambda text: text),
                autoescape=False,
                undefined=StrictUndefined,
            )
            
            super().__init__(name, extra_imports, **kwargs)
        
        def __repr__(self) -> str:
            return "InlineTemplate(...)"


class DownloadSource(Source):
    """
    下载文件源：�?URL 下载文件
    
    特性：
    - 自动缓存（基�?tmp_dir�?    - 代理控制（ignore_proxy 参数�?    - 断点续传（redownload_files 参数�?    - URL 自动解析文件�?    """
    
    def __init__(
        self,
        name: str,
        redownload_files: bool = False,
        ignore_proxy: bool = True,
    ):
        """
        Args:
            name: 下载 URL
            redownload_files: 是否强制重新下载（不使用缓存�?            ignore_proxy: 是否忽略 http_proxy/https_proxy 环境变量
        """
        super().__init__(name)
        
        self.url = self.name
        self.cache = not redownload_files and bool(self.env.tmp_dir)
        self.download_path = self.env.tmp_dir
        self.ignore_proxy = ignore_proxy
        
        Logger.debug(
            f"创建下载�? url={self.url}, cache={self.cache}, "
            f"ignore_proxy={self.ignore_proxy}"
        )
    
    def get_content(self) -> bytes:
        """
        下载文件并返回内�?        
        Returns:
            bytes: 文件二进制内�?            
        Raises:
            Fail: 下载失败或目录不存在
        """
        # 验证下载目录
        if self.download_path and not os.path.exists(self.download_path):
            raise Fail(f"下载目录不存�? {self.download_path}")
        
        # 生成文件�?        parsed = urllib.parse.urlparse(self.url)
        if parsed.path:
            filename = os.path.basename(parsed.path)
        else:
            filename = f"download.{int(time.time())}"
        
        filepath = os.path.join(self.download_path, filename) if self.download_path else None
        
        # 缓存检�?        if self.cache and filepath and os.path.exists(filepath):
            Logger.info(f"使用缓存文件: {filepath} (URL: {self.url})")
            return sudo.read_file(filepath)
        
        # 执行下载
        Logger.info(f"开始下�? {self.url}")
        
        # 配置代理
        if self.ignore_proxy:
            Logger.debug("忽略系统代理设置")
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        else:
            opener = urllib.request.build_opener()
        
        req = urllib.request.Request(self.url)
        
        try:
            with opener.open(req) as web_file:
                content = web_file.read()
            
            Logger.info(f"下载成功: {len(content)} bytes from {self.url}")
            
            # 缓存文件
            if self.cache and filepath:
                Logger.debug(f"缓存�? {filepath}")
                sudo.create_file(filepath, content)
            
            return content
        
        except urllib.error.HTTPError as ex:
            raise Fail(f"下载失败 (HTTP {ex.code}): {self.url} - {ex.reason}")
        
        except urllib.error.URLError as ex:
            raise Fail(f"下载失败 (URL Error): {self.url} - {ex.reason}")
        
        except Exception as ex:
            raise Fail(f"下载失败 (未知错误): {self.url} - {str(ex)}")


# 便捷函数
def create_source(source_type: SourceType, name: str, **kwargs: Any) -> Source:
    """
    工厂函数：根据类型创建源实例
    
    Args:
        source_type: 源类型枚�?        name: 源标识符
        **kwargs: 传递给构造函数的参数
        
    Returns:
        Source: 对应的源实例
        
    示例�?        source = create_source(SourceType.STATIC, "config.xml")
        source = create_source(SourceType.DOWNLOAD, "http://example.com/file")
    """
    source_classes: Dict[SourceType, Type[Source]] = {
        SourceType.STATIC: StaticFile,
        SourceType.TEMPLATE: Template,
        SourceType.INLINE_TEMPLATE: InlineTemplate,
        SourceType.DOWNLOAD: DownloadSource,
    }
    
    if source_type not in source_classes:
        raise Fail(f"未知的源类型: {source_type}")
    
    return source_classes[source_type](name, **kwargs)
