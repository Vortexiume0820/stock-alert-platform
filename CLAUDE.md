# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Stock Alert Platform** is a production-like stock price monitoring system that watches Taiwan stock prices (via twstock API) and sends Slack notifications when price changes exceed configured thresholds. It's a comprehensive DevOps/SRE learning project showcasing containerization, observability, and orchestration practices.

## Architecture

### System Flow
```
twstock API (free Taiwan stock data)
    ↓ (every 1 minute via APScheduler)
FastAPI service (port 8000)
    ├─ GET /price/{stock_id} - fetch single stock price
    ├─ GET /prices?ids=2330,2454 - fetch multiple stocks
    ├─ GET /monitor (requires API key) - check all configured stocks
    └─ GET /health - liveness probe
    ↓
Alert Logic (in scheduler)
    ├─ Circuit Breaker (pybreaker) - fails after 5 consecutive errors, resets after 60s
    ├─ Retry (tenacity) - exponential backoff with 3 max attempts for network errors
    └─ State tracking - prevents duplicate Slack alerts
    ↓
Slack Webhook
```

### Key Components

**Backend Service** (`app/`):
- `main.py` - FastAPI app entry point with lifespan management, Prometheus & OpenTelemetry auto-instrumentation
- `routers/price.py` - Stock price query endpoints with error handling & logging
- `routers/alert.py` - Protected endpoint to check all monitored stocks
- `services/stock.py` - StockService wrapper around twstock with circuit breaker & retry logic
- `services/scheduler.py` - APScheduler background job that runs every 1 minute, fetches prices, and sends Slack alerts
- `services/notifier.py` - Slack webhook sender
- `config.py` - Environment variable loading (SLACK_WEBHOOK_URL, API_KEY)
- `config.yml` - Stock symbols, names, and alert thresholds (e.g., 2330: 台積電, threshold: 3%)
- `logger.py` - JSON structured logging setup (via python-json-logger)
- `tracer.py` - OpenTelemetry setup exporting to Tempo via gRPC on port 4317
- `dependencies.py` - API key verification for protected endpoints

**Observability Stack** (`monitoring/`):
- `prometheus.yml` - Scrapes metrics from FastAPI (/metrics endpoint) every 15 seconds
- `alert_rules.yml` - 8 alert rules covering API downtime, high latency, error rates, scheduler staleness, fetch failures, SLOs, and circuit breaker opens
- `slo_rules.yml` - SLI/SLO recording rules (compute success rates, staleness, availability from raw metrics)
- `alertmanager.yml` - Routes CRITICAL/WARNING alerts to Slack channels with color coding; inhibits warnings when critical exists
- `promtail.yml` - Collects Docker container logs and ships to Loki
- `tempo.yml` - Receives distributed traces from FastAPI via OTLP gRPC
- `grafana/provisioning/` - Auto-provisions Prometheus data source and dashboards
- `grafana/dashboards/` - Dashboard JSON files for stock prices, API metrics, and SLOs

**Container Orchestration**:
- `docker-compose.yml` - Defines 8 services (api, prometheus, grafana, alertmanager, loki, promtail, tempo) with internal/external networks
- `Dockerfile` - Python 3.13-slim, installs deps, runs FastAPI via `fastapi run`
- `.env.example` - Template for SLACK_WEBHOOK_URL and API_KEY
- `start.sh` - Helper script to substitute env vars into alertmanager.yml template and start compose

## Common Tasks

### Local Development Setup
```bash
# Clone and navigate
git clone git@github.com:Vortexiume0820/stock-alert-platform.git
cd stock-alert-platform

# Create virtual environment (Python 3.11+)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and populate env template
cp .env.exmaple .env
# Edit .env with your Slack Webhook URL and API_KEY
```

### Running Services

**Local Docker Compose** (all-in-one observability stack):
```bash
# Ensure .env is configured
docker compose up -d

# Check service status
docker compose ps

# View logs (api service)
docker compose logs -f api

# Access services:
# API docs:    http://localhost:8000/docs
# Grafana:     http://localhost:3000 (admin/admin)
# Prometheus:  http://localhost:9090 (not exposed but available internally)
# AlertManager: not exposed (internal only)
```

**FastAPI in development** (without observability):
```bash
# From within activated venv
fastapi run app/main.py

# or with auto-reload
fastapi dev app/main.py
```

### Testing API Endpoints

