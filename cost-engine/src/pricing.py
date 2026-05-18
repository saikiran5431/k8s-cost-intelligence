# AWS us-east-1 on-demand pricing (per hour)
# This is what makes your project realistic!

CLOUD_PRICING = {
    "aws": {
        "cpu_cost_per_core_hour": 0.048,      # ~m5.xlarge rate per core
        "memory_cost_per_gb_hour": 0.006,     # ~m5.xlarge rate per GB
        "storage_cost_per_gb_hour": 0.0001,   # EBS gp3
    },
    "gcp": {
        "cpu_cost_per_core_hour": 0.031611,
        "memory_cost_per_gb_hour": 0.004237,
        "storage_cost_per_gb_hour": 0.00011,
    },
    "azure": {
        "cpu_cost_per_core_hour": 0.044,
        "memory_cost_per_gb_hour": 0.005,
        "storage_cost_per_gb_hour": 0.00012,
    }
}

# Node types for simulation
NODE_TYPES = {
    "standard": {
        "cpu_cores": 4,
        "memory_gb": 8,
        "hourly_cost": 0.192,
    },
    "high-memory": {
        "cpu_cores": 4,
        "memory_gb": 32,
        "hourly_cost": 0.384,
    }
}

def get_pricing(provider: str = "aws") -> dict:
    return CLOUD_PRICING.get(provider, CLOUD_PRICING["aws"])

def calculate_hourly_cost(
    cpu_cores: float,
    memory_gb: float,
    provider: str = "aws"
) -> float:
    """Calculate hourly cost for given resources."""
    pricing = get_pricing(provider)
    cpu_cost = cpu_cores * pricing["cpu_cost_per_core_hour"]
    memory_cost = memory_gb * pricing["memory_cost_per_gb_hour"]
    return round(cpu_cost + memory_cost, 6)

def calculate_monthly_cost(hourly_cost: float) -> float:
    """Convert hourly cost to monthly (730 hours/month)."""
    return round(hourly_cost * 730, 4)