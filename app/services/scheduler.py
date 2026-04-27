from apscheduler.schedulers.background import BackgroundScheduler
from app.services.stock import StockService
from app.services.notifier import send_slack_alert
import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config.yml"

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def check_stocks():
    print("執行股價檢查...")
    config = load_config()
    service = StockService()
    
    for stock in config.get("stocks", []):
        try:
            data = service.get_price(
                stock_id=stock["id"],
                threshold_pct=stock["threshold_pct"]
            )
            print(f"{stock['name']}（{stock['id']}）：{data['price']} 變動 {data['change_pct']}%")
            
            if data["alert"]:
                send_slack_alert(
                    stock_id=stock["id"],
                    name=stock["name"],
                    price=data["price"],
                    change_pct=data["change_pct"]
                )
        except Exception as e:
            print(f"檢查 {stock['id']} 時發生錯誤：{e}")

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_stocks, "interval", minutes=1)
    scheduler.start()
    print("排程啟動：每分鐘自動檢查股價")
    return scheduler