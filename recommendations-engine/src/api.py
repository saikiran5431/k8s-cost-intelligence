# recommendations-engine/src/api.py

import logging
import time
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from recommender import generate_recommendations

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="K8s Cost Recommendations API",
    description="Detects over-provisioned pods and suggests right-sizing",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache results for 60 seconds
_cache = {"data": None, "timestamp": 0}
CACHE_TTL = 60

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.get("/recommendations")
def recommendations():
    global _cache
    now = time.time()
    if _cache["data"] and (now - _cache["timestamp"]) < CACHE_TTL:
        logger.info("Returning cached recommendations")
        return _cache["data"]

    logger.info("Generating fresh recommendations...")
    start = time.time()
    result = generate_recommendations()
    elapsed = round(time.time() - start, 2)

    result["generated_at"] = datetime.utcnow().isoformat()
    result["computation_seconds"] = elapsed

    _cache = {"data": result, "timestamp": now}
    logger.info(
        f"Generated {len(result['recommendations'])} recommendations "
        f"in {elapsed}s. "
        f"Total savings possible: ${result['summary']['total_monthly_savings_possible']:.2f}/month"
    )
    return result

@app.get("/recommendations/summary")
def summary():
    data = recommendations()
    return {
        "summary": data["summary"],
        "generated_at": data["generated_at"],
        "top_3": data["recommendations"][:3]
    }

@app.get("/recommendations/critical")
def critical():
    data = recommendations()
    critical_recs = [
        r for r in data["recommendations"]
        if r["severity"] == "critical"
    ]
    return {
        "count": len(critical_recs),
        "recommendations": critical_recs,
        "generated_at": data["generated_at"]
    }