from apscheduler.schedulers.background import BackgroundScheduler
from app.services.stock import StockService
from app.services.notifier import send_slack_alert
from app.logger import setup_logger
import yaml
from pathlib import Path
import traceback

logger = setup_logger("scheduler")
CONFIG_PATH = Path(__file__).parent.parent / "config.yml"

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def check_stocks():
    logger.info("股價排程檢查開始", extra={"event": "scheduler_run"})
    config = load_config()
    service = StockService()

    for stock in config.get("stocks", []):
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

            if data["alert"]:
                send_slack_alert(
                    stock_id=stock["id"],
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