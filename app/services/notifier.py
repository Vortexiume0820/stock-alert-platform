import httpx
import os
from app.config import settings

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

def send_slack_alert(stock_id: str, name: str, price: float, change_pct: float):
    url = settings.SLACK_WEBHOOK_URL
    
    message = {
        "text": f"📈 *股價警示*\n股票：{name}（{stock_id}）\n現價：{price}\n變動：{change_pct}%"
    }
    
    with httpx.Client() as client:
        response = client.post(SLACK_WEBHOOK_URL, json=message)
        if response.status_code == 200:
            print(f"Slack 通知發送成功：{stock_id}")
        else:
            print(f"Slack 通知發送失敗：{response.status_code}")