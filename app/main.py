from fastapi import FastAPI
from app.routers import price, alert
from prometheus_fastapi_instrumentator import Instrumentator
from app.services.scheduler import start_scheduler
from contextlib import asynccontextmanager

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