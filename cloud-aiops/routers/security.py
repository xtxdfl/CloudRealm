from fastapi import APIRouter
from typing import List
from models import AuditLog, AuthStatus, Status

router = APIRouter()

audit_logs_db = [
    AuditLog(id=1, user="admin", action="Granted Policy", resource="/hdfs/data/finance", timestamp="10:23 AM", status="Success"),
    AuditLog(id=2, user="user_dev", action="Access Denied", resource="/hive/finance.salary", timestamp="09:45 AM", status="Failed"),
    AuditLog(id=3, user="system", action="Keytab Renew", resource="hdfs/nn", timestamp="08:00 AM", status="Success"),
    AuditLog(id=4, user="external_ip", action="SSH Login", resource="Master01", timestamp="02:11 AM", status="Warning"),
]

auth_status_db = [
    AuthStatus(component="LDAP", status=Status.HEALTHY, details="Connected: ad.cloudrealm.internal"),
    AuthStatus(component="Kerberos", status=Status.HEALTHY, details="CLOUDREALM.COM (MIT KDC)"),
]

@router.get("/security/audit_logs", response_model=List[AuditLog])
async def get_audit_logs():
    return audit_logs_db

@router.get("/security/auth_status", response_model=List[AuthStatus])
async def get_auth_status():
    return auth_status_db
