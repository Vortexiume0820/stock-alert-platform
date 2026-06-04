from fastapi import APIRouter, HTTPException
from app.services.stock import StockService
from app.logger import setup_logger

router = APIRouter()
service = StockService()
logger = setup_logger("price")

@router.get("/price/{stock_id}")
def get_price(stock_id: str):
    try:
        result = service.get_price(stock_id)
        logger.info(
            "單支股票查詢",
            extra={
                "event": "price_queried",
                "stock_id": stock_id,
                "price": result.get("price")
            }
        )
        return result
    except RuntimeError as e:
        # CB open — twstock 暫時不可用
        logger.error(
            "單支股票查詢失敗",
            extra={"event": "circuit_breaker_open", "stock_id": stock_id, "error": str(e)}
        )
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        # 股票資料不足 — 使用者的問題
        logger.error(
            "單支股票查詢失敗",
            extra={"event": "price_query_error", "stock_id": stock_id, "error": str(e)}
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # 未預期錯誤 — 讓 FastAPI 處理成 500
        logger.error(
            "單支股票查詢失敗",
            extra={"event": "price_query_error", "stock_id": stock_id, "error": str(e)}
        )
        raise

@router.get("/prices")
def get_multiple_prices(ids: str):
    # 這裡完全不用動
    stock_ids = [s.strip() for s in ids.split(",")]
    try:
        result = service.get_multiple_prices(stock_ids)
        logger.info(
            "多支股票查詢",
            extra={
                "event": "prices_queried",
                "stock_ids": stock_ids,
                "count": len(stock_ids)
            }
        )
        return result
    except Exception as e:
        logger.error(
            "多支股票查詢失敗",
            extra={"event": "prices_query_error", "stock_ids": stock_ids, "error": str(e)}
        )
        raise