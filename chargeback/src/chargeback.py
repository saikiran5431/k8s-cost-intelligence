# chargeback/src/chargeback.py

import os
import json
import requests
import logging
from datetime import datetime, timezone
from typing import Dict, List

logger = logging.getLogger(__name__)

PROMETHEUS_URL = os.getenv(
    "PROMETHEUS_URL",
    "http://kube-prometheus-stack-prometheus.monitoring.svc.cluster.local:9090"
)

TEAM_CONFIG_PATH = os.getenv("TEAM_CONFIG_PATH", "/config/teams.json")

# Fallback team config if ConfigMap not mounted
DEFAULT_TEAMS = {
    "backend": {
        "name": "Backend Engineering",
        "email": "backend@company.com",
        "namespaces": ["workloads"],
        "budget_monthly": 50.0,
        "cost_center": "CC-001"
    },
    "platform": {
        "name": "Platform Engineering",
        "email": "platform@company.com",
        "namespaces": ["monitoring", "cost-system"],
        "budget_monthly": 100.0,
        "cost_center": "CC-002"
    }
}

def load_team_config() -> Dict:
    try:
        with open(TEAM_CONFIG_PATH) as f:
            return json.load(f)["teams"]
    except Exception:
        logger.warning("Using default team config")
        return DEFAULT_TEAMS

def query(q: str) -> List[Dict]:
    try:
        r = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": q},
            timeout=10
        )
        r.raise_for_status()
        data = r.json()
        return data["data"]["result"] if data["status"] == "success" else []
    except Exception as e:
        logger.error(f"Query failed: {e}")
        return []

def get_namespace_costs() -> Dict:
    """Fetch all cost metrics per namespace."""
    metrics = {}

    # Hourly cost
    for r in query("k8s_namespace_hourly_cost_dollars"):
        ns = r["metric"].get("exported_namespace", "")
        if ns:
            metrics.setdefault(ns, {})["hourly_cost"] = float(r["value"][1])

    # Monthly cost
    for r in query("k8s_namespace_monthly_cost_dollars"):
        ns = r["metric"].get("exported_namespace", "")
        if ns:
            metrics.setdefault(ns, {})["monthly_cost"] = float(r["value"][1])

    # Waste
    for r in query("k8s_namespace_waste_hourly_cost_dollars"):
        ns = r["metric"].get("exported_namespace", "")
        if ns:
            metrics.setdefault(ns, {})["waste_hourly"] = float(r["value"][1])

    # Efficiency
    for r in query("k8s_namespace_efficiency_percent"):
        ns = r["metric"].get("exported_namespace", "")
        if ns:
            metrics.setdefault(ns, {})["efficiency"] = float(r["value"][1])

    return metrics

def generate_chargeback_report() -> Dict:
    """Generate full chargeback report per team."""
    teams      = load_team_config()
    ns_costs   = get_namespace_costs()
    now        = datetime.now(timezone.utc)
    report     = {
        "generated_at":  now.isoformat(),
        "period":        now.strftime("%B %Y"),
        "currency":      "USD",
        "cloud_provider":"AWS",
        "teams":         [],
        "summary": {
            "total_monthly_cost":  0.0,
            "total_monthly_waste": 0.0,
            "total_teams":         len(teams),
            "over_budget_teams":   0,
        }
    }

    for team_id, team_info in teams.items():
        team_namespaces = team_info.get("namespaces", [])
        budget          = team_info.get("budget_monthly", 0)

        # Aggregate across all team namespaces
        total_hourly  = 0.0
        total_monthly = 0.0
        total_waste   = 0.0
        efficiencies  = []
        ns_breakdown  = []

        for ns in team_namespaces:
            data = ns_costs.get(ns, {})
            h    = data.get("hourly_cost",  0.0)
            m    = data.get("monthly_cost", 0.0)
            w    = data.get("waste_hourly", 0.0)
            e    = data.get("efficiency",   0.0)

            total_hourly  += h
            total_monthly += m
            total_waste   += w
            if e > 0:
                efficiencies.append(e)

            ns_breakdown.append({
                "namespace":      ns,
                "hourly_cost":    round(h, 4),
                "monthly_cost":   round(m, 2),
                "waste_hourly":   round(w, 4),
                "waste_monthly":  round(w * 730, 2),
                "efficiency":     round(e, 1),
            })

        avg_efficiency  = round(sum(efficiencies) / len(efficiencies), 1) if efficiencies else 0
        waste_monthly   = round(total_waste * 730, 2)
        budget_used_pct = round((total_monthly / budget * 100), 1) if budget > 0 else 0
        over_budget     = total_monthly > budget

        if over_budget:
            report["summary"]["over_budget_teams"] += 1

        report["summary"]["total_monthly_cost"]  += total_monthly
        report["summary"]["total_monthly_waste"] += waste_monthly

        report["teams"].append({
            "team_id":        team_id,
            "team_name":      team_info["name"],
            "email":          team_info["email"],
            "cost_center":    team_info["cost_center"],
            "namespaces":     team_namespaces,
            "budget_monthly": budget,
            "hourly_cost":    round(total_hourly, 4),
            "monthly_cost":   round(total_monthly, 2),
            "waste_hourly":   round(total_waste, 4),
            "waste_monthly":  waste_monthly,
            "avg_efficiency": avg_efficiency,
            "budget_used_pct": budget_used_pct,
            "over_budget":    over_budget,
            "status": "over_budget" if over_budget else (
                "warning" if budget_used_pct > 80 else "healthy"
            ),
            "namespace_breakdown": ns_breakdown,
        })

    # Sort by monthly cost descending
    report["teams"].sort(key=lambda x: x["monthly_cost"], reverse=True)
    report["summary"]["total_monthly_cost"]  = round(report["summary"]["total_monthly_cost"], 2)
    report["summary"]["total_monthly_waste"] = round(report["summary"]["total_monthly_waste"], 2)

    return report

def generate_csv_report(report: Dict) -> str:
    """Generate CSV for Finance team."""
    lines = [
        f"K8s Cost Chargeback Report — {report['period']}",
        f"Generated: {report['generated_at']}",
        f"Cloud Provider: {report['cloud_provider']}",
        "",
        "Team,Cost Center,Namespaces,Monthly Cost ($),Monthly Waste ($),"
        "Budget ($),Budget Used (%),Avg Efficiency (%),Status",
    ]

    for t in report["teams"]:
        ns_list = "|".join(t["namespaces"]) if t["namespaces"] else "none"
        lines.append(
            f"{t['team_name']},{t['cost_center']},{ns_list},"
            f"{t['monthly_cost']},{t['waste_monthly']},"
            f"{t['budget_monthly']},{t['budget_used_pct']},"
            f"{t['avg_efficiency']},{t['status']}"
        )

    lines += [
        "",
        "SUMMARY",
        f"Total Monthly Cost,${report['summary']['total_monthly_cost']}",
        f"Total Monthly Waste,${report['summary']['total_monthly_waste']}",
        f"Over Budget Teams,{report['summary']['over_budget_teams']}",
    ]

    return "\n".join(lines)