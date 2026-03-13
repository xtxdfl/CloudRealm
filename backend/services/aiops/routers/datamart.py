from fastapi import APIRouter
from typing import List
from models import DataAsset

router = APIRouter()

assets_db = [
    DataAsset(
        name="dw_sales.fact_orders", 
        type="HIVE", 
        owner="DataTeam", 
        quality_score=98.5, 
        description="Daily sales transactions fact table",
        lineage_upstream=["ods.orders_log"],
        lineage_downstream=["dm_sales.daily_report"]
    ),
    DataAsset(
        name="ods_log.clickstream", 
        type="KAFKA", 
        owner="AppTeam", 
        quality_score=100.0, 
        description="Real-time user click events",
        lineage_upstream=["app_server"],
        lineage_downstream=["dw_log.user_behavior"]
    ),
    DataAsset(
        name="dim_users", 
        type="HBASE", 
        owner="UserCenter", 
        quality_score=92.0, 
        description="User profile dimension table",
        lineage_upstream=["crm_db.users"],
        lineage_downstream=["dw_sales.fact_orders"]
    ),
]

@router.get("/datamart/assets", response_model=List[DataAsset])
async def get_assets():
    return assets_db

@router.get("/datamart/stats")
async def get_stats():
    return {
        "managed_tables": 2485,
        "quality_score_avg": 94.2,
        "storage_usage_pb": 1.2,
        "storage_capacity_percent": 65
    }
