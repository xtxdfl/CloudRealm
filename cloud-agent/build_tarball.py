import os
import tarfile
import shutil

base_dir = "c:/yj/CloudRealm/cloud-agent"
output_tar = os.path.join(base_dir, "cloud-agent-linux-amd64.tar.gz")

components = [
    ("service", "python/cloud_agent"),
    ("../cloud-common/cloud_commons", "python/cloud_commons"),
    ("conf/unix", "conf"),
    ("etc/init.d", "etc/init.d"),
    ("etc/init", "etc/init"),
]

agent_bin = '''#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_LIB_DIR="$(dirname "$SCRIPT_DIR")"
AGENT_HOME="$(dirname "$AGENT_LIB_DIR")"

export cloud_AGENT_CONF_DIR="${AGENT_HOME}/conf"
export HOME_DIR="${AGENT_HOME}"
export CONFIG_FILE="${AGENT_HOME}/conf/cloud-agent.ini"
export PYTHONPATH="${AGENT_LIB_DIR}/python:${AGENT_LIB_DIR}/python/cloud_commons:${PYTHONPATH:-}"
export PATH="${AGENT_LIB_DIR}/python:${PATH}"

exec python "${AGENT_LIB_DIR}/python/cloud_agent/main.py" "$@"
'''

os.makedirs(os.path.join(base_dir, "target/src"), exist_ok=True)
src_script = os.path.join(base_dir, "target/src/cloud-agent")
content = agent_bin.encode('ascii').replace(b'\r', b'')
with open(src_script, 'wb') as f:
    f.write(content)
os.chmod(src_script, 0o755)

components.append(("target/src/cloud-agent", "bin/cloud-agent"))

if os.path.exists(output_tar):
    os.remove(output_tar)

with tarfile.open(output_tar, "w:gz") as tar:
    for src, arcname in components:
        src_path = os.path.join(base_dir, src)
        if os.path.exists(src_path):
            tar.add(src_path, arcname=arcname)
            print(f"Added: {src} -> {arcname}")
        else:
            print(f"Warning: {src_path} does not exist")

print(f"\nCreated: {output_tar}")
print(f"Size: {os.path.getsize(output_tar)} bytes")