```bash
# Health check (no auth needed)
curl http://localhost:8000/health

# Get single stock price
curl http://localhost:8000/price/2330

# Get multiple stocks
curl "http://localhost:8000/prices?ids=2330,2454"

# Check all monitored stocks (requires X-API-Key header)
curl -H "X-API-Key: your-api-key" http://localhost:8000/monitor
```

### Key Metrics & Observability

**Custom Metrics** exported to Prometheus:
- `circuit_breaker_open_total` - Count of Circuit Breaker state changes to OPEN
- `scheduler_runs_total` - Number of scheduler executions
- `scheduler_last_success_timestamp` - Unix timestamp of last successful scheduler run
- `stock_price_fetch_total` - Counter with labels [stock_id, status]
- `slack_alert_sent_total` - Counter of alerts sent per stock_id
- `http_request_duration_seconds` - Prometheus FastAPI instrumentator metric
- `http_requests_total` - Request count by status code (auto-instrumented)

**Tracing**: All spans exported to Tempo include stock_id, price, change_pct, alert status, errors.

**Alerts** (from alert_rules.yml):
- `APIDown` - API up metric is 0
- `HighAPILatency` - Average response time > 500ms
- `APIHighErrorRate` - 5xx errors > 1% of traffic
- `SchedulerStopped` - No scheduler runs in 5 minutes
- `StockDataStale` - Scheduler hasn't completed successfully in 90 seconds
- `StockFetchHighFailRate` - Success rate < 80% in 5 minutes
- `SLOAvailabilityBreach` - HTTP availability < 99.5% (manual queries only, not scheduler)
- `CircuitBreakerOpen` - Circuit breaker opened in last 5 minutes

## Code Patterns & Design

### Resilience Patterns
- **Circuit Breaker** (`pybreaker`): Stops calling twstock after 5 failures, automatically resets after 60 seconds. Prometheus listener tracks state transitions.
- **Retry with Exponential Backoff** (`tenacity`): Max 3 attempts with 1-10 second waits for connection errors.
- **Alert State Tracking** (`_alert_state` dict in scheduler): Prevents duplicate Slack messages on consecutive runs where price remains above threshold.

### Error Handling
- `RuntimeError` (CB open) → 503 Service Unavailable
- `ValueError` (insufficient data) → 400 Bad Request
- Unhandled exceptions → 500 (FastAPI default)
- All errors logged as JSON with event type, stock_id, and error message

### Configuration
- Stock symbols, names, thresholds live in `config.yml` (not hardcoded)
- Secrets (SLACK_WEBHOOK_URL, API_KEY) via environment variables
- AlertManager routing, channel names, and color formatting in `alertmanager.yml`

### Logging
- JSON structured logging everywhere (`app.logger.setup_logger()`)
- Extra fields: `event`, `stock_id`, `stock_name`, `price`, `change_pct`, `alert_triggered`
- Exported to Loki via Promtail

### Instrumentation
- OpenTelemetry auto-instrumentation via `FastAPIInstrumentor` and `HTTPXClientInstrumentor`
- Manual spans for business logic: `scheduler.check_stocks`, `stock.check`, `stock_service.get_price`
- Span attributes: stock.id, stock.price, stock.change_pct, stock.alert_triggered, errors

## Important Files

| File | Purpose |
|------|---------|
| `app/config.yml` | Stock monitoring config (modify to add/remove stocks) |
| `.env` | Runtime secrets (created from .env.exmaple, in .gitignore) |
| `docker-compose.yml` | Service definitions and networking |
| `requirements.txt` | Python dependencies (FastAPI, Prometheus, OpenTelemetry, twstock, etc.) |
| `monitoring/alert_rules.yml` | Alert definitions (modify thresholds here) |
| `monitoring/alertmanager.yml` | Alert routing and Slack integration |
| `Dockerfile` | Container image definition |

## Dependencies Highlight

- **fastapi** 0.136.1 - Web framework
- **uvicorn** 0.46.0 - ASGI server
- **twstock** 1.5.1 - Taiwan stock free API wrapper
- **pybreaker** 1.2 - Circuit breaker pattern
- **tenacity** 9.0.0 - Retry logic
- **apscheduler** 3.11.2 - Background job scheduler
- **prometheus-client** 0.25.0 - Prometheus metric client
- **prometheus-fastapi-instrumentator** 7.1.0 - Auto-instrument FastAPI
- **opentelemetry-sdk** 1.33.0, **opentelemetry-exporter-otlp-proto-grpc** - Distributed tracing
- **python-json-logger** 2.0.7 - JSON logging
- **pydantic** 2.13.3 - Data validation
- **pydantic-settings** 2.14.0 - Settings from env vars
- **requests** 2.33.1, **httpx** 0.28.1 - HTTP clients

