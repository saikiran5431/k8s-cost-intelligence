# recommendations-engine/src/pod_metrics.py

import os
import requests
import logging

logger = logging.getLogger(__name__)

PROMETHEUS_URL = os.getenv(
    "PROMETHEUS_URL",
    "http://kube-prometheus-stack-prometheus.monitoring.svc.cluster.local:9090"
)

def query(q):
    try:
        r = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": q},
            timeout=10
        )
        r.raise_for_status()
        data = r.json()
        if data["status"] == "success":
            return data["data"]["result"]
        return []
    except Exception as e:
        logger.error(f"Query failed: {e}")
        return []

def get_pod_cpu_usage():
    """Actual CPU usage per pod in cores."""
    results = query("""
        sum by (pod, namespace) (
            rate(container_cpu_usage_seconds_total{
                cpu="total", namespace!=""
            }[10m])
        )
    """)
    return {
        (r["metric"].get("namespace",""), r["metric"].get("pod","")): float(r["value"][1])
        for r in results
        if r["metric"].get("pod")
    }

def get_pod_memory_usage():
    """Actual memory usage per pod in GB."""
    results = query("""
        sum by (pod, namespace) (
            container_memory_working_set_bytes{
                pod!="", namespace!=""
            }
        ) / 1024 / 1024 / 1024
    """)
    return {
        (r["metric"].get("namespace",""), r["metric"].get("pod","")): float(r["value"][1])
        for r in results
        if r["metric"].get("pod")
    }

def get_pod_cpu_requests():
    """CPU requests per pod in cores."""
    results = query("""
        sum by (pod, namespace) (
            kube_pod_container_resource_requests{
                resource="cpu", namespace!=""
            }
        )
    """)
    return {
        (r["metric"].get("namespace",""), r["metric"].get("pod","")): float(r["value"][1])
        for r in results
        if r["metric"].get("pod")
    }

def get_pod_memory_requests():
    """Memory requests per pod in GB."""
    results = query("""
        sum by (pod, namespace) (
            kube_pod_container_resource_requests{
                resource="memory", namespace!=""
            }
        ) / 1024 / 1024 / 1024
    """)
    return {
        (r["metric"].get("namespace",""), r["metric"].get("pod","")): float(r["value"][1])
        for r in results
        if r["metric"].get("pod")
    }

def get_deployment_for_pod():
    """Map pod name to its deployment."""
    results = query("""
        kube_pod_owner{owner_kind="ReplicaSet"}
    """)
    rs_to_pod = {}
    for r in results:
        pod = r["metric"].get("pod","")
        rs  = r["metric"].get("owner_name","")
        ns  = r["metric"].get("namespace","")
        if pod and rs:
            rs_to_pod[(ns, rs)] = pod

    results2 = query("""
        kube_replicaset_owner{owner_kind="Deployment"}
    """)
    pod_to_deployment = {}
    for r in results2:
        rs   = r["metric"].get("replicaset","")
        dep  = r["metric"].get("owner_name","")
        ns   = r["metric"].get("namespace","")
        for (rns, rrs), pod in rs_to_pod.items():
            if rns == ns and rrs == rs:
                pod_to_deployment[(ns, pod)] = dep
    return pod_to_deployment
