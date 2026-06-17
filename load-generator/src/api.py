# load-generator/src/api.py
#
# New service. Runs as its own pod inside the cluster (cost-system
# namespace) so that generated traffic actually travels over the cluster
# network to workloads/frontend and workloads/backend ClusterIP Services -
# the same path real production traffic would take. This is intentionally
# a separate pod rather than reusing recommendations-engine or web-ui's
# nginx container, so the load generator's own CPU usage doesn't get
# attributed to (and skew the cost numbers of) an unrelated component.

import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="K8s Load Generator",
    description="Generates configurable synthetic traffic against sample workloads for live demo purposes",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Allowed targets ──────────────────────────────────────────────────────
# Deliberately a fixed allowlist, not a free-text URL field. This service
# runs with network access inside the cluster; letting the UI POST an
# arbitrary URL here would turn it into an open internal SSRF pivot. Add
# new entries here (and only here) if you want to be able to load-test
# other sample workloads later.
TARGETS = {
    "frontend": "http://frontend.workloads.svc.cluster.local:80/",
    "backend":  "http://backend.workloads.svc.cluster.local:80/get",
}

MAX_DURATION_SECONDS = 300      # hard ceiling: 5 minutes per run
MAX_REQUESTS_PER_SECOND = 200    # hard ceiling per worker-run
MIN_REQUESTS_PER_SECOND = 1

# ── In-memory job state ──────────────────────────────────────────────────
# Single-replica service (see deployment.yaml) - in-memory state is fine,
# same pattern the other components already use for their response cache.
_jobs: dict = {}
_active_job_id: Optional[str] = None
_lock = asyncio.Lock()


class LoadRequest(BaseModel):
    target: str = Field(..., description="Which sample workload to hit: 'frontend' or 'backend'")
    duration_seconds: int = Field(..., ge=1, le=MAX_DURATION_SECONDS)
    requests_per_second: int = Field(..., ge=MIN_REQUESTS_PER_SECOND, le=MAX_REQUESTS_PER_SECOND)


class LoadStatus(BaseModel):
    job_id: str
    target: str
    requests_per_second: int
    duration_seconds: int
    status: str  # "running" | "completed" | "stopped" | "failed"
    started_at: str
    elapsed_seconds: float
    requests_sent: int
    requests_succeeded: int
    requests_failed: int


async def _run_load_job(job_id: str, target_url: str, target_name: str, duration_seconds: int, rps: int):
    job = _jobs[job_id]
    interval = 1.0 / rps
    end_time = time.monotonic() + duration_seconds

    async with httpx.AsyncClient(timeout=5.0) as client:
        while time.monotonic() < end_time:
            if job["status"] == "stopped":
                break

            tick_start = time.monotonic()

            async def fire():
                try:
                    resp = await client.get(target_url)
                    if resp.status_code < 500:
                        job["requests_succeeded"] += 1
                    else:
                        job["requests_failed"] += 1
                except Exception:
                    job["requests_failed"] += 1
                finally:
                    job["requests_sent"] += 1

            # Fire this tick's batch of requests concurrently rather than
            # sequentially, so requests_per_second actually reflects rate,
            # not (rate limited by single-request round-trip latency).
            await asyncio.gather(*[fire() for _ in range(rps)])

            elapsed_tick = time.monotonic() - tick_start
            sleep_for = max(0.0, interval * rps - elapsed_tick)
            # interval*rps == 1 second of "budget" per batch; sleep off
            # whatever wasn't consumed by the requests themselves.
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)

    if job["status"] != "stopped":
        job["status"] = "completed"

    global _active_job_id
    async with _lock:
        if _active_job_id == job_id:
            _active_job_id = None

    logger.info(
        f"Load job {job_id} on {target_name} finished: "
        f"status={job['status']} sent={job['requests_sent']} "
        f"ok={job['requests_succeeded']} failed={job['requests_failed']}"
    )


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/targets")
def list_targets():
    return {"targets": list(TARGETS.keys())}


@app.post("/load/start", response_model=LoadStatus)
async def start_load(req: LoadRequest):
    global _active_job_id

    if req.target not in TARGETS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown target '{req.target}'. Valid targets: {list(TARGETS.keys())}"
        )

    async with _lock:
        if _active_job_id is not None and _jobs.get(_active_job_id, {}).get("status") == "running":
            raise HTTPException(
                status_code=409,
                detail=(
                    "A load job is already running "
                    f"(job_id={_active_job_id}). Stop it before starting a new one."
                )
            )

        job_id = str(uuid.uuid4())[:8]
        job = {
            "job_id": job_id,
            "target": req.target,
            "requests_per_second": req.requests_per_second,
            "duration_seconds": req.duration_seconds,
            "status": "running",
            "started_at": datetime.utcnow().isoformat(),
            "_start_monotonic": time.monotonic(),
            "requests_sent": 0,
            "requests_succeeded": 0,
            "requests_failed": 0,
        }
        _jobs[job_id] = job
        _active_job_id = job_id

    asyncio.create_task(
        _run_load_job(
            job_id, TARGETS[req.target], req.target,
            req.duration_seconds, req.requests_per_second
        )
    )

    logger.info(
        f"Started load job {job_id}: target={req.target} "
        f"rps={req.requests_per_second} duration={req.duration_seconds}s"
    )

    return _serialize_job(job)


@app.post("/load/stop")
async def stop_load():
    global _active_job_id
    async with _lock:
        if _active_job_id is None:
            return {"message": "No active load job to stop."}
        job = _jobs.get(_active_job_id)
        if job:
            job["status"] = "stopped"
        stopped_id = _active_job_id
        _active_job_id = None
    return {"message": f"Stopped job {stopped_id}."}


@app.get("/load/status", response_model=Optional[LoadStatus])
async def load_status():
    if _active_job_id is None:
        return None
    job = _jobs.get(_active_job_id)
    if job is None:
        return None
    return _serialize_job(job)


@app.get("/load/history")
def load_history():
    return {
        "jobs": [
            _serialize_job(j) for j in
            sorted(_jobs.values(), key=lambda j: j["_start_monotonic"], reverse=True)[:20]
        ]
    }


def _serialize_job(job: dict) -> dict:
    elapsed = round(time.monotonic() - job["_start_monotonic"], 1)
    return {
        "job_id": job["job_id"],
        "target": job["target"],
        "requests_per_second": job["requests_per_second"],
        "duration_seconds": job["duration_seconds"],
        "status": job["status"],
        "started_at": job["started_at"],
        "elapsed_seconds": elapsed,
        "requests_sent": job["requests_sent"],
        "requests_succeeded": job["requests_succeeded"],
        "requests_failed": job["requests_failed"],
    }
