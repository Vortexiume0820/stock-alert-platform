import httpx
import os

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

def send_slack_alert(stock_id: str, name: str, price: float, change_pct: float):
    if not SLACK_WEBHOOK_URL:
        print("警告：SLACK_WEBHOOK_URL 未設定")
        return
    
    message = {
        "text": f"📈 *股價警示*\n股票：{name}（{stock_id}）\n現價：{price}\n變動：{change_pct}%"
    }
    
    with httpx.Client() as client:
        response = client.post(SLACK_WEBHOOK_URL, json=message)
        if response.status_code == 200:
            print(f"Slack 通知發送成功：{stock_id}")
        else:
            print(f"Slack 通知發送失敗：{response.status_code}")