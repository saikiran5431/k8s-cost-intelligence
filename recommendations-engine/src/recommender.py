# recommendations-engine/src/recommender.py

import logging
from pod_metrics import (
    get_pod_cpu_usage,
    get_pod_memory_usage,
    get_pod_cpu_requests,
    get_pod_memory_requests,
    get_deployment_for_pod,
)

logger = logging.getLogger(__name__)

# Cloud pricing
CPU_COST_PER_CORE_HOUR    = 0.048
MEMORY_COST_PER_GB_HOUR   = 0.006
HOURS_PER_MONTH           = 730

# Thresholds
CPU_WASTE_THRESHOLD    = 0.1   # flag if using < 10% of requested CPU
MEMORY_WASTE_THRESHOLD = 0.2   # flag if using < 20% of requested memory
MIN_CPU_REQUEST        = 0.010 # 10m minimum CPU recommendation
MIN_MEMORY_REQUEST_GB  = 0.032 # 32Mi minimum memory recommendation
SAFETY_BUFFER          = 1.3   # recommend 30% above peak usage

SKIP_NAMESPACES = {"kube-system", "kube-public", "kube-node-lease"}

def cores_to_millicores(cores):
    return int(cores * 1000)

def gb_to_mi(gb):
    return int(gb * 1024)

def monthly_cost(cpu_cores, memory_gb):
    return (cpu_cores * CPU_COST_PER_CORE_HOUR +
            memory_gb * MEMORY_COST_PER_GB_HOUR) * HOURS_PER_MONTH

