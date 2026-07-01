# K8s 部署說明

## 概念對照：docker-compose → K8s

| docker-compose 概念 | K8s 對應 | 說明 |
|---------------------|----------|------|
| `services.xxx` | `Deployment` | 定義要跑什麼 container |
| `container_name` | `Pod` | 實際跑起來的單位 |
| `ports: "8000:8000"` | `Service (NodePort)` | 對外開放流量 |
| `ports`（內部通訊）| `Service (ClusterIP)` | 叢集內部通訊 |
| `volumes: ./file:/path` | `ConfigMap + volumeMounts` | 設定檔掛載 |
| `volumes: named_volume` | `PersistentVolumeClaim` | 持久化資料 |
| `env_file: .env` | `Secret + envFrom` | 敏感環境變數 |
| `networks: internal` | `ClusterIP Service` | 預設行為，不對外 |
| `networks: external` | `NodePort Service` | 需要特別指定 |
| `depends_on` | `readinessProbe` | 等前置服務就緒 |
| （無）| `Namespace` | 資源隔離 |
| （無）| `DaemonSet` | 每個 Node 都跑一個 |

---

## 檔案結構

```
k8s/
├── 00-namespace.yaml           # 建立 stock-alert Namespace
├── 01-secret.yaml              # .env → K8s Secret（需填入 base64 值）
├── 02-configmap-api.yaml       # app/config.yml
├── 03-configmap-prometheus.yaml # prometheus.yml + alert_rules.yml + slo_rules.yml
├── 04-configmap-alertmanager.yaml # alertmanager.yml
├── 05-configmap-grafana.yaml   # grafana provisioning（資料源 + dashboard 路徑）
├── 06-configmap-promtail.yaml  # promtail.yml（已改為 K8s 路徑）
├── 07-configmap-tempo.yaml     # tempo.yaml
├── 08-deployment-api.yaml      # FastAPI Deployment + NodePort Service
├── 09-deployment-prometheus.yaml # Prometheus Deployment + ClusterIP Service
├── 10-deployment-grafana.yaml  # Grafana PVC + Deployment + NodePort Service
├── 11-deployment-alertmanager.yaml # AlertManager Deployment + ClusterIP Service
├── 12-deployment-loki.yaml     # Loki Deployment + ClusterIP Service
├── 13-daemonset-promtail.yaml  # Promtail DaemonSet（注意：不是 Deployment）
└── 14-deployment-tempo.yaml    # Tempo Deployment + ClusterIP Service（雙 Port）
```

---

## 啟動前準備

### 1. 安裝本地 K8s（擇一）

```bash
# 方案 A：kind（推薦，最輕量）
brew install kind
kind create cluster --name stock-alert

# 方案 B：k3d
brew install k3d
k3d cluster create stock-alert
```

### 2. Build API image 並載入叢集

```bash
# K8s 無法用 build: . 直接 build，需要先建好 image
docker build -t stock-alert-api:latest .

# 把 image 載入 kind 叢集（繞過 registry）
kind load docker-image stock-alert-api:latest --name stock-alert
```

### 3. 填入 Secret

```bash
# 產生 base64 編碼
echo -n "https://hooks.slack.com/your-webhook-url" | base64
echo -n "your-api-key" | base64

# 編輯 01-secret.yaml，填入上面產生的值
```

---

## 部署順序

```bash
# 建議依序 apply，確保依賴關係正確
kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/01-secret.yaml
kubectl apply -f k8s/02-configmap-api.yaml
kubectl apply -f k8s/03-configmap-prometheus.yaml
kubectl apply -f k8s/04-configmap-alertmanager.yaml
kubectl apply -f k8s/05-configmap-grafana.yaml
kubectl apply -f k8s/06-configmap-promtail.yaml
kubectl apply -f k8s/07-configmap-tempo.yaml
kubectl apply -f k8s/08-deployment-api.yaml
kubectl apply -f k8s/09-deployment-prometheus.yaml
kubectl apply -f k8s/10-deployment-grafana.yaml
kubectl apply -f k8s/11-deployment-alertmanager.yaml
kubectl apply -f k8s/12-deployment-loki.yaml
kubectl apply -f k8s/13-daemonset-promtail.yaml
kubectl apply -f k8s/14-deployment-tempo.yaml

# 或者一次 apply 整個目錄（順序由檔名數字決定）
kubectl apply -f k8s/
```

---

## 驗證與存取

```bash
# 查看所有資源狀態
kubectl get all -n stock-alert

# 查看 Pod 是否正常運行
kubectl get pods -n stock-alert

# 查看某個 Pod 的日誌
kubectl logs -n stock-alert deployment/api -f

# 查看 Pod 詳細狀態（排錯用）
kubectl describe pod -n stock-alert <pod-name>
```

### 存取服務（NodePort）

| 服務    | 位址                    | 說明               |
|---------|-------------------------|--------------------|
| API     | http://localhost:30800  | FastAPI REST API   |
| Grafana | http://localhost:30300  | 帳號：admin/admin  |

### 存取 ClusterIP 服務（只在叢集內部，需 port-forward）

```bash
# Prometheus
kubectl port-forward svc/prometheus 9090:9090 -n stock-alert

# AlertManager
kubectl port-forward svc/alertmanager 9093:9093 -n stock-alert

# Loki
kubectl port-forward svc/loki 3100:3100 -n stock-alert
```

---

## 重點差異總結

| 面向 | docker-compose | K8s（本檔） |
|------|---------------|-------------|
| Promtail 採集方式 | docker_sd_configs + Docker socket | kubernetes_sd_configs + /var/log/pods |
| Promtail 部署類型 | 一般 container | DaemonSet（每節點一個）|
| Prometheus 資料 | 重啟消失 | emptyDir（Pod 存活期間保留）|
| Loki 資料 | 重啟消失 | emptyDir（Pod 存活期間保留）|
| Prometheus/AlertManager 對外 | ports 對外暴露 | ClusterIP（不對外）|
| API image | 從 Dockerfile build | 需先 build + kind load |
| 資源限制 | 無設定 | 每個 Pod 都有 requests/limits |
