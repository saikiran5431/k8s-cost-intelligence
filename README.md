# K8s Cost Intelligence Platform 💰

![Kubernetes](https://img.shields.io/badge/kubernetes-%23326ce5.svg?style=for-the-badge&logo=kubernetes&logoColor=white)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Prometheus](https://img.shields.io/badge/Prometheus-E6522C?style=for-the-badge&logo=Prometheus&logoColor=white)
![Grafana](https://img.shields.io/badge/grafana-%23F46800.svg?style=for-the-badge&logo=grafana&logoColor=white)
![Helm](https://img.shields.io/badge/Helm-0F1689?style=for-the-badge&logo=helm&logoColor=white)
![ArgoCD](https://img.shields.io/badge/Argo%20CD-1e0477?style=for-the-badge&logo=argo&logoColor=#d16044)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)

> A production-grade Kubernetes cost monitoring and optimization platform that detects resource waste, generates right-sizing recommendations, provides team chargeback reports, and sends Slack alerts — saving companies thousands of dollars monthly.

---

## 🎯 Problem This Solves

Most Kubernetes clusters waste **60-80% of reserved resources** because developers over-provision "just in case." There is no built-in tool to tell you:
- How much money is being wasted right now?
- Which pods are the biggest offenders?
- What exactly should you change to save money?
- Which team owns the wasteful workloads?

This platform answers all of those questions in real time.

---

## 💰 Real Results From This Deployment

| Metric | Value |
|--------|-------|
| 💸 Monthly Waste Detected | **$142.09/month** |
| 🔍 Pods Analyzed | **19 pods** |
| 🚨 Pods Flagged | **13 pods (68%)** |
| ✅ Savings Possible | **$142.09/month** |
| 📉 Worst Namespace | **workloads (2.8% efficient)** |
| 🏆 Best Namespace | **monitoring (95.8% efficient)** |

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Kubernetes Cluster                         │
│                                                                    │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────────────┐   │
│   │  frontend   │   │   backend   │   │   worker (×5 pods)  │   │
│   │ nginx:alpine│   │   httpbin   │   │      busybox        │   │
│   │ 500m CPU req│   │ 250m CPU req│   │   100m CPU each     │   │
│   └─────────────┘   └─────────────┘   └─────────────────────┘   │
│          │                 │                      │               │
│          └─────────────────┴──────────────────────┘              │
│                            │  container metrics                   │
│                            ▼                                      │
│   ┌────────────────────────────────────────────────────────┐     │
│   │                    Prometheus                           │     │
│   │              (Time-Series Database)                     │     │
│   │  ◄── cAdvisor (CPU/memory actual usage)                │     │
│   │  ◄── kube-state-metrics (requests/limits)              │     │
│   │  ◄── node-exporter (host metrics)                      │     │
│   │  ◄── cost-exporter (our custom $$ metrics)             │     │
│   └────────────────────────────────────────────────────────┘     │
│                            │                                      │
│          ┌─────────────────┼──────────────────┐                  │
│          ▼                 ▼                  ▼                   │
│   ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐       │
│   │    Cost     │  │   Grafana    │  │  AlertManager    │       │
│   │  Exporter   │  │  Dashboard   │  │  → Slack #alerts │       │
│   │  (Python)   │  │  6 panels    │  │  4 rules firing  │       │
│   └─────────────┘  └──────────────┘  └──────────────────┘       │
│          │                                                        │
│          ▼                                                        │
│   ┌────────────────┐  ┌──────────────┐  ┌──────────────────┐    │
│   │ Recommendations│  │  Chargeback  │  │    Web UI        │    │
│   │    Engine      │  │     API      │  │   Dashboard      │    │
│   │  FastAPI:8080  │  │  FastAPI:8090│  │   Nginx:80       │    │
│   └────────────────┘  └──────────────┘  └──────────────────┘    │
│                                                                    │
│   ┌────────────────────────────────────────────────────────┐     │
│   │                      ArgoCD                            │     │
│   │              (GitOps — Auto Sync)                      │     │
│   │         GitHub Push → Auto Deploy to K8s              │     │
│   └────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Cluster | Kubernetes (Minikube v1.28) | Container orchestration |
| Metrics DB | Prometheus | Time-series storage + alerting |
| Visualization | Grafana | Cost dashboards (6 panels) |
| Cost Engine | Python 3.11 + prometheus-client | Custom $$ metrics exporter |
| Recommendations | Python FastAPI | Right-sizing API |
| Web Dashboard | HTML/JS + Nginx | Beautiful cost UI |
| Chargeback | Python FastAPI | Team cost reports + CSV |
| Alerting | PrometheusRule + AlertManager | Slack notifications |
| GitOps | ArgoCD | Automated Git→K8s sync |
| Packaging | Helm 3 | One-command installation |
| K8s Monitoring | kube-prometheus-stack | Full observability stack |

---

## 📦 Project Structure

```
k8s-cost-intelligence/
│
├── cost-engine/                  # 🔧 Custom Prometheus Exporter
│   ├── src/
│   │   ├── cost_exporter.py      # Main exporter — Gauges, Counters, main loop
│   │   ├── metrics.py            # PromQL queries to Prometheus
│   │   └── pricing.py            # AWS/GCP/Azure price list + calculations
│   ├── k8s/
│   │   ├── deployment.yaml       # K8s Deployment + Service
│   │   ├── rbac.yaml             # ServiceAccount + ClusterRole + Binding
│   │   └── servicemonitor.yaml   # Prometheus scrape config
│   ├── Dockerfile
│   └── requirements.txt
│
├── recommendations-engine/       # 🧠 Right-Sizing Recommendations API
│   ├── src/
│   │   ├── api.py                # FastAPI endpoints
│   │   ├── recommender.py        # Detection rules + savings calculation
│   │   └── pod_metrics.py        # Per-pod Prometheus queries
│   ├── k8s/
│   │   ├── deployment.yaml
│   │   └── rbac.yaml
│   └── Dockerfile
│
├── web-ui/                       # 🎨 Web Dashboard
│   ├── src/
│   │   └── index.html            # Full dashboard (HTML + CSS + JS)
│   ├── nginx.conf                # Nginx reverse proxy config
│   ├── k8s/
│   │   └── deployment.yaml
│   └── Dockerfile
│
├── chargeback/                   # 💼 Team Cost Reports
│   ├── src/
│   │   ├── api.py                # FastAPI + CSV endpoint
│   │   └── chargeback.py        # Team aggregation logic
│   ├── k8s/
│   │   ├── deployment.yaml
│   │   └── team-config.yaml     # Team → namespace mapping ConfigMap
│   └── Dockerfile
│
├── monitoring/                   # 📊 Monitoring Configuration
│   ├── prometheus/
│   │   └── prometheus-values.yaml  # Helm values for kube-prometheus-stack
│   ├── grafana/
│   │   └── dashboards/
│   │       └── cost-intelligence.json  # Custom Grafana dashboard JSON
│   └── alerting/
│       ├── cost-alerts.yaml         # PrometheusRule (5 alert rules)
│       └── alertmanager-slack.yaml  # AlertManager Slack config
│
├── cluster/
│   └── namespaces/
│       └── namespaces.yaml       # monitoring, workloads, cost-system
│
├── workloads/                    # 🧪 Sample over-provisioned workloads
│   ├── frontend/deployment.yaml  # nginx (500m CPU request — intentional waste)
│   ├── backend/deployment.yaml   # httpbin (250m CPU request)
│   └── worker/deployment.yaml    # busybox ×5 (100m each)
│
├── helm/                         # 📦 Helm Chart
│   └── k8s-cost-intelligence/
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
│
├── argocd/                       # 🔄 GitOps
│   └── apps/
│
├── k8s-manifests/                # 📁 Manifests for ArgoCD sync
│   ├── cost-system/
│   └── monitoring/
│
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites

```bash
# Required tools
brew install minikube kubectl helm argocd
# Docker Desktop must be running with at least 6GB memory
```

### 1. Clone & Start Cluster

```bash
git clone https://github.com/saikiran5431/k8s-cost-intelligence
cd k8s-cost-intelligence

minikube start --cpus=4 --memory=5500 --driver=docker --kubernetes-version=v1.28.0
```

### 2. Install Monitoring Stack

```bash
kubectl apply -f cluster/namespaces/namespaces.yaml

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --values monitoring/prometheus/prometheus-values.yaml \
  --wait
```

### 3. Deploy Sample Workloads

```bash
kubectl apply -f workloads/frontend/deployment.yaml
kubectl apply -f workloads/backend/deployment.yaml
kubectl apply -f workloads/worker/deployment.yaml
```

### 4. Build & Deploy Cost Intelligence Stack

```bash
eval $(minikube docker-env)

docker build -t cost-exporter:latest cost-engine/
docker build -t recommendations-engine:latest recommendations-engine/
docker build -t web-ui:latest web-ui/
docker build -t chargeback:latest chargeback/

kubectl apply -f cost-engine/k8s/
kubectl apply -f recommendations-engine/k8s/
kubectl apply -f web-ui/k8s/
kubectl apply -f chargeback/k8s/
```

### 5. Deploy Alerts + Dashboard

```bash
kubectl apply -f monitoring/alerting/cost-alerts.yaml
kubectl apply -f monitoring/grafana/cost-dashboard-configmap.yaml
```

### 6. Access Everything

```bash
# Web UI (opens in browser automatically)
minikube service web-ui -n cost-system

# Grafana Dashboard (admin / cost-intelligence-2024)
kubectl port-forward svc/kube-prometheus-stack-grafana 3000:80 -n monitoring

# Prometheus UI
kubectl port-forward svc/kube-prometheus-stack-prometheus 9090:9090 -n monitoring

# Recommendations API + Swagger docs
kubectl port-forward svc/recommendations-engine 8080:8080 -n cost-system
# Open: http://localhost:8080/docs

# Chargeback API
kubectl port-forward svc/chargeback 8090:8090 -n cost-system
# Open: http://localhost:8090/docs

# ArgoCD UI (admin / see secret)
kubectl port-forward svc/argocd-server 8080:443 -n argocd
```

---

## 📊 Custom Prometheus Metrics

These metrics are exported by our cost-exporter and available in Prometheus/Grafana:

```promql
# Current hourly cost per namespace in USD
k8s_namespace_hourly_cost_dollars{namespace="workloads", provider="aws"}

# Projected monthly cost per namespace
k8s_namespace_monthly_cost_dollars{namespace="workloads", provider="aws"}

# Hourly waste cost (reserved but unused)
k8s_namespace_waste_hourly_cost_dollars{namespace="workloads"}

# Resource efficiency percentage
k8s_namespace_efficiency_percent{namespace="workloads"}

# CPU cost breakdown
k8s_namespace_cpu_hourly_cost_dollars{namespace="workloads"}

# Memory cost breakdown
k8s_namespace_memory_hourly_cost_dollars{namespace="workloads"}

# Total exporter scrape count (health check)
k8s_cost_exporter_scrapes_total
```

---

## 🚨 Alert Rules

| Alert | Threshold | Severity | Fires For |
|-------|-----------|----------|-----------|
| HighNamespaceWaste | waste > $0.05/hr | warning | workloads |
| CriticalNamespaceWaste | waste > $0.10/hr | critical | workloads |
| LowNamespaceEfficiency | efficiency < 10% | warning | workloads |
| HighMonthlyProjection | monthly > $5 | warning | monitoring |
| CostExporterDown | exporter unreachable | critical | — (inactive = healthy) |

---

## 🌐 API Reference

### Recommendations Engine (port 8080)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/recommendations` | All pod recommendations sorted by savings |
| GET | `/recommendations/critical` | Critical issues only |
| GET | `/recommendations/summary` | Top 3 + summary stats |
| GET | `/docs` | Swagger UI |

### Chargeback API (port 8090)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/chargeback` | Full team cost report |
| GET | `/chargeback/summary` | Summary per team |
| GET | `/chargeback/csv` | Download CSV for Finance |
| GET | `/chargeback/team/{id}` | Single team report |
| GET | `/docs` | Swagger UI |

---

## 🔐 Security — RBAC

All components follow the least-privilege principle:

```yaml
# cost-exporter only gets READ access
verbs: ["get", "list", "watch"]
resources: ["pods", "nodes", "namespaces"]
```

No component has write/delete access to the cluster.

---

## 💡 Key Engineering Decisions

| Decision | Why |
|----------|-----|
| Pull-based Prometheus over push | Centralized scrape control, detects down targets |
| Custom exporter over Kubecost | Free, open-source, full control, learning value |
| FastAPI over Flask | Auto Swagger docs, async support, type safety |
| ArgoCD for GitOps | Industry standard, visual deployment tree |
| Helm for packaging | One-command install, configurable values |
| Namespace-level costs | Maps to team ownership for chargeback |

---

## 🎓 What I Learned Building This

- Writing custom Prometheus exporters in Python
- PromQL query language for time-series data
- Kubernetes RBAC (ServiceAccount, ClusterRole, ClusterRoleBinding)
- Docker layer caching optimization
- FastAPI for production REST APIs
- AlertManager routing and Slack integration
- GitOps with ArgoCD
- Helm chart development
- Real-world K8s cost optimization strategies

---

## 👤 Author

**Saikiran** — Aspiring DevOps Engineer

- GitHub: [@saikiran5431](https://github.com/saikiran5431)

---

## ⭐ Star this repo if it helped you!

> Built as a portfolio project to demonstrate real-world DevOps skills.
> Every component is production-grade and deployable.
