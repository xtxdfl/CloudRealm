# main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import httpx
import subprocess
from datetime import datetime
import sqlite3

app = FastAPI(title="运维管理系统API")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 数据库初始化
def init_db():
    conn = sqlite3.connect('ops.db')
    cursor = conn.cursor()

    # 创建任务表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        schedule TEXT NOT NULL,
        last_run TEXT,
        next_run TEXT,
        status TEXT NOT NULL,
        progress INTEGER NOT NULL,
        owner TEXT NOT NULL,
        workflow TEXT
    )
    ''')

    # 创建告警规则表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS alert_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        severity TEXT NOT NULL,
        condition TEXT NOT NULL,
        duration TEXT NOT NULL,
        receiver TEXT NOT NULL
    )
    ''')

    conn.commit()
    conn.close()

init_db()

# Prometheus配置
PROMETHEUS_URL = "http://localhost:9090"
GRAFANA_URL = "http://localhost:3000"
ELASTICSEARCH_URL = "http://localhost:9200"
N9E_URL = "http://localhost:10000"

# Pydantic模型
class Task(BaseModel):
    name: str
    type: str
    schedule: str
    owner: str
    workflow: Optional[dict] = None

class AlertRule(BaseModel):
    name: str
    severity: str
    condition: str
    duration: str
    receiver: str

class PrometheusConfig(BaseModel):
    url: str
    refresh_interval: int
    time_range: str

class ELKConfig(BaseModel):
    elasticsearch_url: str
    kibana_url: str
    username: str
    password: str

# API路由
@app.get("/")
def read_root():
    return {"message": "运维管理系统API"}

# Prometheus相关API
@app.get("/prometheus/metrics")
async def get_metrics(query: str, time_range: str = "1h"):
    """从Prometheus获取指标数据"""
    try:
        async with httpx.AsyncClient() as client:
            # 计算开始时间
            end_time = datetime.now()
            if time_range == "5m":
                start_time = end_time - timedelta(minutes=5)
            elif time_range == "15m":
                start_time = end_time - timedelta(minutes=15)
            elif time_range == "30m":
                start_time = end_time - timedelta(minutes=30)
            elif time_range == "1h":
                start_time = end_time - timedelta(hours=1)
            elif time_range == "6h":
                start_time = end_time - timedelta(hours=6)
            elif time_range == "24h":
                start_time = end_time - timedelta(hours=24)
            else:
                start_time = end_time - timedelta(days=7)

            # 调用Prometheus API
            params = {
                'query': query,
                'start': start_time.timestamp(),
                'end': end_time.timestamp(),
                'step': '15s'
            }
            response = await client.get(f"{PROMETHEUS_URL}/api/v1/query_range", params=params)

            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(status_code=response.status_code, detail="Prometheus查询失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/prometheus/config")
def get_prometheus_config():
    """获取Prometheus配置"""
    return {
        "url": PROMETHEUS_URL,
        "grafana_url": GRAFANA_URL
    }

@app.post("/prometheus/config")
def update_prometheus_config(config: PrometheusConfig):
    """更新Prometheus配置"""
    global PROMETHEUS_URL, GRAFANA_URL
    PROMETHEUS_URL = config.url
    # 实际项目中应保存到数据库或配置文件
    return {"message": "配置更新成功"}

