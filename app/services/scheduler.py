from apscheduler.schedulers.background import BackgroundScheduler
from app.services.stock import StockService
from app.services.notifier import send_slack_alert
from app.logger import setup_logger
import yaml
from pathlib import Path
import traceback
from prometheus_client import Counter


logger = setup_logger("scheduler")
CONFIG_PATH = Path(__file__).parent.parent / "config.yml"
scheduler_runs_total = Counter('scheduler_runs_total', 'Scheduler execution count')  # ← 新增

_alert_state: dict[str, bool] = {}


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def check_stocks():
    scheduler_runs_total.inc()
    logger.info("股價排程檢查開始", extra={"event": "scheduler_run"})
    config = load_config()
    service = StockService()

    for stock in config.get("stocks", []):
        stock_id = stock["id"]
        try:
            data = service.get_price(
                stock_id=stock["id"],
                threshold_pct=stock["threshold_pct"]
            )
            logger.info(
                "股價查詢成功",
                extra={
                    "event": "price_checked",
                    "stock_id": stock["id"],
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
                logger.warning(
                    "告警已發送",
                    extra={
                        "event": "alert_sent",
                        "stock_id": stock["id"],
                        "stock_name": stock["name"],
                        "price": data["price"],
                        "change_pct": data["change_pct"]
                    }
                )
            _alert_state[stock_id] = curr_alerted
        except Exception as e:
            logger.error(
                "股價查詢失敗",
                extra={
                    "event": "price_check_error",
                    "stock_id": stock["id"],
                    "stock_name": stock.get("name", "unknown"),
                    "error": str(e),
                    "traceback": traceback.format_exc()
                }
            )

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_stocks, "interval", minutes=1)
    scheduler.start()
    logger.info("排程啟動", extra={"event": "scheduler_started", "interval_minutes": 1})
    return scheduler