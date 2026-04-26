from fastapi import APIRouter
from app.services.stock import StockService

router = APIRouter()
service = StockService()

@router.get("/price/{stock_id}")
def get_price(stock_id: str):
    return service.get_price(stock_id)

@router.get("/prices")
def get_multiple_prices(ids: str):
    stock_ids = [s.strip() for s in ids.split(",")]
    return service.get_multiple_prices(stock_ids)