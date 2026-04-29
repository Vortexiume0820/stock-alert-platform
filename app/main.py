from fastapi import FastAPI
from app.routers import price, alert
from prometheus_fastapi_instrumentator import Instrumentator
from app.services.scheduler import start_scheduler
from contextlib import asynccontextmanager
import logging

logger = logging.getLogger("stock_alert")

@app.get("/stock/{symbol}")
async def get_stock(symbol: str):
    logger.info(f"Fetching stock: {symbol}")
    ...
    logger.info(f"Stock fetched: {symbol} price={price}")
    
@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = start_scheduler()
    yield
    scheduler.shutdown()

app = FastAPI()

Instrumentator().instrument(app).expose(app)

app.include_router(price.router)
app.include_router(alert.router)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/monitor")
def get_monitored_stocks():
        return{"status": "ok"}