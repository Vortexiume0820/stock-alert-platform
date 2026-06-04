from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
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
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Stock Alert API",
        version="1.0.0",
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key"
        }
    }
    openapi_schema["security"] = [{"ApiKeyAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
# 初始化 Tracer
setup_tracer()

# 自動埋點
FastAPIInstrumentor().instrument_app(app,  
                                     excluded_urls="health,metrics,monitor,docs,openapi.json,redoc")
HTTPXClientInstrumentor().instrument()

Instrumentator(
    excluded_handlers=["/health", "/metrics", "/docs", "/openapi.json", "/redoc", "/monitor"]
).instrument(app).expose(app)

app.include_router(price.router)
app.include_router(alert.router)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/monitor")
def get_monitored_stocks():
    return {"status": "ok"}