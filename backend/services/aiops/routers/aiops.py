from fastapi import APIRouter
from typing import List
from models import Anomaly, Prediction

router = APIRouter()

anomalies_db = [
    Anomaly(
        id=1, 
        title="Unusual Traffic Spike", 
        description="HDFS DataNode-04 network in > 3σ baseline", 
        severity="High", 
        timestamp="10 mins ago",
        confidence=0.95
    ),
    Anomaly(
        id=2, 
        title="Application Slowdown", 
        description="JVM GC Pause (Stop-the-world) > 5s", 
        severity="Medium", 
        timestamp="1 hour ago",
        confidence=0.88
    )
]

predictions_db = [
    Prediction(
        metric="HDFS Storage", 
        current_value=1.2, 
        predicted_value=1.8, 
        days_left=32, 
        recommendation="Add 2 DataNodes by next month"
    )
]

@router.get("/aiops/anomalies", response_model=List[Anomaly])
async def get_anomalies():
    return anomalies_db

@router.get("/aiops/predictions", response_model=List[Prediction])
async def get_predictions():
    return predictions_db
