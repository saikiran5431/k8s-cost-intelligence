# chargeback/src/api.py

import logging
import time
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from chargeback import generate_chargeback_report, generate_csv_report

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="K8s Chargeback API",
    description="Team cost allocation and chargeback reporting",
    version="1.0.0"
)

app.add_middleware(CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_cache = {"data": None, "timestamp": 0}
CACHE_TTL = 60

def get_report():
    global _cache
    now = time.time()
    if _cache["data"] and (now - _cache["timestamp"]) < CACHE_TTL:
        return _cache["data"]
    data = generate_chargeback_report()
    _cache = {"data": data, "timestamp": now}
    return data

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/chargeback")
def chargeback():
    return get_report()

@app.get("/chargeback/summary")
def summary():
    report = get_report()
    return {
        "period":   report["period"],
        "summary":  report["summary"],
        "teams":    [{
            "team_name":      t["team_name"],
            "monthly_cost":   t["monthly_cost"],
            "waste_monthly":  t["waste_monthly"],
            "budget_used_pct":t["budget_used_pct"],
            "status":         t["status"],
            "avg_efficiency": t["avg_efficiency"],
        } for t in report["teams"]]
    }

@app.get("/chargeback/csv")
def csv_report():
    report = get_report()
    csv    = generate_csv_report(report)
    return Response(
        content=csv,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=chargeback-report.csv"}
    )

@app.get("/chargeback/team/{team_id}")
def team_report(team_id: str):
    report = get_report()
    for t in report["teams"]:
        if t["team_id"] == team_id:
            return t
    return {"error": f"Team {team_id} not found"}
