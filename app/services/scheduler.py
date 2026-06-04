from apscheduler.schedulers.background import BackgroundScheduler
from app.services.stock import StockService
from app.services.notifier import send_slack_alert
from app.logger import setup_logger
from opentelemetry import trace
import yaml
from pathlib import Path
import traceback
from prometheus_client import Counter, Gauge


logger = setup_logger("scheduler")
CONFIG_PATH = Path(__file__).parent.parent / "config.yml"

scheduler_runs_total = Counter('scheduler_runs_total', 'Scheduler execution count')

# 業務層 metrics
stock_price_fetch_total = Counter(
    'stock_price_fetch_total',
    '股價查詢次數',
    ['stock_id', 'status']  # status: success | failed
)
scheduler_last_success_timestamp = Gauge(
    'scheduler_last_success_timestamp',
    '上次排程成功完成的 Unix timestamp'
)
slack_alert_sent_total = Counter(
    'slack_alert_sent_total',
    'Slack 告警送出次數',
    ['stock_id']
)

_alert_state: dict[str, bool] = {}


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def check_stocks():
    tracer = trace.get_tracer("scheduler")  # setup_tracer() 之後才取，確保拿到正確 provider
    scheduler_runs_total.inc()
    logger.info("股價排程檢查開始", extra={"event": "scheduler_run"})
    config = load_config()
    service = StockService()
        
    with tracer.start_as_current_span("scheduler.check_stocks") as root_span:
        stocks = config.get("stocks", [])
        root_span.set_attribute("scheduler.stock_count", len(stocks))

        fetch_failed = False
        for stock in stocks:
            stock_id = stock["id"]

            with tracer.start_as_current_span("stock.check") as span:
                span.set_attribute("stock.id", stock_id)
                span.set_attribute("stock.name", stock["name"])
                span.set_attribute("stock.threshold_pct", stock["threshold_pct"])

                try:
                    data = service.get_price(
                        stock_id=stock_id,
                        threshold_pct=stock["threshold_pct"]
                    )
                    stock_price_fetch_total.labels(stock_id=stock_id, status="success").inc()
                    span.set_attribute("stock.price", data["price"])
                    span.set_attribute("stock.change_pct", data["change_pct"])
                    span.set_attribute("stock.alert_triggered", data["alert"])

                    logger.info(
                        "股價查詢成功",
                        extra={
                            "event": "price_checked",
                            "stock_id": stock_id,
                            "stock_name": stock["name"],
                            "price": data["price"],
                            "change_pct": data["change_pct"],
                            "alert_triggered": data["alert"]
                        }
                    )

                    prev_alerted = _alert_state.get(stock_id, False)
                    curr_alerted = data["alert"]

                    if curr_alerted and not prev_alerted:
                        send_slack_alert(
                            stock_id=stock_id,
                            name=stock["name"],
                            price=data["price"],
                            change_pct=data["change_pct"]
                        )
                        slack_alert_sent_total.labels(stock_id=stock_id).inc()
                        span.set_attribute("stock.slack_sent", True)
                        logger.warning(
                            "告警已發送",
                            extra={
                                "event": "alert_sent",
                                "stock_id": stock_id,
                                "stock_name": stock["name"],
                                "price": data["price"],
                                "change_pct": data["change_pct"]
                            }
                        )
                    _alert_state[stock_id] = curr_alerted

                except Exception as e:
                    stock_price_fetch_total.labels(stock_id=stock_id, status="failed").inc()
                    fetch_failed = True
                    span.set_status(trace.StatusCode.ERROR, str(e))
                    span.set_attribute("stock.error", str(e))
                    logger.error(
                        "股價查詢失敗",
                        extra={
                            "event": "price_check_error",
                            "stock_id": stock_id,
                            "stock_name": stock.get("name", "unknown"),
                            "error": str(e),
                            "traceback": traceback.format_exc()
                        }
                    )

        if not fetch_failed:
            scheduler_last_success_timestamp.set_to_current_time()


def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_stocks, "interval", minutes=1)
    scheduler.start()
    logger.info("排程啟動", extra={"event": "scheduler_started", "interval_minutes": 1})
    return scheduler