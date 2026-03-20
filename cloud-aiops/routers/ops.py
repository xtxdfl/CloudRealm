from fastapi import APIRouter
from typing import List
from models import Alert, AlertLevel, Task, MetricPoint
import random
from datetime import datetime, timedelta

router = APIRouter()

alerts_db = [
    Alert(id=1, level=AlertLevel.CRITICAL, message="DataNode (Worker-03) 心跳丢失", source="HDFS", timestamp="2分钟前"),
    Alert(id=2, level=AlertLevel.WARNING, message="YARN 队列 (root.default) 资源使用率 > 90%", source="YARN", timestamp="15分钟前"),
    Alert(id=3, level=AlertLevel.CRITICAL, message="Hive Metastore 连接超时", source="HIVE", timestamp="32分钟前"),
    Alert(id=4, level=AlertLevel.WARNING, message="Kafka Topic (logs) 消费积压", source="KAFKA", timestamp="1小时前"),
    Alert(id=5, level=AlertLevel.INFO, message="集群配置变更：hdfs-site.xml", source="Cloud", timestamp="2小时前"),
    Alert(id=6, level=AlertLevel.INFO, message="Spark Job (Daily-ETL) 完成", source="SPARK", timestamp="3小时前"),
]

tasks_db = [
    Task(id="t1", name="Daily ETL Workflow", status="Running", progress=45),
    Task(id="t2", name="Hourly Aggregation", status="Pending", progress=0),
    Task(id="t3", name="Data Cleanup", status="Success", progress=100),
]

@router.get("/ops/alerts", response_model=List[Alert])
async def get_alerts():
    return alerts_db

@router.get("/ops/tasks", response_model=List[Task])
async def get_tasks():
    # Simulate progress
    for task in tasks_db:
        if task.status == "Running":
            task.progress = min(100, task.progress + 5)
            if task.progress >= 100:
                task.status = "Success"
    return tasks_db

@router.get("/ops/metrics/cpu", response_model=List[MetricPoint])
async def get_cpu_metrics():
    # Generate last 20 points
    now = datetime.now()
    points = []
    for i in range(20):
        points.append(MetricPoint(
            timestamp=int((now - timedelta(minutes=20-i)).timestamp()),
            value=random.uniform(20, 60)
        ))
    return points
