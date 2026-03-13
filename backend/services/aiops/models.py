from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum
from datetime import datetime

# --- Enums ---
class Status(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    STOPPED = "stopped"
    UNKNOWN = "unknown"

class AlertLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

# --- Service Management ---
class ServiceInfo(BaseModel):
    name: str
    version: str
    status: Status
    config_version: str
    role: str
    description: Optional[str] = None
    components: List[str] = []

# --- Host Management ---
class HostInfo(BaseModel):
    hostname: str
    ip: str
    role: str  # Master, Worker, Gateway
    status: Status
    cpu_usage: float
    mem_usage: float
    disk_usage: float
    components: List[str] = []
    uptime: str

# --- Data Mart ---
class DataAsset(BaseModel):
    name: str
    type: str  # HIVE, HBASE, KAFKA
    owner: str
    quality_score: float
    description: Optional[str] = None
    lineage_upstream: List[str] = []
    lineage_downstream: List[str] = []

# --- Security Management ---
class AuditLog(BaseModel):
    id: int
    user: str
    action: str
    resource: str
    timestamp: str
    status: str  # Success, Failed

class AuthStatus(BaseModel):
    component: str  # LDAP, Kerberos
    status: Status
    details: str

# --- Ops Management ---
class MetricPoint(BaseModel):
    timestamp: int
    value: float

class Alert(BaseModel):
    id: int
    level: AlertLevel
    message: str
    source: str
    timestamp: str

class Task(BaseModel):
    id: str
    name: str
    status: str  # Running, Pending, Success, Failed
    progress: int

# --- AIOps ---
class Anomaly(BaseModel):
    id: int
    title: str
    description: str
    severity: str
    timestamp: str
    confidence: float

class Prediction(BaseModel):
    metric: str
    current_value: float
    predicted_value: float
    days_left: int
    recommendation: str

# --- User Management ---
class User(BaseModel):
    username: str
    role: str
    status: str
    last_login: str
