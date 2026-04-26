# 📈 Stock Alert Platform

> 股價異常監控與自動通知系統 — 個人 DevOps / SRE 實作專案

一個模擬生產環境的完整監控平台，當台股價格變動超過設定閾值時，自動透過 Slack 發送通知。專案涵蓋容器化、CI/CD、K8s 部署、可觀測性（Observability）與資安掃描，展示端對端的 DevOps 實踐。

---

## 📐 系統架構

```
[twstock API]
      │  每分鐘抓取股價
      ▼
[FastAPI 服務]  ──── /health ────────────────────┐
      │         ──── /price/{stock_id} ──────────┤
      │         ──── /alert/threshold ────────────┤
      │                                           │
      ▼                                     [Prometheus]
[Alert Logic]                                     │
      │  價格變動 > 閾值                           ▼
      ▼                                      [Grafana]
[AlertManager]  ─────────────────────► [Slack Webhook]
```

---

## 🛠️ 技術棧

| 類別 | 工具 |
|------|------|
| 後端服務 | Python 3.11 + FastAPI |
| 資料來源 | twstock（台股免費套件） |
| 容器化 | Docker + Docker Compose |
| 編排 | Kubernetes（k3s） |
| CI/CD | GitLab CI / GitHub Actions |
| 監控指標 | Prometheus + Grafana |
| 日誌 | Loki |
| 告警 | AlertManager → Slack |
| IaC | Terraform（GKE 版本） |
| 資安掃描 | Trivy（Container 漏洞掃描） |

---

## 🚀 快速啟動（本地 Docker Compose）

### 前置需求
- Docker 24+
- Docker Compose v2

### 啟動服務

```bash
git clone https://github.com/your-name/stock-alert-platform
cd stock-alert-platform

# 複製環境變數設定
cp .env.example .env
# 填入你的 Slack Webhook URL

# 啟動所有服務
docker compose up -d
```

### 確認服務狀態

```bash
docker compose ps

# 服務端點
# API 文件：  http://localhost:8000/docs
# Grafana：   http://localhost:3000  (admin/admin)
# Prometheus：http://localhost:9090
```

---

## 📡 API 說明

### 查詢股價
```
GET /price/{stock_id}

範例：GET /price/2330
回傳：{ "stock_id": "2330", "price": 910.0, "change_pct": 1.2 }
```

### 健康檢查
```
GET /health
回傳：{ "status": "ok", "uptime_seconds": 3600 }
```

### 設定警示閾值
```
POST /alert/threshold
Body：{ "stock_id": "2330", "threshold_pct": 3.0 }
```

---

## 🔄 CI/CD Pipeline

每次 `git push` 到 `main` 分支，自動觸發：

```
push → Build Docker Image
     → Trivy 資安掃描（發現 HIGH/CRITICAL 漏洞則中止）
     → 推送至 Container Registry
     → 部署至 K8s（kubectl rollout）
     → Smoke Test（打 /health 確認服務存活）
```

Pipeline 設定檔：`.gitlab-ci.yml` / `.github/workflows/deploy.yml`

---

## ☸️ Kubernetes 部署

```bash
# 部署至本地 k3s
kubectl apply -f k8s/

# 確認 Pod 狀態
kubectl get pods -n stock-alert

# 查看服務 log
kubectl logs -f deployment/stock-alert-api -n stock-alert
```

### K8s 資源清單

```
k8s/
├── namespace.yaml
├── deployment.yaml      # FastAPI Pod，設定 resource limit
├── service.yaml         # ClusterIP
├── ingress.yaml         # 對外路由
├── hpa.yaml             # CPU > 70% 自動擴展
├── configmap.yaml       # 環境設定
└── secret.yaml          # Slack Webhook（加密）
```

---

## 📊 監控與告警

### Grafana Dashboard

提供以下監控面板：
- 各股票價格即時走勢
- API 請求量與錯誤率（Error Rate）
- Pod CPU / Memory 使用率
- 告警觸發歷史紀錄

### 告警規則範例

當以下條件成立，自動發送 Slack 通知：
- 股價 5 分鐘內變動超過 ±3%
- API Error Rate > 5%
- Pod 重啟超過 3 次

---

## 🔒 資安設計

- **CI 階段**：Trivy 掃描 Docker image，HIGH 以上漏洞阻斷部署
- **K8s 層**：Pod 設定 `runAsNonRoot: true`、`readOnlyRootFilesystem: true`
- **Secret 管理**：敏感資訊透過 K8s Secret 注入，不寫入程式碼
- **Network Policy**：限制 Pod 間不必要的網路存取

---

## 📁 專案結構

```
stock-alert-platform/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── routers/
│   │   ├── price.py         # 股價查詢
│   │   └── alert.py         # 告警設定
│   └── services/
│       ├── stock.py         # twstock 封裝
│       └── notifier.py      # Slack 通知邏輯
├── k8s/                     # K8s manifest
├── terraform/               # GKE 資源定義
├── monitoring/
│   ├── prometheus.yml       # 抓取設定
│   ├── alertmanager.yml     # 告警路由
│   └── grafana/
│       └── dashboards/      # Dashboard JSON
├── .gitlab-ci.yml           # CI/CD Pipeline
├── Dockerfile
├── docker-compose.yml       # 本地開發用
├── .env.example
└── README.md
```

---

## 🗺️ Roadmap

- [x] Docker Compose 本地版本
- [x] GitLab CI/CD + Trivy 掃描
- [x] K8s 部署（k3s）
- [x] Prometheus + Grafana 監控
- [x] AlertManager → Slack 通知
- [ ] Terraform 部署至 GKE
- [ ] Loki 日誌整合
- [ ] HTTPS / TLS 設定

---

## 🤔 設計決策紀錄

### 為什麼選 FastAPI 而非 Flask？
FastAPI 內建 `/docs` Swagger UI 與型別驗證，開發效率高，且原生支援 async，適合 I/O 密集的股價查詢場景。

### 為什麼用 twstock 而非付費 API？
個人專案以學習為主，twstock 提供台股免費資料，穩定性足夠，且不需要申請 API key，降低上手門檻。

### HPA 的觸發條件為何設 CPU 70%？
參考 Google SRE 建議，避免過早擴展浪費資源，也避免過晚導致服務降級，70% 是常見的平衡點。

---

## 聯絡

如有任何問題或建議，歡迎開 Issue 或聯絡我。# stock-alert-platform