## Git & CI/CD Notes

- Main branch is `main`
- No CI/CD pipelines currently configured (README mentions GitLab CI / GitHub Actions but not implemented in repo)
- Commits reference phases (Phase 1-5), with latest on scheduling, metrics, SLI/SLO, and Grafana dashboards

## Development Pitfalls

- **twstock API failures**: The free twstock API can be slow or temporarily unavailable; circuit breaker will kick in after 5 failures. Monitor the `CircuitBreakerOpen` alert.
- **Slack webhook authentication**: Must use a valid Slack app incoming webhook URL in `.env`; alertmanager.yml has a placeholder that should be templated from env vars (see `start.sh`).
- **Config reloading**: `config.yml` is read every scheduler run, so changes take effect within 1 minute without restart.
- **Alert deduplication**: AlertManager's `group_wait: 10s` means alerts are batched before sending; `repeat_interval: 1h` means resolved alerts are repeated hourly.
- **Tempo requires gRPC port 4317**: If traces aren't appearing, ensure Tempo is listening and the exporter endpoint is correct.

## AI 指導原則

### 解釋方式
- 遇到錯誤時，先說明「為什麼會發生」再給解法
- 每個指令都要附上說明，例如：
  `docker compose up -d`（-d 表示背景執行，不佔用終端機）
- 介紹新概念時請附上 SRE 實際應用場景
  例如：解釋 Prometheus 時說明它在 on-call 流程中扮演什麼角色

### 學習引導
- 不要直接給完整設定檔，先說明每個欄位的用途再讓我自己填
- 若我的做法有更好的 SRE 實踐方式，請主動提出並說明原因
- 適時提醒 SRE 核心概念，例如 SLO/SLI/Error Budget 與當前操作的關聯

### 除錯習慣養成
- 引導我先看 log 再問問題，例如提示我執行：
  `docker compose logs grafana` 或 `kubectl logs -n monitoring`
- 教我用系統化方式縮小問題範圍，而不是直接給答案
- 遇到設定錯誤時，說明這個錯誤在正式環境會造成什麼影響

### 安全與最佳實踐
- 若我的做法有安全疑慮請立即提醒（例如帳密寫死在設定檔）
- 提醒我什麼東西不該 commit 進 git（secrets、token 等）
- 適時建議 production-ready 的做法，即使現在只是學習環境

### 行動前查明原則（重要）
- **提供任何 Prometheus query 前，必須先讀取 `monitoring/slo_rules.yml` 與 `monitoring/alert_rules.yml`**，確認是否已有對應的 recording rule 或告警閾值，優先使用現有定義而非重新撰寫原始 PromQL
- 若有 recording rule 可用，說明：「這個指標已在 slo_rules.yml 定義為 recording rule，直接使用 `rule_name` 比原始 query 更正確，原因是...」
- **每一個建議動作執行前，先向使用者說明**：要查什麼、為什麼查、查完後會怎麼做，不要直接給結論而跳過查明過程
- 若給的方案存在「更好的做法」，必須主動揭露，不能等使用者自己發現
- 使用者是 SRE/DevOps 初學者，不會主動懷疑建議是否為最佳解，Claude 有責任在第一次就給出正確方向

## SLO Dashboard 設定參考

### Recording Rules（定義於 monitoring/slo_rules.yml）
使用 dashboard 前必須先讀取此檔，確認實際 rule 名稱，以下為預期存在的指標：
- `sli:scheduler_staleness:seconds` — 距上次排程成功秒數（原始：`time() - scheduler_last_success_timestamp`）

### Threshold 設計原則（對齊 alert_rules.yml）
| Panel | 黃色 | 紅色 | 依據 |
|---|---|---|---|
| Scheduler 新鮮度 | 90s | 180s | StockDataStale 告警 90s，紅色保留緩衝 |
| 成功率 SLI | 0.99 | 0.995 | SLO 目標 99.5% |
| P95 延遲 | 0.3s | 0.5s | HighAPILatency 告警 500ms |
| Error Budget | 0.25 | 0.1 | 低於 25% 警示，低於 10% 緊急 |

### SLO 目標
- 股價查詢成功率：**99.5%**（`SLOAvailabilityBreach` 告警閾值）
- Scheduler 新鮮度：**90 秒內**必須完成一次（`StockDataStale` 告警閾值）