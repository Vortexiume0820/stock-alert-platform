from fastapi import APIRouter
from pathlib import Path
import yaml
from app.services.stock import StockService

router = APIRouter()
service = StockService()

CONFIG_PATH = Path(__file__).parent.parent / "config.yml"

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

@router.get("/monitor")
def get_monitored_stocks():
    config = load_config()
    stocks = config.get("stocks", [])
    
    results = []
    for stock in stocks:
        data = service.get_price(
            stock_id=stock["id"],
            threshold_pct=stock["threshold_pct"]
        )
        data["name"] = stock["name"]   # 把中文名稱加進回傳
        results.append(data)
    
    return results