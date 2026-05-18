# cost-engine/src/metrics.py

import os
import requests
import logging
from typing import Dict, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROMETHEUS_URL = os.getenv(
    "PROMETHEUS_URL",
    "http://kube-prometheus-stack-prometheus.monitoring.svc.cluster.local:9090"
)

def query_prometheus(query: str) -> List[Dict]:
    """Execute a PromQL query and return results."""
    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": query},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        if data["status"] == "success":
            return data["data"]["result"]
        return []
    except Exception as e:
        logger.error(f"Prometheus query failed: {e}")
        return []

def get_namespace_cpu_usage() -> Dict[str, float]:
    """Get actual CPU usage per namespace in cores."""
    # Removed container!="" filter — not present in cadvisor metrics
    query = """
        sum by (namespace) (
            rate(container_cpu_usage_seconds_total{
                namespace!="",
                cpu="total"
            }[5m])
        )
    """
    results = query_prometheus(query)
    logger.info(f"CPU usage results: {results}")
    return {
        r["metric"]["namespace"]: float(r["value"][1])
        for r in results
        if "namespace" in r["metric"]
    }

def get_namespace_memory_usage() -> Dict[str, float]:
    """Get actual memory usage per namespace in GB."""
    # Use container_memory_working_set_bytes without container filter
    query = """
        sum by (namespace) (
            container_memory_working_set_bytes{
                namespace!="",
                pod!=""
            }
        ) / 1024 / 1024 / 1024
    """
    results = query_prometheus(query)
    logger.info(f"Memory usage results: {results}")
    return {
        r["metric"]["namespace"]: float(r["value"][1])
        for r in results
        if "namespace" in r["metric"]
    }

def get_namespace_cpu_requests() -> Dict[str, float]:
    """Get CPU requests per namespace (what's reserved)."""
    query = """
        sum by (namespace) (
            kube_pod_container_resource_requests{
                resource="cpu",
                namespace!=""
            }
        )
    """
    results = query_prometheus(query)
    return {
        r["metric"]["namespace"]: float(r["value"][1])
        for r in results
        if "namespace" in r["metric"]
    }

def get_namespace_memory_requests() -> Dict[str, float]:
    """Get memory requests per namespace in GB."""
    query = """
        sum by (namespace) (
            kube_pod_container_resource_requests{
                resource="memory",
                namespace!=""
            }
        ) / 1024 / 1024 / 1024
    """
    results = query_prometheus(query)
    return {
        r["metric"]["namespace"]: float(r["value"][1])
        for r in results
        if "namespace" in r["metric"]
    }

def get_pod_count_by_namespace() -> Dict[str, int]:
    """Get running pod count per namespace."""
    query = """
        sum by (namespace) (
            kube_pod_status_phase{phase="Running"}
        )
    """
    results = query_prometheus(query)
    return {
        r["metric"]["namespace"]: int(float(r["value"][1]))
        for r in results
        if "namespace" in r["metric"]
    }