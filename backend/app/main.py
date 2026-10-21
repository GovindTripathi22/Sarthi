# backend/app/main.py — FastAPI Gateway & Health Endpoint
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import time

app = FastAPI(
    title="Sarthi Middleware Gateway",
    version="1.4.0",
    description="Autonomous API Self-Healing & Contract Drift Middleware"
)

@app.get("/")
def read_root():
    return {
        "system": "Sarthi (AutoPatch)",
        "status": "OPERATIONAL",
        "version": "1.4.0",
        "proxy_route_prefix": "/proxy/{integration_id}/*"
    }

@app.get("/health")
def health_check():
    return {"status": "HEALTHY", "timestamp": time.time()}
