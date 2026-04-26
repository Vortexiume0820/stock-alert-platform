# 第三步：建立新的虛擬環境
python3 -m venv venv

# 第四步：啟動
source venv/bin/activate


# 程式碼有異動就需要重新 build，指令是：
docker compose up --build

# 舊的容器還殘留著，執行這個一次清掉：
docker compose down
這會停止並移除所有相關容器，然後再重新啟動：
docker compose up --build