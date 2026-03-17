from fastapi import APIRouter
from typing import List
from models import HostInfo, Status
import random

router = APIRouter()

# Mock Hosts
def generate_mock_hosts():
    hosts = []
    roles = ["Master", "Worker", "Worker", "Worker", "Gateway"]
    for i, role in enumerate(roles):
        hosts.append(HostInfo(
            hostname=f"{role.lower()}-{i+1:02d}.cloudrealm.internal",
            ip=f"192.168.1.{10+i}",
            role=role,
            status=Status.HEALTHY if i != 3 else Status.WARNING,
            cpu_usage=random.uniform(10, 90),
            mem_usage=random.uniform(20, 80),
            disk_usage=random.uniform(30, 70),
            uptime="15d 4h 23m",
            components=["DataNode", "NodeManager"] if role == "Worker" else ["NameNode", "ResourceManager"]
        ))
    return hosts

hosts_db = generate_mock_hosts()

@router.get("/hosts", response_model=List[HostInfo])
async def get_hosts():
    # Update mock data slightly on each call to simulate live metrics
    for host in hosts_db:
        host.cpu_usage = max(0, min(100, host.cpu_usage + random.uniform(-5, 5)))
        host.mem_usage = max(0, min(100, host.mem_usage + random.uniform(-3, 3)))
    return hosts_db

@router.get("/hosts/top", response_model=List[HostInfo])
async def get_top_hosts(limit: int = 5, sort_by: str = "cpu"):
    # Sort logic
    sorted_hosts = sorted(hosts_db, key=lambda x: getattr(x, f"{sort_by}_usage", 0), reverse=True)
    return sorted_hosts[:limit]
