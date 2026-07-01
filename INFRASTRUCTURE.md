# Infrastructure 說明文件

> 適合初次接手此專案的 SRE / DevOps 人員閱讀。  
> 說明各服務 Port、容器設定、網路架構、監控設定與告警規則。

---

## 目錄

1. [系統架構總覽](#1-系統架構總覽)
2. [Port 對應總表](#2-port-對應總表)
3. [Docker 容器規格](#3-docker-容器規格)
4. [網路架構](#4-網路架構)
5. [各設定檔詳解](#5-各設定檔詳解)
6. [告警規則說明](#6-告警規則說明)
7. [SLI / SLO 定義](#7-sli--slo-定義)
8. [Grafana 資料源與 Dashboard](#8-grafana-資料源與-dashboard)
9. [安全注意事項](#9-安全注意事項)
10. [快速啟動與驗證](#10-快速啟動與驗證)

---

## 1. 系統架構總覽

```
外部資料來源                 應用層                    通知
──────────────      ─────────────────────      ──────────────
twstock API    →    FastAPI (port 8000)    →    Slack Webhook
（台股免費 API）     APScheduler (每 1 分鐘)
                    Circuit Breaker (pybreaker)
                    Retry (tenacity)

可觀測性（Observability Stack）
───────────────────────────────────────────────────────────
Metrics:  FastAPI /metrics → Prometheus (9090) → Grafana (3000)
Logs:     Docker logs → Promtail → Loki (3100)  → Grafana (3000)
Traces:   FastAPI OTLP → Tempo (4317/3200)      → Grafana (3000)
Alerts:   Prometheus → AlertManager (9093) → Slack
```

---

## 2. Port 對應總表

| 服務           | 容器名稱           | Host Port | Container Port | 協定  | 對外？ | 用途                              |
|----------------|-------------------|-----------|----------------|-------|--------|-----------------------------------|
| FastAPI (api)  | stock-alert-api   | 8000      | 8000           | HTTP  | 是     | REST API、/metrics、/health       |
| Prometheus     | prometheus        | 9090      | 9090           | HTTP  | 是 *   | 指標儲存與查詢（PromQL）           |
| Grafana        | grafana           | 3000      | 3000           | HTTP  | 是     | 視覺化 Dashboard（帳密 admin/admin）|
| AlertManager   | alertmanager      | 9093      | 9093           | HTTP  | 是 *   | 告警路由與通知管理                 |
| Loki           | loki              | 3100      | 3100           | HTTP  | 是 *   | 日誌聚合儲存                       |
| Promtail       | promtail          | —         | —              | —     | 否     | 日誌採集（純 agent，無需對外）     |
| Tempo          | tempo             | 3200      | 3200           | HTTP  | 是     | Trace 查詢 HTTP 端點               |
| Tempo (OTLP)   | tempo             | 4317      | 4317           | gRPC  | 是     | 接收 OpenTelemetry Traces          |

> **\* 備註**：Prometheus（9090）、AlertManager（9093）、Loki（3100）在 docker-compose.yml 中有 port mapping，但在生產環境**不應對外開放**，建議移除 ports 區塊，僅供容器內部通訊。

### Port 用途補充說明

| Port | 誰會連進來                           | 誰會主動連出去                     |
|------|--------------------------------------|------------------------------------|
| 8000 | 使用者 / curl / Prometheus scrape    | twstock API、Slack Webhook         |
| 9090 | Grafana（讀取指標）                  | AlertManager（推送告警）           |
| 9093 | Prometheus（推送告警）               | Slack Webhook（送通知）            |
| 3000 | 使用者瀏覽器                         | Prometheus / Loki / Tempo（查詢）  |
| 3100 | Promtail（推送日誌）/ Grafana（查詢）| —                                  |
| 3200 | Grafana（查詢 Traces）               | —                                  |
| 4317 | FastAPI（推送 OTLP Traces）          | —                                  |
| 9080 | —（Promtail 內部）                   | Loki:3100                          |

---

## 3. Docker 容器規格

> 目前 docker-compose.yml **未設定 CPU / Memory limits**，所有服務使用 Host 資源上限。  
> 建議正式環境補上 `deploy.resources.limits` 以避免單一服務耗盡主機資源。

### 3.1 api（FastAPI 應用）

| 項目           | 值                                              |
|----------------|-------------------------------------------------|
| 映像來源       | 本機 `Dockerfile` build（python:3.13-slim）     |
| 容器名稱       | `stock-alert-api`                               |
| 工作目錄       | `/code`                                         |
| 啟動指令       | `fastapi run app/main.py --host 0.0.0.0 --port 8000` |
| 環境變數       | 從 `.env` 讀取（SLACK_WEBHOOK_URL、API_KEY）    |
| 掛載 Volume    | `./app/config.yml → /code/app/config.yml`（熱更新用）|
| 所屬網路       | `internal`、`external`（雙網路）                |
| CPU/Memory     | 未限制                                          |

**Dockerfile 說明：**
```dockerfile
FROM python:3.13-slim          # 輕量化 Python 3.13 基礎映像
WORKDIR /code                  # 應用程式放在 /code
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt  # 先裝依賴再 COPY 程式碼（利用 layer cache）
COPY . .
EXPOSE 8000
CMD ["fastapi", "run", "app/main.py", "--host", "0.0.0.0", "--port", "8000"]
```

### 3.2 prometheus

| 項目        | 值                                                   |
|-------------|------------------------------------------------------|
| 映像        | `prom/prometheus`（latest）                          |
| 容器名稱    | `prometheus`                                         |
| 掛載設定檔  | `prometheus.yml`、`alert_rules.yml`、`slo_rules.yml` |
| 儲存        | 無 named volume（重啟後資料清除）                    |
| 所屬網路    | `internal` 僅限                                      |
| CPU/Memory  | 未限制                                               |

### 3.3 grafana

| 項目        | 值                                                                       |
|-------------|--------------------------------------------------------------------------|
| 映像        | `grafana/grafana`（latest）                                              |
| 容器名稱    | `grafana`                                                                |
| 預設帳密    | `admin / admin`（GF_SECURITY_ADMIN_PASSWORD 環境變數）                   |
| 掛載 Volume | `grafana_data`（named volume，重啟後保留）                               |
| 掛載設定    | `provisioning/`（自動設定資料源）、`dashboards/`（自動載入 Dashboard）   |
| 所屬網路    | `internal`、`external`（供瀏覽器存取）                                   |
| depends_on  | prometheus（須先啟動）                                                   |

### 3.4 alertmanager

| 項目        | 值                                                 |
|-------------|----------------------------------------------------|
| 映像        | `prom/alertmanager`（latest）                      |
| 容器名稱    | `alertmanager`                                     |
| 啟動參數    | `--config.file=/etc/alertmanager/alertmanager.yml` |
| 掛載設定檔  | `alertmanager.yml`                                 |
| 環境變數    | 從 `.env` 讀取（未直接使用，供 template 使用）     |
| 所屬網路    | `internal` 僅限                                    |

### 3.5 loki

| 項目        | 值                                        |
|-------------|-------------------------------------------|
| 映像        | `grafana/loki:latest`                     |
| 容器名稱    | `loki`                                    |
| 啟動參數    | `-config.file=/etc/loki/local-config.yaml`（使用預設內建設定）|
| 儲存        | 無 named volume（重啟後日誌清除）         |
| 所屬網路    | `internal` 僅限                           |

### 3.6 promtail

| 項目        | 值                                                          |
|-------------|-------------------------------------------------------------|
| 映像        | `grafana/promtail:latest`                                   |
| 容器名稱    | `promtail`                                                  |
| 掛載 Volume | `/var/lib/docker/containers`（唯讀，採集 container logs）   |
| 掛載 Socket | `/var/run/docker.sock`（Docker API，自動發現容器）          |
| 所屬網路    | `internal` 僅限                                             |

### 3.7 tempo

| 項目        | 值                                               |
|-------------|--------------------------------------------------|
| 映像        | `grafana/tempo:latest`                           |
| 容器名稱    | （未設定，使用預設名稱）                         |
| 啟動參數    | `-config.file=/etc/tempo.yaml`                   |
| 掛載設定檔  | `tempo.yml`                                      |
| 儲存        | 寫入容器內 `/tmp/tempo/`（重啟後 Trace 清除）    |
| 所屬網路    | `internal` 僅限                                  |

---

## 4. 網路架構

```
                  ┌──────── external network ────────┐
                  │                                   │
  瀏覽器 ─────────┤ grafana:3000   api:8000           │
  curl    ────────┤                                   │
                  └───────────────────────────────────┘
                  ┌──────── internal network ─────────────────────────────┐
                  │                                                        │
                  │  api:8000  ←── prometheus:9090 (scrape /metrics)      │
                  │       ↓                  ↓ (評估 alert_rules)         │
                  │  loki:3100 ←── promtail  alertmanager:9093 → Slack    │
                  │       ↑                                                │
                  │  tempo:3200 ←── api (OTLP gRPC → 4317)               │
                  │       ↑                                                │
                  │  grafana:3000 ─── 查詢 prometheus/loki/tempo          │
                  └────────────────────────────────────────────────────────┘
```

**兩個 bridge network 的設計原因：**
- `internal`：所有服務互通，不直接暴露 Host
- `external`：只有 `api` 和 `grafana` 加入，代表這兩個服務才需要被外部存取
- Prometheus、AlertManager、Loki 等內部服務只在 `internal` 網路，無法從外部直接連線（安全考量）

---

## 5. 各設定檔詳解

### 5.1 `app/config.yml`（股票監控設定）

```yaml
stocks:
  - id: "2330"
    name: "台積電"
    threshold_pct: 3.0   # 漲跌超過 3% 觸發 Slack 通知
  - id: "2454"
    name: "聯發科"
    threshold_pct: 2.5   # 漲跌超過 2.5% 觸發 Slack 通知
```

- Scheduler 每次執行都會**重新讀取**此檔，修改後 1 分鐘內生效，無需重啟服務
- 新增股票：在 stocks 下加一個 `- id / name / threshold_pct` 條目即可

### 5.2 `monitoring/prometheus.yml`（指標抓取設定）

```yaml
global:
  scrape_interval: 15s        # 每 15 秒抓一次所有 targets 的指標

scrape_configs:
  - job_name: "stock-alert-api"
    static_configs:
      - targets: ["api:8000"] # 抓取 FastAPI 的 /metrics 端點

rule_files:
  - "alert_rules.yml"         # 告警規則
  - "slo_rules.yml"           # SLI/SLO recording rules

alerting:
  alertmanagers:
    - static_configs:
        - targets: ["alertmanager:9093"]  # 告警發送目標
```

### 5.3 `monitoring/alertmanager.yml`（告警路由設定）

| 設定項目        | 值      | 說明                                       |
|-----------------|---------|--------------------------------------------|
| resolve_timeout | 5m      | 告警解除後等 5 分鐘再發「已解除」通知     |
| group_wait      | 10s     | 同一批告警等 10 秒後一起發送（避免洗版）  |
| group_interval  | 5m      | 同一 group 每 5 分鐘才能再發一次          |
| repeat_interval | 1h      | 未解除的告警每小時重複提醒一次            |

**告警路由：**
- `severity: critical` → `#alert` 頻道，紅色 (#FF0000)
- `severity: warning` → `#alert` 頻道，橘色 (#FFA500)

**Inhibit Rule（抑制規則）：**  
若同一 `alertname` 已有 critical 告警在發送，warning 告警會被自動抑制，避免重複打擾。

> **安全警告**：目前 `alertmanager.yml` 內含明文 Slack Webhook URL，請務必不要 commit 此檔案到公開 repo。  
> 正確做法是使用 `alertmanager.yml.template` + `start.sh` 的 `envsubst` 機制，從環境變數注入 URL。

### 5.4 `monitoring/alertmanager.yml.template`（安全版本模板）

`slack_api_url` 欄位留空，由 `start.sh` 執行 `envsubst` 從 `.env` 的 `SLACK_WEBHOOK_URL` 注入後產生正式的 `alertmanager.yml`。

```bash
# start.sh 做的事
export SLACK_WEBHOOK_URL=$(grep SLACK_WEBHOOK_URL .env | cut -d '=' -f2)
envsubst < ./monitoring/alertmanager.yml.template > ./monitoring/alertmanager.yml
docker compose up -d
```

### 5.5 `monitoring/promtail.yml`（日誌採集設定）

```yaml
server:
  http_listen_port: 9080    # Promtail 自身的管理端點（容器內部）

clients:
  - url: http://loki:3100/loki/api/v1/push  # 推送目標

scrape_configs:
  - job_name: containers
    docker_sd_configs:
      - host: unix:///var/run/docker.sock   # 透過 Docker socket 自動發現容器
        refresh_interval: 5s
    relabel_configs:
      - source_labels: ['__meta_docker_container_name']
        regex: '/(.*)'
        target_label: 'container'           # 以容器名稱作為 label
```

Promtail 會採集所有 Docker 容器的 stdout/stderr 日誌並推送到 Loki。  
在 Grafana Explore 介面可用 `{container="stock-alert-api"}` 查詢 API 日誌。

### 5.6 `monitoring/tempo.yml`（分散式追蹤設定）

```yaml
server:
  http_listen_port: 3200    # Grafana 查詢 Trace 的 HTTP 端點

distributor:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: 0.0.0.0:4317  # 接收 FastAPI 發來的 OTLP gRPC Traces

storage:
  trace:
    backend: local
    local:
      path: /tmp/tempo/traces     # 存在容器內，重啟後清除
    wal:
      path: /tmp/tempo/wal        # Write-Ahead Log
```

FastAPI 啟動時會透過 `app/tracer.py` 設定 OTLP exporter 指向 `tempo:4317`。

---

## 6. 告警規則說明

定義於 `monitoring/alert_rules.yml`，由 Prometheus 評估，觸發後送至 AlertManager。

| 告警名稱               | 嚴重等級 | 觸發條件                                           | 等待時間 | 說明                                             |
|------------------------|----------|----------------------------------------------------|----------|--------------------------------------------------|
| `APIDown`              | critical | `up{job="stock-alert-api"} == 0`                  | 1m       | Prometheus 無法 scrape API，服務可能掛掉         |
| `HighAPILatency`       | warning  | `sli:latency_p95:rate5m > 0.5`                    | 1m       | P95 延遲超過 500ms                               |
| `APIHighErrorRate`     | critical | 5xx 錯誤率 > 1%                                   | 1m       | API 大量回傳錯誤                                 |
| `SchedulerStopped`     | critical | 5 分鐘內 scheduler 執行次數為 0                   | 3m       | 排程器停止，股價監控中斷                         |
| `StockDataStale`       | warning  | `sli:scheduler_staleness:seconds > 90`            | 1m       | 距上次成功執行超過 90 秒，資料可能過期           |
| `StockFetchHighFailRate`| warning | `sli:fetch_success_rate:rate5m < 0.8`             | 2m       | 股價查詢成功率低於 80%                           |
| `SLOAvailabilityBreach`| warning  | `sli:http_availability:rate5m < 0.995`            | 5m       | HTTP API 可用性低於 SLO 目標 99.5%               |
| `CircuitBreakerOpen`   | warning  | `increase(circuit_breaker_open_total[5m]) > 0`    | 0m（即時）| Circuit Breaker 開啟，twstock 連線失敗次數過多  |

---

## 7. SLI / SLO 定義

定義於 `monitoring/slo_rules.yml`，每 30 秒計算一次 Recording Rule。

| Recording Rule                      | 計算公式                                                                 | SLO 目標         |
|-------------------------------------|--------------------------------------------------------------------------|------------------|
| `sli:fetch_success_rate:rate5m`     | 成功查詢次數 / 總查詢次數（5 分鐘滾動窗口）                             | ≥ 80%（fetch）   |
| `sli:scheduler_staleness:seconds`   | `time() - scheduler_last_success_timestamp`                             | < 90 秒          |
| `sli:http_availability:rate5m`      | 2xx 請求數 / 總請求數（5 分鐘滾動窗口）                                 | ≥ 99.5%          |
| `sli:latency_p95:rate5m`            | P95 請求延遲（histogram_quantile 0.95）                                  | < 500ms          |
| `sli:scheduler_run_rate:rate5m`     | Scheduler 每秒執行次數（正常約 0.0167/s = 每分鐘 1 次）                 | > 0              |

### Grafana Dashboard 顏色閾值設計

| Panel             | 黃色（警示）| 紅色（緊急）| 依據                          |
|-------------------|-------------|-------------|-------------------------------|
| Scheduler 新鮮度  | 90s         | 180s        | StockDataStale 告警 90s       |
| HTTP 成功率       | 0.99        | 0.995       | SLO 目標 99.5%                |
| P95 延遲          | 0.3s        | 0.5s        | HighAPILatency 告警 500ms     |
| Error Budget      | 0.25        | 0.1         | 低於 25% 警示，低於 10% 緊急  |

---

## 8. Grafana 資料源與 Dashboard

### 資料源（自動 Provisioning）

設定於 `monitoring/grafana/provisioning/datasources/prometheus.yml`：

| 資料源名稱  | 類型       | URL                    | 預設 |
|-------------|------------|------------------------|------|
| Prometheus  | prometheus | http://prometheus:9090 | 是   |
| Loki        | loki       | http://loki:3100       | 否   |
| Tempo       | tempo      | http://tempo:3200      | 否   |

Tempo 已設定 **Trace → Logs 關聯**：點選 Trace 可直接跳轉到 Loki 查對應時間的日誌。

### Dashboard（自動 Provisioning）

設定於 `monitoring/grafana/provisioning/dashboards/dashboard.yml`，從 `/etc/grafana/dashboards` 自動載入：

| 檔案                    | 內容                              |
|-------------------------|-----------------------------------|
| `dashboard.json`        | 股價、API 指標、Circuit Breaker   |
| `slo.dashboard.json`    | SLI/SLO 成功率、新鮮度、Error Budget |

**allowUiUpdates: true**：允許在 Grafana UI 直接修改 Dashboard 並儲存（開發環境方便調整）。

---

## 9. 安全注意事項

| 問題                              | 風險等級 | 建議處理方式                                                    |
|-----------------------------------|----------|-----------------------------------------------------------------|
| `alertmanager.yml` 內含明文 Webhook URL | 高   | 使用 `alertmanager.yml.template` + `start.sh` 動態生成，並將 `alertmanager.yml` 加入 `.gitignore` |
| Prometheus / AlertManager 對外開放 | 中   | 移除 docker-compose.yml 中的 `ports`，改為僅 `internal` 網路   |
| Grafana 預設密碼 admin/admin       | 中   | 修改 `GF_SECURITY_ADMIN_PASSWORD` 環境變數                      |
| Tempo / Loki 資料存放於容器 /tmp   | 低   | 增加 named volume 持久化，避免重啟後 trace/log 消失             |
| 無 resource limits                 | 低   | 正式環境補上 `deploy.resources.limits` 防止 OOM                 |

---

## 10. 快速啟動與驗證

### 啟動服務

```bash
# 方法一：自動注入 Slack Webhook 並啟動（推薦）
./start.sh

# 方法二：直接啟動（需確保 alertmanager.yml 已設定正確）
docker compose up -d
```

### 驗證各服務

```bash
# API 健康狀態
curl http://localhost:8000/health

# Prometheus metrics
curl http://localhost:8000/metrics | grep scheduler

# Grafana（瀏覽器開啟）
open http://localhost:3000  # 帳號：admin / 密碼：admin

# 查看 API 即時日誌
docker compose logs -f api

# 查看所有容器狀態
docker compose ps
```

### 常用除錯指令

```bash
# 確認 Prometheus 正確 scrape 到 API
curl http://localhost:9090/api/v1/targets

# 查看目前觸發中的告警
curl http://localhost:9090/api/v1/alerts

# 查看 AlertManager 收到的告警
curl http://localhost:9093/api/v1/alerts

# 重新讀取股票設定（修改 config.yml 後等 1 分鐘自動生效，也可重啟 api）
docker compose restart api
```

---

*最後更新：2026-07-01*
