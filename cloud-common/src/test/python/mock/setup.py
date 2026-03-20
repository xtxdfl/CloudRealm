#!/usr/bin/env python3
# Copyright (c) 2007-2012 Michael Foord & the mock team
# License: BSD-3-Clause (https://opensource.org/licenses/BSD-3-Clause)

__version__ = "3.0.5"  # 示例版本号，实际应从mock模块导入

import os
from setuptools import setup, find_packages
from distutils.core import setup as distutils_setup  # 备用导入

# 基础包信息
PACKAGE_NAME = "mock"
MODULES = ["mock"]
DESCRIPTION = "Python Mocking and Patching Library for Testing"
LONG_DESC_PATH = os.path.join(os.path.dirname(__file__), "README.txt")
AUTHOR = "Michael Foord"
AUTHOR_EMAIL = "michael@voidspace.org.uk"
PROJECT_URL = "https://github.com/testing-cabal/mock"
KEYWORDS = "testing test mock unittest patching stubs fakes doubles".split()

# 读取长描述
def get_long_description():
    """读取并返回README文件内容作为长描述"""
    try:
        with open(LONG_DESC_PATH, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return DESCRIPTION

# 包分类信息
CLASSIFIERS = [
    "Development Status :: 5 - Production/Stable",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: BSD License",
    "Programming Language :: Python",
    "Programming Language :: Python :: 2",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 2.7",
    "Programming Language :: Python :: 3.5",
    "Programming Language :: Python :: 3.6",
    "Programming Language :: Python :: 3.7",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: Implementation :: CPython",
    "Programming Language :: Python :: Implementation :: PyPy",
    "Operating System :: OS Independent",
    "Topic :: Software Development :: Libraries",
    "Topic :: Software Development :: Libraries :: Python Modules",
    "Topic :: Software Development :: Testing",
]

# 设置参数
setup_params = {
    "name": PACKAGE_NAME,
    "version": __version__,
    "py_modules": MODULES,
    "author": AUTHOR,
    "author_email": AUTHOR_EMAIL,
    "description": DESCRIPTION,
    "long_description": get_long_description(),
    "keywords": KEYWORDS,
    "url": PROJECT_URL,
    "classifiers": CLASSIFIERS,
}

# 设置测试依赖
try:
    setup_params.update({
        "tests_require": ["unittest2; python_version<'3.0'"],
        "test_suite": "unittest2.collector",
    })
    setup(**setup_params)
except ImportError:
    # 回退到distutils（旧环境）
    setup_params.pop("tests_require", None)
    setup_params.pop("test_suite", None)
    distutils_setup(**setup_params)

