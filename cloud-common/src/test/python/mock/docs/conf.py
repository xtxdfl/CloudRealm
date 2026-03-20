#!/usr/bin/env python3
"""Mock库的文档配置 - 优化Sphinx设置"""
import sys
import os
from datetime import datetime
import mock  # 导入被mock的模块本身

# ---- 路径配置 ----
# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath('../src'))

# ---- 基础配置 ----
project = "Python Mock库"
author = "Mock核心开发团队"
copyright = f"2003-{datetime.now().year}, {author}"
release = mock.__version__
version = '.'.join(release.split('.')[:2])  # 主次版本号

# ---- 扩展配置 ----
extensions = [
    'sphinx.ext.autodoc',     # 自动API文档生成
    'sphinx.ext.napoleon',    # Google风格文档支持
    'sphinx.ext.intersphinx',  # 跨文档链接
    'sphinx.ext.todo',        # TODO支持
    'sphinx.ext.viewcode',    # 源代码查看
    'sphinx_copybutton',      # 代码块复制按钮
    'sphinx_inline_tabs',     # 多语言标签支持
    'sphinxext.opengraph',    # OpenGraph元数据
]

# ---- 主题和视觉配置 ----
html_theme = 'furo'  # 现代化响应式主题
html_theme_options = {
    "sidebar_hide_name": True,
    "navigation_with_keys": True,
    "source_repository": "https://github.com/python/mock/",
    "source_branch": "main",
    "source_directory": "docs/",
}

html_title = f"Mock {release} 文档"
html_short_title = "Python Mock库"
html_logo = "_static/logo.svg"
html_favicon = "_static/favicon.ico"

# ---- 内容配置 ----
source_suffix = '.rst'
master_doc = 'index'
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']
templates_path = ['_templates']
pygments_style = 'monokai'

# ---- 国际化配置 ----
language = "zh"
locale_dirs = ['locales/']  # 国际化翻译目录

# ---- 功能配置 ----
autodoc_default_options = {
    'members': True,
    'show_inheritance': True,
    'member-order': 'groupwise'
}
autodoc_typehints = "signature"

todo_include_todos = True

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
}

# ---- 文档测试配置 ----
doctest_global_setup = """
import os
import sys
sys.path.append(os.getcwd())
from mock import patch, MagicMock, Mock, call
"""

# ---- 静态资源 ----
html_static_path = ['_static']
html_css_files = ['custom.css']
html_js_files = ['responsive.js']

# ---- OpenGraph元数据 ----
ogp_site_url = "https://mock.readthedocs.io/"
ogp_image = "_static/opengraph.png"

def setup(app):
    app.add_config_value('is_rtd', False, 'env')  # 用于ReadTheDocs检测
    app.add_css_file('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css')