def generate_recommendations():
    """
    Analyze all pods and return actionable recommendations.

    FIX (severity/savings double-counting): previously, a pod that was both
    "idle" (near-zero usage) AND tripped the CPU/memory over-provisioned
    rules would get THREE separate issue entries (CPU, memory, AND idle),
    and their monthly_saving fields were summed together. Since "idle"
    already covers the full cost of cpu_req+mem_req, and the CPU/memory
    rules separately estimate savings from *resizing* (not removing) the
    same requests, summing all three overstated the true recoverable
    savings for idle pods by roughly 2x. Idle pods are now classified
    exclusively as IDLE_POD (skipping the separate CPU/memory issues),
    since "remove/scale to zero" is a strictly better recommendation than
    "resize" for a pod doing nothing, and it avoids overlapping savings
    claims.
    """
    cpu_usage    = get_pod_cpu_usage()
    mem_usage    = get_pod_memory_usage()
    cpu_requests = get_pod_cpu_requests()
    mem_requests = get_pod_memory_requests()
    pod_to_dep   = get_deployment_for_pod()

    recommendations = []
    summary = {
        "total_pods_analyzed": 0,
        "total_pods_flagged":  0,
        "total_monthly_waste": 0.0,
        "total_monthly_savings_possible": 0.0,
    }

    all_pods = set(
        list(cpu_usage.keys()) +
        list(cpu_requests.keys())
    )

    for (namespace, pod) in all_pods:
        if namespace in SKIP_NAMESPACES:
            continue
        if not pod:
            continue

        summary["total_pods_analyzed"] += 1

        cpu_used = cpu_usage.get((namespace, pod), 0)
        mem_used = mem_usage.get((namespace, pod), 0)
        cpu_req  = cpu_requests.get((namespace, pod), 0)
        mem_req  = mem_requests.get((namespace, pod), 0)

        if cpu_req == 0 and mem_req == 0:
            continue

        # Calculate efficiency
        cpu_eff = (cpu_used / cpu_req * 100) if cpu_req > 0 else 100
        mem_eff = (mem_used / mem_req * 100) if mem_req > 0 else 100

        issues   = []
        severity = "ok"

        is_idle = cpu_used < 0.001 and mem_used < 0.010

        if is_idle:
            # ── Idle pod: one clean issue covering full reserved cost ────
            # Deliberately skips the CPU/memory over-provisioned checks
            # below so we don't double-count savings - see fix note above.
            idle_saving = monthly_cost(cpu_req, mem_req)
            issues.append({
                "type":    "IDLE_POD",
                "message": (
                    f"Pod appears idle: CPU={cores_to_millicores(cpu_used):.2f}m, "
                    f"Memory={gb_to_mi(mem_used):.0f}Mi. "
                    f"Consider scaling down or removing."
                ),
                "monthly_saving": round(idle_saving, 2),
            })
            severity = "critical"
        else:
            # ── Rule 1: CPU over-provisioned ──────────────────────────
            if cpu_req > 0 and cpu_eff < CPU_WASTE_THRESHOLD * 100:
                recommended_cpu = max(MIN_CPU_REQUEST, cpu_used * SAFETY_BUFFER)
                cpu_saving_monthly = monthly_cost(
                    cpu_req - recommended_cpu, 0
                )
                issues.append({
                    "type":             "CPU_OVER_PROVISIONED",
                    "current_request":  f"{cores_to_millicores(cpu_req)}m",
                    "actual_usage":     f"{cores_to_millicores(cpu_used):.1f}m",
                    "recommended":      f"{cores_to_millicores(recommended_cpu)}m",
                    "efficiency":       f"{cpu_eff:.1f}%",
                    "monthly_saving":   round(cpu_saving_monthly, 2),
                    "message": (
                        f"CPU request is {cores_to_millicores(cpu_req)}m but "
                        f"actual usage is only {cores_to_millicores(cpu_used):.1f}m "
                        f"({cpu_eff:.1f}% efficient). "
                        f"Reduce to {cores_to_millicores(recommended_cpu)}m "
                        f"and save ${cpu_saving_monthly:.2f}/month."
                    )
                })
                severity = "warning" if cpu_eff > 5 else "critical"

            # ── Rule 2: Memory over-provisioned ───────────────────────
            if mem_req > 0 and mem_eff < MEMORY_WASTE_THRESHOLD * 100:
                recommended_mem = max(MIN_MEMORY_REQUEST_GB, mem_used * SAFETY_BUFFER)
                mem_saving_monthly = monthly_cost(0, mem_req - recommended_mem)
                issues.append({
                    "type":            "MEMORY_OVER_PROVISIONED",
                    "current_request": f"{gb_to_mi(mem_req)}Mi",
                    "actual_usage":    f"{gb_to_mi(mem_used)}Mi",
                    "recommended":     f"{gb_to_mi(recommended_mem)}Mi",
                    "efficiency":      f"{mem_eff:.1f}%",
                    "monthly_saving":  round(mem_saving_monthly, 2),
                    "message": (
                        f"Memory request is {gb_to_mi(mem_req)}Mi but "
                        f"actual usage is only {gb_to_mi(mem_used)}Mi "
                        f"({mem_eff:.1f}% efficient). "
                        f"Reduce to {gb_to_mi(recommended_mem)}Mi "
                        f"and save ${mem_saving_monthly:.2f}/month."
                    )
                })
                if severity != "critical":
                    severity = "warning"

        if issues:
            total_saving = sum(i.get("monthly_saving", 0) for i in issues)
            summary["total_pods_flagged"]          += 1
            summary["total_monthly_savings_possible"] += total_saving

            deployment = pod_to_dep.get((namespace, pod), "unknown")

            recommendations.append({
                "namespace":    namespace,
                "pod":          pod,
                "deployment":   deployment,
                "deployment_is_guessed": deployment == "unknown",
                "severity":     severity,
                "cpu_efficiency":    round(cpu_eff, 1),
                "memory_efficiency": round(mem_eff, 1),
                "current_cpu_request":    f"{cores_to_millicores(cpu_req)}m",
                "current_memory_request": f"{gb_to_mi(mem_req)}Mi",
                "actual_cpu_usage":       f"{cores_to_millicores(cpu_used):.1f}m",
                "actual_memory_usage":    f"{gb_to_mi(mem_used):.0f}Mi",
                "monthly_saving":         round(total_saving, 2),
                "issues":                 issues,
            })

    # Sort by monthly saving (biggest first)
    recommendations.sort(key=lambda x: x["monthly_saving"], reverse=True)

    summary["total_monthly_waste"] = round(
        sum(r["monthly_saving"] for r in recommendations), 2
    )

    return {
        "summary":        summary,
        "recommendations": recommendations,
    }
