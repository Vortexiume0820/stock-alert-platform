from fastapi import FastAPI
from app.routers import price, alert
from prometheus_fastapi_instrumentator import Instrumentator

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