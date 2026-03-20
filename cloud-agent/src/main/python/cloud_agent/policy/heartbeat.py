# heartbeat.py
def send_heartbeat():
    payload = {
        "status": get_system_status(),
        "policies": get_active_policies(),  # 上报当前生效策略
        "keys": get_key_versions()          # 上报密钥版本
    }
    requests.post(f"{SERVER_URL}/api/agent/heartbeat", json=payload)