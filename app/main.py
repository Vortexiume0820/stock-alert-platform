from fastapi import FastAPI
from app.routers import price, alert
from prometheus_fastapi_instrumentator import Instrumentator
from app.services.scheduler import start_scheduler
from app.logger import setup_logger
from app.tracer import setup_tracer
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

from contextlib import asynccontextmanager

logger = setup_logger("main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("服務啟動", extra={"event": "app_startup"})
    scheduler = start_scheduler()
    yield
    scheduler.shutdown()
    logger.info("服務關閉", extra={"event": "app_shutdown"})

# lifespan 傳入 FastAPI — 這是之前漏掉的
app = FastAPI(lifespan=lifespan)
# 初始化 Tracer
setup_tracer()

# 自動埋點
FastAPIInstrumentor().instrument_app(app)
HTTPXClientInstrumentor().instrument()

Instrumentator().instrument(app).expose(app)

app.include_router(price.router)
app.include_router(alert.router)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/monitor")
def get_monitored_stocks():
    return {"status": "ok"}