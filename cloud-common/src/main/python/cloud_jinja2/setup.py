#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cloud Jinja2 引擎 - 企业级模板引擎解决方�?~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

cloud Jinja2 是基于原�?Jinja2 深度优化的模板引�?
�?支持所有原�?Jinja2 语法和功�?�?增强多线程处理能�?�?优化模板编译性能
�?提供企业级安全特�?
核心价�?
--------
�?适用于高并发Web应用
�?集成高级内存管理
�?增强沙盒安全环境
�?支持分布式编�?�?CI/CD 就绪

[应用场景]
------------
�?金融行业报表系统
�?电商平台动态页面生�?�?云计算配置模�?�?大规模邮件发送系�?�?IoT设备配置分发
"""

import sys
import platform
import os
from setuptools import setup, Extension, find_packages
from pathlib import Path

# 配置元数�?PACKAGE_NAME = "cloud_jinja2"
VERSION = "2.7.0"
AUTHOR = "cloud 技术团�?
AUTHOR_EMAIL = "tech-team@cloud.org"
LICENSE = "cloud Enterprise License"
URL = "https://platform.cloud.org/jinja"
REQUIREMENTS_FILE = "requirements.txt"

# 构建信息
IS_WINDOWS = platform.system() == "Windows"
DEBUG = os.getenv("DEBUG_BUILD", "false").lower() == "true"
ENABLE_OPTIMIZATIONS = os.getenv("OPTIMIZE", "true").lower() == "true"
ENABLE_COVERAGE = os.getenv("TEST_COVERAGE", "false").lower() == "true"

def read_project_file(filename: str) -> str:
    """读取项目文件内容"""
    filepath = Path(__file__).parent / filename
    return filepath.read_text(encoding="utf-8")

def get_requirements() -> list:
    """从requirements文件获取依赖"""
    req_text = read_project_file(REQUIREMENTS_FILE)
    return [
        line.strip() for line in req_text.splitlines()
        if line.strip() and not line.startswith("#")
    ]

# 配置扩展模块
ext_compile_args = []
if ENABLE_OPTIMIZATIONS:
    if not IS_WINDOWS:
        ext_compile_args.extend(["-O3", "-march=native", "-flto", "-fno-strict-aliasing"])
        if DEBUG:
            ext_compile_args.remove("-O3")
            ext_compile_args.append("-Og")
    else:
        if DEBUG:
            ext_compile_args.append("/Od")
        else:
            ext_compile_args.extend(["/Ox", "/Oi", "/Ot", "/GL"])

ext_link_args = []
if ENABLE_OPTIMIZATIONS and not IS_WINDOWS:
    ext_link_args.extend(["-flto", "-fuse-linker-plugin"])

# 安全编译选项
if IS_WINDOWS:
    ext_compile_args.extend(["/GS", "/sdl"])
else:
    ext_compile_args.extend(["-fstack-protector", "-D_FORTIFY_SOURCE=2"])

# C 扩展模块
ext_modules = [
    Extension(
        "cloud_jinja2._speedups",
        sources=["cloud_jinja2/_speedups.c"],
        extra_compile_args=ext_compile_args[:],
        extra_link_args=ext_link_args[:]
    ),
    Extension(
        "cloud_jinja2._debugsupport",
        sources=["cloud_jinja2/_debugsupport.c"],
        extra_compile_args=ext_compile_args[:],
        extra_link_args=ext_link_args[:]
    )
]

# 测试配置
TESTS_REQUIRE = ["pytest>=6.0", "coverage", "pytest-cov", "pytest-xdist"]
if ENABLE_COVERAGE:
    TESTS_REQUIRE.append("coverage-badge")

# 特性标�?features = {}
if "--with-debugsupport" in sys.argv:
    features["debugsupport"] = True
    sys.argv.remove("--with-debugsupport")
else:
    # 默认在开发构建中包含调试支持
    if DEBUG:
        features["debugsupport"] = True

# 包数据文�?package_data = {
    PACKAGE_NAME: [
        "templates/*.html",
        "templates/*.txt",
        "testsuite/res/*.*",
        "testsuite/data/*.*",
        "assets/*.css",
        "_markupsafe/*.*"
    ]
}

# CLI 工具入口
console_scripts = [
    "jinja-cli=cloud_jinja2.cli:main",
    "jinja-analyze=cloud_jinja2.analyzer:analyze_project"
]

# 设置配置
setup_config = {
    "name": PACKAGE_NAME,
    "version": VERSION,
    "url": URL,
    "license": LICENSE,
    "author": AUTHOR,
    "author_email": AUTHOR_EMAIL,
    "description": "企业级模板引擎解决方�?- 针对性能和安全进行优�?,
    "long_description": read_project_file("README.md"),
    "long_description_content_type": "text/markdown",
    "packages": find_packages(include=[PACKAGE_NAME, f"{PACKAGE_NAME}.*"]),
    "package_data": package_data,
    "include_package_data": True,
    "zip_safe": False,
    "ext_modules": ext_modules,
    "python_requires": ">=3.8",
    "install_requires": get_requirements(),
    "extras_require": {
        "i18n": ["babel>=0.8"],
        "security": ["pycryptodomex>=3.10"]
    },
    "tests_require": TESTS_REQUIRE,
    "test_suite": f"{PACKAGE_NAME}.testsuite.suite",
    "entry_points": {
        "console_scripts": console_scripts,
        "babel.extractors": [
            "cloud_jinja2 = cloud_jinja2.ext:babel_extract[i18n]"
        ]
    },
    "classifiers": [
        "Development Status :: 5 - Production/Stable",
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "License :: Other/Proprietary License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Security",
        "Topic :: Software Development :: Code Generators",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "Topic :: Text Processing :: Markup :: HTML"
    ],
    "project_urls": {
        "Documentation": "https://docs.platform.cloud.org/jinja",
        "Bug Tracker": "https://issues.cloud.org/projects/JINJA",
        "Source Code": "https://git.platform.cloud.org/sre/jinja-engine"
    }
}

# 平台特定配置
if IS_WINDOWS:
    # 禁用Windows平台上的LTO优化
    setup_config["ext_modules"][0].extra_link_args = []
    setup_config["ext_modules"][1].extra_link_args = []

if DEBUG:
    setup_config["define_macros"] = [('DEBUG', '1')]
    setup_config["ext_modules"][0].extra_compile_args.append("-DDEBUG")

if ENABLE_COVERAGE:
    setup_config["ext_modules"][0].extra_compile_args.append("--coverage")
    setup_config["ext_modules"][0].extra_link_args.append("--coverage")
    setup_config["ext_modules"][1].extra_compile_args.append("--coverage")
    setup_config["ext_modules"][1].extra_link_args.append("--coverage")

# 处理遗留兼容�?if "--with-speedups" in sys.argv:
    print(
        "⚠️注意: --with-speedups参数已弃用，速度优化模块已默认启用\n"
        "可通过环境变量禁用: SET OPTIMIZE=false"
    )
    sys.argv.remove("--with-speedups")

if __name__ == "__main__":
    setup(**setup_config)