# ELK相关API
@app.get("/elk/logs")
async def search_logs(query: str, size: int = 50):
    """从Elasticsearch搜索日志"""
    try:
        async with httpx.AsyncClient() as client:
            # 构建查询DSL
            dsl_query = {
                "query": {
                    "query_string": {
                        "query": query
                    }
                },
                "sort": [
                    {
                        "@timestamp": {
                            "order": "desc"
                        }
                    }
                ],
                "size": size
            }

            response = await client.post(
                f"{ELASTICSEARCH_URL}/_search",
                json=dsl_query,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 200:
                result = response.json()
                logs = []
                for hit in result.get("hits", {}).get("hits", []):
                    source = hit.get("_source", {})
                    logs.append({
                        "timestamp": source.get("@timestamp", ""),
                        "level": source.get("level", "INFO"),
                        "message": source.get("message", ""),
                        "host": source.get("host", ""),
                        "source": source.get("source", "")
                    })
                return {"logs": logs}
            else:
                raise HTTPException(status_code=response.status_code, detail="日志查询失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/elk/config")
def get_elk_config():
    """获取ELK配置"""
    return {
        "elasticsearch_url": ELASTICSEARCH_URL,
        "kibana_url": "http://localhost:5601"
    }

@app.post("/elk/config")
def update_elk_config(config: ELKConfig):
    """更新ELK配置"""
    global ELASTICSEARCH_URL
    ELASTICSEARCH_URL = config.elasticsearch_url
    # 实际项目中应保存到数据库或配置文件
    return {"message": "配置更新成功"}

# 任务调度相关API
@app.get("/tasks", response_model=List[Task])
def get_tasks():
    """获取所有任务"""
    conn = sqlite3.connect('ops.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, type, schedule, last_run, next_run, status, progress, owner, workflow FROM tasks")
    rows = cursor.fetchall()
    conn.close()

    tasks = []
    for row in rows:
        tasks.append({
            "id": row[0],
            "name": row[1],
            "type": row[2],
            "schedule": row[3],
            "last_run": row[4],
            "next_run": row[5],
            "status": row[6],
            "progress": row[7],
            "owner": row[8],
            "workflow": eval(row[9]) if row[9] else None
        })
    return tasks

@app.post("/tasks")
def create_task(task: Task):
    """创建新任务"""
    conn = sqlite3.connect('ops.db')
    cursor = conn.cursor()

    # 计算下次运行时间（简化版）
    next_run = calculate_next_run(task.schedule)

    cursor.execute(
        "INSERT INTO tasks (name, type, schedule, last_run, next_run, status, progress, owner, workflow) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (task.name, task.type, task.schedule, None, next_run, "pending", 0, task.owner, str(task.workflow) if task.workflow else None)
    )

    conn.commit()
    task_id = cursor.lastrowid
    conn.close()

    # 添加任务到调度系统（实际项目中使用APScheduler等）
    # scheduler.add_job(...)

    return {"id": task_id, **task.dict(), "status": "pending", "progress": 0, "next_run": next_run}

@app.put("/tasks/{task_id}")
def update_task(task_id: int, task: Task):
    """更新任务"""
    conn = sqlite3.connect('ops.db')
    cursor = conn.cursor()

    next_run = calculate_next_run(task.schedule)

    cursor.execute(
        "UPDATE tasks SET name=?, type=?, schedule=?, owner=?, workflow=? WHERE id=?",
        (task.name, task.type, task.schedule, task.owner, str(task.workflow) if task.workflow else None, task_id)
    )

    conn.commit()
    conn.close()

    # 更新调度系统中的任务
    # scheduler.reschedule_job(...)

    return {"message": "任务更新成功"}

@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    """删除任务"""
    conn = sqlite3.connect('ops.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    conn.commit()
    conn.close()

    # 从调度系统中移除任务
    # scheduler.remove_job(...)

    return {"message": "任务删除成功"}

@app.post("/tasks/{task_id}/start")
def start_task(task_id: int):
    """启动任务"""
    conn = sqlite3.connect('ops.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET status='running', progress=0 WHERE id=?", (task_id,))
    conn.commit()
    conn.close()

    # 启动任务
    # job = scheduler.get_job(...)
    # if job: job.resume()

    return {"message": "任务已启动"}

@app.post("/tasks/{task_id}/stop")
def stop_task(task_id: int):
    """停止任务"""
    conn = sqlite3.connect('ops.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET status='stopped' WHERE id=?", (task_id,))
    conn.commit()
    conn.close()

    # 停止任务
    # job = scheduler.get_job(...)
    # if job: job.pause()

    return {"message": "任务已停止"}

@app.get("/tasks/{task_id}/logs")
def get_task_logs(task_id: int):
    """获取任务日志"""
    # 实际项目中应从日志文件或日志系统获取
    return {
        "logs": [
            "2024-03-10 12:00:01 - 任务开始执行",
            "2024-03-10 12:00:15 - 处理数据中...",
            "2024-03-10 12:01:30 - 任务执行成功"
        ]
    }

def calculate_next_run(schedule: str) -> str:
    """计算下次运行时间（简化版）"""
    from datetime import datetime, timedelta
    # 实际项目中应使用croniter等库计算
    return (datetime.now() + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M")

# 告警相关API
@app.get("/alerts/rules", response_model=List[AlertRule])
def get_alert_rules():
    """获取告警规则"""
    conn = sqlite3.connect('ops.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, severity, condition, duration, receiver FROM alert_rules")
    rows = cursor.fetchall()
    conn.close()

    rules = []
    for row in rows:
        rules.append({
            "id": row[0],
            "name": row[1],
            "severity": row[2],
            "condition": row[3],
            "duration": row[4],
            "receiver": row[5]
        })
    return rules

@app.post("/alerts/rules")
def create_alert_rule(rule: AlertRule):
    """创建告警规则"""
    conn = sqlite3.connect('ops.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO alert_rules (name, severity, condition, duration, receiver) VALUES (?, ?, ?, ?, ?)",
        (rule.name, rule.severity, rule.condition, rule.duration, rule.receiver)
    )
    conn.commit()
    rule_id = cursor.lastrowid
    conn.close()

    # 同步到夜莺告警系统
    sync_to_n9e(rule)

    return {"id": rule_id, **rule.dict()}

@app.put("/alerts/rules/{rule_id}")
def update_alert_rule(rule_id: int, rule: AlertRule):
    """更新告警规则"""
    conn = sqlite3.connect('ops.db')
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE alert_rules SET name=?, severity=?, condition=?, duration=?, receiver=? WHERE id=?",
        (rule.name, rule.severity, rule.condition, rule.duration, rule.receiver, rule_id)
    )
    conn.commit()
    conn.close()

    # 同步到夜莺告警系统
    sync_to_n9e(rule)

    return {"message": "告警规则更新成功"}

@app.delete("/alerts/rules/{rule_id}")
def delete_alert_rule(rule_id: int):
    """删除告警规则"""
    conn = sqlite3.connect('ops.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM alert_rules WHERE id=?", (rule_id,))
    conn.commit()
    conn.close()

    # 从夜莺告警系统删除
    delete_from_n9e(rule_id)

    return {"message": "告警规则删除成功"}

@app.get("/alerts/active")
def get_active_alerts():
    """获取当前活动告警"""
    # 实际项目中应从夜莺或其他告警系统获取
    return [
        {
            "id": 1,
            "name": "生产数据库CPU过高",
            "severity": "critical",
            "condition": "CPU使用率超过90%",
            "duration": "5分钟",
            "source": "db-prod-01",
            "value": "94%"
        },
        {
            "id": 2,
            "name": "磁盘空间不足",
            "severity": "warning",
            "condition": "磁盘使用率超过85%",
            "duration": "15分钟",
            "source": "node-03",
            "value": "87%"
        }
    ]

def sync_to_n9e(rule: AlertRule):
    """同步告警规则到夜莺"""
    try:
        async with httpx.AsyncClient() as client:
            # 夜莺告警API调用示例
            n9e_rule = {
                "name": rule.name,
                "severity": rule.severity,
                "condition": rule.condition,
                "duration": rule.duration,
                "receivers": [rule.receiver]
            }

            # 实际夜莺API端点可能不同
            response = await client.post(
                f"{N9E_URL}/api/v1/rules",
                json=n9e_rule,
                headers={"Authorization": "Bearer YOUR_N9E_TOKEN"}
            )

            if response.status_code != 200:
                print(f"同步到夜莺失败: {response.text}")
    except Exception as e:
        print(f"同步到夜莺出错: {str(e)}")

def delete_from_n9e(rule_id: int):
    """从夜莺删除告警规则"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{N9E_URL}/api/v1/rules/{rule_id}",
                headers={"Authorization": "Bearer YOUR_N9E_TOKEN"}
            )

            if response.status_code != 200:
                print(f"从夜莺删除失败: {response.text}")
    except Exception as e:
        print(f"从夜莺删除出错: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
