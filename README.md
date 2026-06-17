# K8s Cost Intelligence Platform 💰

![Kubernetes](https://img.shields.io/badge/kubernetes-%23326ce5.svg?style=for-the-badge&logo=kubernetes&logoColor=white)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Prometheus](https://img.shields.io/badge/Prometheus-E6522C?style=for-the-badge&logo=Prometheus&logoColor=white)
![Grafana](https://img.shields.io/badge/grafana-%23F46800.svg?style=for-the-badge&logo=grafana&logoColor=white)
![Helm](https://img.shields.io/badge/Helm-0F1689?style=for-the-badge&logo=helm&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)

> A production-grade Kubernetes cost monitoring and optimization platform that detects resource waste, generates right-sizing recommendations, provides team chargeback reports, sends Slack alerts, and lets you generate live synthetic load from the dashboard to watch the numbers react in real time.

---

## 🎯 Problem This Solves

Most Kubernetes clusters waste **60-80% of reserved resources** because developers over-provision "just in case." There is no built-in tool to tell you:
- How much money is being wasted right now?
- Which pods are the biggest offenders?
- What exactly should you change to save money?
- Which team owns the wasteful workloads?

This platform answers all of those questions in real time, running entirely on your own machine via Minikube.

---

## 🆕 What's new in this version

- **Manual load generator** — a panel in the web dashboard lets you pick a target (`frontend` or `backend`), set a duration and requests/sec, and fire real in-cluster HTTP traffic at it. Watch CPU usage, cost, and efficiency numbers move live as the load runs. See [Load Generator](#-load-generator) below.
- **Fixed a Grafana dashboard bug** where the ConfigMap-deployed dashboard used `{{namespace}}` in panel legends instead of `{{exported_namespace}}` (the actual Prometheus label name after relabeling — see the comment in `cost-engine/src/cost_exporter.py` for why), causing blank/broken series legends. Both dashboard copies are now generated from the same source and stay in sync.
- **Fixed a savings double-counting bug** in the recommendations engine where a pod that was both "idle" and over-provisioned on CPU/memory could get three overlapping savings estimates summed together, inflating the total savings number. Idle pods are now classified once, cleanly.
- **Fixed stale "Refresh" button** — clicking refresh in the web UI now forces a real recompute (`?force=true`) instead of silently returning the same 60-second cached numbers.
- **Flagged guessed deployment names** — when the API can't resolve a pod's real owning Deployment from cluster metadata, the UI now visibly marks the suggested `kubectl` fix command as a guess instead of presenting it as fact.
- **Restored a cAdvisor double-count filter** in the CPU/memory usage queries (`container!=""`) that the previous comment in `metrics.py` claimed wasn't needed — it is, on most cAdvisor versions, to avoid summing the pod-aggregate row on top of per-container rows.
- **Removed the committed Slack webhook secret.** It's now a placeholder — see the comment at the top of `monitoring/alerting/alertmanager-slack.yaml` for how to supply your real one without committing it.

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

> Note: these numbers were captured before the idle-pod double-counting fix above. Expect a somewhat lower (more accurate) total savings figure after re-running on this version.

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
│          ▲                 ▲                      │               │
│          │  load traffic   │                       │               │
│   ┌─────────────────┐      │                       │               │
│   │  Load Generator │──────┘                       │               │
│   │  (new, FastAPI)  │                              │               │
│   └─────────────────┘                              │               │
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
│   │                │  │              │  │  + Load Gen UI   │    │
│   └────────────────┘  └──────────────┘  └──────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

This project runs entirely on a local Minikube cluster. "Live" here means the dashboard reflects real-time changes on your own machine as workloads run and as you trigger load — not a publicly hosted deployment.

---

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Cluster | Kubernetes (Minikube) | Container orchestration, runs locally on any OS |
| Metrics DB | Prometheus | Time-series storage + alerting |
| Visualization | Grafana | Cost dashboards (6 panels) |
| Cost Engine | Python 3.11 + prometheus-client | Custom $$ metrics exporter |
| Recommendations | Python FastAPI | Right-sizing API |
| Load Generator | Python FastAPI + httpx | Configurable in-cluster traffic generation |
| Web Dashboard | HTML/JS + Nginx | Cost UI + load generator controls |
| Chargeback | Python FastAPI | Team cost reports + CSV |
| Alerting | PrometheusRule + AlertManager | Slack notifications |
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
├── load-generator/               # ⚡ NEW: Manual load generator
│   ├── src/
│   │   └── api.py                # FastAPI endpoints: /load/start, /load/stop, /load/status
│   ├── k8s/
│   │   └── deployment.yaml
│   └── Dockerfile
│
├── web-ui/                       # 🎨 Web Dashboard
│   ├── src/
│   │   └── index.html            # Full dashboard + load generator panel
│   ├── nginx.conf                # Proxies /api/ and /load-api/
│   ├── k8s/
│   │   └── deployment.yaml
│   └── Dockerfile
│
├── chargeback/                   # 💼 Team Cost Reports
│   ├── src/
│   │   ├── api.py
│   │   └── chargeback.py
│   ├── k8s/
│   │   ├── deployment.yaml
│   │   └── team-config.yaml
│   └── Dockerfile
│
├── monitoring/                   # 📊 Monitoring Configuration
│   ├── prometheus/
│   │   └── prometheus-values.yaml
│   ├── grafana/
│   │   ├── dashboards/
│   │   │   └── cost-intelligence.json
│   │   └── cost-dashboard-configmap.yaml
│   ├── alerting/
│   │   ├── cost-alerts.yaml
│   │   ├── alertmanager-config.yaml
│   │   └── alertmanager-slack.yaml
│   └── multi-cloud-config.yaml
│
├── cluster/
│   └── namespaces/
│       └── namespaces.yaml
│
├── workloads/                    # 🧪 Sample over-provisioned workloads
│   ├── frontend/deployment.yaml
│   ├── backend/deployment.yaml
│   └── worker/deployment.yaml
│
├── helm/                         # 📦 Helm Chart
│   ├── index.yaml
│   └── k8s-cost-intelligence/
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
│
├── k8s-manifests/                # 📁 Flat manifest mirror (kubectl apply -R friendly)
│   ├── namespaces.yaml
│   ├── cost-system/
│   └── monitoring/
│
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites

This project runs the same way on macOS, Linux, and Windows (via WSL2). You need: Docker (Desktop on Mac/Windows, Docker Engine on Linux), Minikube, kubectl, and Helm.

**macOS:**
```bash
brew install minikube kubectl helm
```

**Linux:**
```bash
# kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# minikube
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube

# helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

**Windows (via WSL2 — recommended) or native PowerShell with winget:**
```powershell
winget install Kubernetes.minikube
winget install Kubernetes.kubectl
winget install Helm.Helm
```
Native Windows (PowerShell) works for the `kubectl`/`helm`/cluster steps below, but Docker image builds and shell scripts below assume a bash-compatible shell — running everything inside WSL2 (Ubuntu) avoids translating commands.

Whatever OS you're on, Docker must be running with at least 6GB memory allocated (Docker Desktop → Settings → Resources, or for Linux, just make sure your host has 6GB+ free).

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
# On Windows PowerShell (without WSL2), use instead:
#   minikube docker-env | Invoke-Expression

docker build -t cost-exporter:latest cost-engine/
docker build -t recommendations-engine:latest recommendations-engine/
docker build -t web-ui:latest web-ui/
docker build -t chargeback:latest chargeback/
docker build -t load-generator:latest load-generator/

kubectl apply -f cost-engine/k8s/
kubectl apply -f recommendations-engine/k8s/
kubectl apply -f web-ui/k8s/
kubectl apply -f chargeback/k8s/
kubectl apply -f load-generator/k8s/
```

### 5. Deploy Alerts + Dashboard

```bash
kubectl apply -f monitoring/alerting/cost-alerts.yaml
kubectl apply -f monitoring/grafana/cost-dashboard-configmap.yaml
```

If you want Slack alerts, first edit `monitoring/alerting/alertmanager-slack.yaml` locally with your own webhook URL (never commit that edit — see the comment at the top of that file), then:
```bash
kubectl apply -f monitoring/alerting/alertmanager-slack.yaml
```

### 6. Access Everything

```bash
# Web UI (opens in browser automatically) — includes the load generator panel
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

# Load Generator API (normally only reached via the web UI's /load-api/ proxy,
# but useful directly for debugging)
kubectl port-forward svc/load-generator 8070:8070 -n cost-system
# Open: http://localhost:8070/docs
```

---

## ⚡ Load Generator

The web UI has a "Generate Load" button in the header that opens a panel where you choose:
- **Target**: `frontend` (nginx) or `backend` (httpbin) — both in the `workloads` namespace
- **Duration**: 1–300 seconds
- **Requests/sec**: 1–200

Clicking Start sends the request to a dedicated `load-generator` pod running inside `cost-system`, which then issues real HTTP requests over the cluster network directly to the target Service's ClusterIP — the same path actual production traffic takes. You'll see live request counts (sent/succeeded/failed) while it runs, and the dashboard automatically forces a fresh recommendation recompute the moment the job finishes, so you don't have to wait up to 60 seconds to see the effect.

This is deliberately a separate pod rather than reusing an existing service, so the load generator's own resource usage doesn't get attributed to (and skew the cost numbers of) an unrelated component. It also only allows a fixed, hardcoded set of targets (no free-text URLs) since it runs with cluster-internal network access.

You can also drive it directly via its API if you prefer:
```bash
curl -X POST http://localhost:8070/load/start \
  -H "Content-Type: application/json" \
  -d '{"target": "frontend", "duration_seconds": 30, "requests_per_second": 20}'

curl http://localhost:8070/load/status

curl -X POST http://localhost:8070/load/stop
```

---

## 📊 Custom Prometheus Metrics

These metrics are exported by our cost-exporter and available in Prometheus/Grafana. Note the label is `exported_namespace`, not `namespace` — see the comment block in `cost-engine/src/cost_exporter.py` for why.

```promql
# Current hourly cost per namespace in USD
k8s_namespace_hourly_cost_dollars{exported_namespace="workloads", provider="aws"}

# Projected monthly cost per namespace
k8s_namespace_monthly_cost_dollars{exported_namespace="workloads", provider="aws"}

# Hourly waste cost (reserved but unused)
k8s_namespace_waste_hourly_cost_dollars{exported_namespace="workloads"}

# Resource efficiency percentage
k8s_namespace_efficiency_percent{exported_namespace="workloads"}

# CPU cost breakdown
k8s_namespace_cpu_hourly_cost_dollars{exported_namespace="workloads"}

# Memory cost breakdown
k8s_namespace_memory_hourly_cost_dollars{exported_namespace="workloads"}

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
| GET | `/recommendations` | All pod recommendations sorted by savings. Add `?force=true` to bypass the 60s cache. |
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

### Load Generator API (port 8070)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/targets` | List valid load targets |
| POST | `/load/start` | Start a job: `{target, duration_seconds, requests_per_second}` |
| POST | `/load/stop` | Stop the currently running job |
| GET | `/load/status` | Current job status (or `null` if none running) |
| GET | `/load/history` | Last 20 jobs |
| GET | `/docs` | Swagger UI |

---

## 🔐 Security — RBAC

All components follow the least-privilege principle:

```yaml
# cost-exporter only gets READ access
verbs: ["get", "list", "watch"]
resources: ["pods", "nodes", "namespaces"]
```

No component has write/delete access to the cluster. The load-generator has no RBAC/ServiceAccount at all — it only makes outbound HTTP calls to other in-cluster Services and never talks to the Kubernetes API.

---

## 💡 Key Engineering Decisions

| Decision | Why |
|----------|-----|
| Pull-based Prometheus over push | Centralized scrape control, detects down targets |
| Custom exporter over Kubecost | Free, open-source, full control, learning value |
| FastAPI over Flask | Auto Swagger docs, async support, type safety |
| Helm for packaging | One-command install, configurable values |
| Namespace-level costs | Maps to team ownership for chargeback |
| Load generator as its own pod | Keeps generated traffic's own resource cost separate from the components being measured, and mirrors how real traffic actually reaches these services |
| Fixed allowlist of load targets | The load generator has cluster network access; a free-text URL field would make it an internal SSRF pivot |

---

## 🎓 What I Learned Building This

- Writing custom Prometheus exporters in Python
- PromQL query language for time-series data
- Kubernetes RBAC (ServiceAccount, ClusterRole, ClusterRoleBinding)
- Docker layer caching optimization
- FastAPI for production REST APIs, including background async tasks for long-running jobs
- AlertManager routing and Slack integration
- Helm chart development
- Real-world K8s cost optimization strategies
- Debugging Prometheus label relabeling collisions (`namespace` → `exported_namespace`)

---

## 👤 Author

**Saikiran** — Aspiring DevOps Engineer

- GitHub: [@saikiran5431](https://github.com/saikiran5431)

---

## ⭐ Star this repo if it helped you!

> Built as a portfolio project to demonstrate real-world DevOps skills.
> Every component is production-grade and deployable.
