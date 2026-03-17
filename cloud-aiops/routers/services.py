from fastapi import APIRouter, HTTPException
from typing import List
from models import ServiceInfo, Status

router = APIRouter()

# Mock DB
services_db = [
    ServiceInfo(name="HDFS", version="3.3.6", status=Status.HEALTHY, config_version="v24", role="Storage", components=["NameNode", "DataNode"]),
    ServiceInfo(name="YARN", version="3.3.6", status=Status.HEALTHY, config_version="v12", role="Compute", components=["ResourceManager", "NodeManager"]),
    ServiceInfo(name="HIVE", version="3.1.3", status=Status.WARNING, config_version="v8", role="Database", components=["HiveServer2", "Metastore"]),
    ServiceInfo(name="SPARK", version="3.5.0", status=Status.HEALTHY, config_version="v3", role="Compute", components=["HistoryServer"]),
    ServiceInfo(name="KAFKA", version="3.6.0", status=Status.HEALTHY, config_version="v15", role="Messaging", components=["Broker"]),
    ServiceInfo(name="HBASE", version="2.5.5", status=Status.HEALTHY, config_version="v10", role="Database", components=["HMaster", "RegionServer"]),
    ServiceInfo(name="ZOOKEEPER", version="3.8.3", status=Status.HEALTHY, config_version="v5", role="Coordination", components=["Server"]),
    ServiceInfo(name="FLINK", version="1.17.1", status=Status.STOPPED, config_version="v1", role="Stream", components=["JobManager"]),
]

@router.get("/services", response_model=List[ServiceInfo])
async def get_services():
    return services_db

@router.get("/services/{name}", response_model=ServiceInfo)
async def get_service(name: str):
    service = next((s for s in services_db if s.name.lower() == name.lower()), None)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return service

@router.post("/services/{name}/restart")
async def restart_service(name: str):
    service = next((s for s in services_db if s.name.lower() == name.lower()), None)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return {"message": f"Service {name} restart initiated", "job_id": "job_12345"}
