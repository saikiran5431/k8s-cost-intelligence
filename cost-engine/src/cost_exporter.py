# cost-engine/src/cost_exporter.py

import time
import logging
import os
from prometheus_client import (
    start_http_server,
    Gauge,
    Counter,
    REGISTRY
)
from metrics import (
    get_namespace_cpu_usage,
    get_namespace_memory_usage,
    get_namespace_cpu_requests,
    get_namespace_memory_requests,
    get_pod_count_by_namespace
)
from pricing import calculate_hourly_cost, calculate_monthly_cost

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ── Prometheus Gauges (our custom metrics) ──────────────────────────────
#
# NOTE on label naming: these gauges are defined with a label called
# "namespace". Because this exporter's own pod lives inside the
# "cost-system" namespace, Prometheus's kubernetes_sd_config attaches its
# own target-discovery "namespace" label (= cost-system) to every series it
# scrapes from this pod. When the scraped metric ALSO defines a label
# literally called "namespace" (ours does), Prometheus's default relabeling
# keeps the target-discovery one and renames our metric's label to
# "exported_namespace" to avoid the collision.
#
# In other words: querying Prometheus directly, you will see
#   k8s_namespace_hourly_cost_dollars{exported_namespace="workloads", ...}
# NOT
#   k8s_namespace_hourly_cost_dollars{namespace="workloads", ...}
#
# Every consumer of these specific metrics (Grafana dashboards, alert
# rules, chargeback.py) must use exported_namespace, not namespace.
# This is already handled correctly in chargeback.py, the alert rules, and
# monitoring/grafana/dashboards/cost-intelligence.json - just keep it in
# mind if you add new panels or queries against these metrics.

NAMESPACE_HOURLY_COST = Gauge(
    "k8s_namespace_hourly_cost_dollars",
    "Estimated hourly cost in USD for namespace based on actual usage",
    ["namespace", "provider"]
)

NAMESPACE_MONTHLY_COST = Gauge(
    "k8s_namespace_monthly_cost_dollars",
    "Estimated monthly cost in USD for namespace based on actual usage",
    ["namespace", "provider"]
)

NAMESPACE_CPU_COST = Gauge(
    "k8s_namespace_cpu_hourly_cost_dollars",
    "Hourly CPU cost in USD per namespace",
    ["namespace"]
)

NAMESPACE_MEMORY_COST = Gauge(
    "k8s_namespace_memory_hourly_cost_dollars",
    "Hourly memory cost in USD per namespace",
    ["namespace"]
)

NAMESPACE_WASTE_COST = Gauge(
    "k8s_namespace_waste_hourly_cost_dollars",
    "Hourly cost of wasted (requested but unused) resources per namespace",
    ["namespace"]
)

NAMESPACE_EFFICIENCY = Gauge(
    "k8s_namespace_efficiency_percent",
    "Resource efficiency percentage (actual usage / requested)",
    ["namespace"]
)

COST_SCRAPE_COUNTER = Counter(
    "k8s_cost_exporter_scrapes_total",
    "Total number of cost calculation scrapes"
)

PROVIDER = os.getenv("CLOUD_PROVIDER", "aws")
SCRAPE_INTERVAL = int(os.getenv("SCRAPE_INTERVAL", "60"))

# ── Core calculation logic ───────────────────────────────────────────────

def calculate_waste(
    requested: float,
    actual: float
) -> float:
    """Calculate wasted resources (requested but not used)."""
    waste = requested - actual
    return max(0, waste)  # waste can't be negative

def compute_namespace_costs():
    """Main function: fetch metrics and compute costs for all namespaces."""
    logger.info("Starting cost computation cycle...")

    # Fetch all metrics in parallel-ish (sequential for simplicity)
    cpu_usage    = get_namespace_cpu_usage()
    mem_usage    = get_namespace_memory_usage()
    cpu_requests = get_namespace_cpu_requests()
    mem_requests = get_namespace_memory_requests()
    pod_counts   = get_pod_count_by_namespace()

    # Get all namespaces seen across any metric
    all_namespaces = set(
        list(cpu_usage.keys()) +
        list(mem_usage.keys()) +
        list(cpu_requests.keys())
    )

    # Skip system namespaces we don't care about
    skip_namespaces = {"kube-system", "kube-public", "kube-node-lease"}

    for namespace in all_namespaces:
        if namespace in skip_namespaces:
            continue

        # Get values with safe defaults
        cpu_used    = cpu_usage.get(namespace, 0)
        mem_used    = mem_usage.get(namespace, 0)
        cpu_req     = cpu_requests.get(namespace, cpu_used)
        mem_req     = mem_requests.get(namespace, mem_used)

        # Cost based on actual usage
        hourly_cost  = calculate_hourly_cost(cpu_used, mem_used, PROVIDER)
        monthly_cost = calculate_monthly_cost(hourly_cost)

        # Cost breakdown
        from pricing import get_pricing
        pricing      = get_pricing(PROVIDER)
        cpu_cost     = cpu_used * pricing["cpu_cost_per_core_hour"]
        memory_cost  = mem_used * pricing["memory_cost_per_gb_hour"]

        # Waste calculation (paying for reserved but unused)
        cpu_waste    = calculate_waste(cpu_req, cpu_used)
        mem_waste    = calculate_waste(mem_req, mem_used)
        waste_cost   = calculate_hourly_cost(cpu_waste, mem_waste, PROVIDER)

        # Efficiency = actual / requested * 100
        if cpu_req > 0 and mem_req > 0:
            cpu_eff = min(100, (cpu_used / cpu_req) * 100)
            mem_eff = min(100, (mem_used / mem_req) * 100)
            efficiency = (cpu_eff + mem_eff) / 2
        else:
            efficiency = 100.0

        # Set Prometheus metrics
        NAMESPACE_HOURLY_COST.labels(
            namespace=namespace, provider=PROVIDER
        ).set(hourly_cost)

        NAMESPACE_MONTHLY_COST.labels(
            namespace=namespace, provider=PROVIDER
        ).set(monthly_cost)

        NAMESPACE_CPU_COST.labels(namespace=namespace).set(cpu_cost)
        NAMESPACE_MEMORY_COST.labels(namespace=namespace).set(memory_cost)
        NAMESPACE_WASTE_COST.labels(namespace=namespace).set(waste_cost)
        NAMESPACE_EFFICIENCY.labels(namespace=namespace).set(efficiency)

        logger.info(
            f"[{namespace}] "
            f"hourly=${hourly_cost:.4f} "
            f"monthly=${monthly_cost:.2f} "
            f"waste=${waste_cost:.4f} "
            f"efficiency={efficiency:.1f}%"
        )

    COST_SCRAPE_COUNTER.inc()
    logger.info(f"Cost computation done. Next in {SCRAPE_INTERVAL}s")

# ── Entry point ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("EXPORTER_PORT", "8000"))
    logger.info(f"Starting K8s Cost Exporter on port {port}")
    start_http_server(port)

    while True:
        try:
            compute_namespace_costs()
        except Exception as e:
            logger.error(f"Error in cost computation: {e}")
        time.sleep(SCRAPE_INTERVAL)
