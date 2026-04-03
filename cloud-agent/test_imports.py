import sys
import os

service_dir = r"c:\yj\CloudRealm\cloud-agent\service"
common_dir = r"c:\yj\CloudRealm\cloud-common\cloud_commons"

sys.path.insert(0, service_dir)
sys.path.insert(0, common_dir)

print("Testing imports from main.py...")

try:
    from CloudConfig import CloudConfig
    print("OK: CloudConfig")
except Exception as e:
    print(f"ERROR: CloudConfig - {e}")

try:
    from PingPortListener import PingPortListener
    print("OK: PingPortListener")
except Exception as e:
    print(f"ERROR: PingPortListener - {e}")

try:
    import hostname
    print("OK: hostname")
except Exception as e:
    print(f"ERROR: hostname - {e}")

try:
    from DataCleaner import DataCleaner
    print("OK: DataCleaner")
except Exception as e:
    print(f"ERROR: DataCleaner - {e}")

try:
    from ExitHelper import ExitHelper
    print("OK: ExitHelper")
except Exception as e:
    print(f"ERROR: ExitHelper - {e}")

try:
    from NetUtil import NetUtil
    print("OK: NetUtil")
except Exception as e:
    print(f"ERROR: NetUtil - {e}")

try:
    from cloud_commons import OSConst, OSCheck
    print("OK: cloud_commons")
except Exception as e:
    print(f"ERROR: cloud_commons - {e}")

try:
    from cloud_commons.shell import shellRunner
    print("OK: cloud_commons.shell")
except Exception as e:
    print(f"ERROR: cloud_commons.shell - {e}")

try:
    from cloud_commons.constants import cloud_SUDO_BINARY
    print("OK: cloud_commons.constants")
except Exception as e:
    print(f"ERROR: cloud_commons.constants - {e}")

try:
    from InitializerModule import InitializerModule
    print("OK: InitializerModule")
except Exception as e:
    print(f"ERROR: InitializerModule - {e}")

try:
    from HeartbeatHandlers import bind_signal_handlers
    print("OK: HeartbeatHandlers")
except Exception as e:
    print(f"ERROR: HeartbeatHandlers - {e}")

try:
    from StatusReporter import StatusReporter
    print("OK: StatusReporter")
except Exception as e:
    print(f"ERROR: StatusReporter - {e}")