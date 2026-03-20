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

import pwd  # 导入标准库pwd模块处理用户信息

def getpwnam(user: str) -> pwd.struct_passwd:
    """
    获取指定用户的密码文件信息
    
    参数:
        user: 要查询的用户名
    
    返回:
        包含用户信息的命名元组(pwd.struct_passwd)
        包含以下字段:
        - pw_name: 用户名
        - pw_passwd: 加密后的密码(通常为'x'表示使用shadow文件)
        - pw_uid: 用户ID
        - pw_gid: 主组ID
        - pw_gecos: 用户描述信息
        - pw_dir: 用户主目录
        - pw_shell: 用户默认shell
    
    异常:
        当用户不存在时抛出KeyError
    """
    return pwd.getpwnam(user)

if __name__ == "__main__":
    # 示例用法: 查询root用户信息
    try:
        user_info = getpwnam("root")
        print(f"用户信息: {user_info}")
        print(f"用户名: {user_info.pw_name}")
        print(f"用户ID: {user_info.pw_uid}")
        print(f"主目录: {user_info.pw_dir}")
    except KeyError:
        print("错误: 指定的用户不存在")
