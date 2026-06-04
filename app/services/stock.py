import twstock
import pybreaker
import logging
from opentelemetry import trace
from prometheus_client import Counter
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import requests.exceptions

logger = logging.getLogger(__name__)

# --- Circuit Breaker 設定 ---

cb_open_total = Counter(
    "circuit_breaker_open_total",
    "Circuit breaker 進入 OPEN 狀態次數"
)

class PrometheusListener(pybreaker.CircuitBreakerListener):
    def state_change(self, cb, old_state, new_state):
        if new_state.name == "open":
            cb_open_total.inc()

stock_breaker = pybreaker.CircuitBreaker(
    fail_max=5,
    reset_timeout=60,
    listeners=[PrometheusListener()]
)

# --- Retry 設定 ---
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
    ConnectionError,
    TimeoutError,
    )),
    # retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _fetch_from_twstock(stock_id: str):
    """只負責跟 twstock 溝通，網路錯誤會被 retry"""
    return twstock.Stock(stock_id)
    

class StockService:

    def get_price(self, stock_id: str, threshold_pct: float = 3.0) -> dict:
        tracer = trace.get_tracer("stock-service")
        with tracer.start_as_current_span("get_price") as span:
            span.set_attribute("stock.id", stock_id)
            span.set_attribute("stock.threshold_pct", threshold_pct)

            try:
                # CB 在外，retry 在內
                stock = stock_breaker.call(_fetch_from_twstock, stock_id)
            except pybreaker.CircuitBreakerError:
                span.set_status(trace.StatusCode.ERROR, "circuit breaker open")
                raise RuntimeError(f"股票服務暫時不可用，請稍後再試")

            if not stock.price or len(stock.price) < 2:
                span.set_status(trace.StatusCode.ERROR, "insufficient price data")
                raise ValueError(f"股票 {stock_id} 無法取得足夠價格資料")

            change_pct = round(
                (stock.price[-1] - stock.price[-2]) / stock.price[-2] * 100, 2
            )
            result = {
                "stock_id": stock_id,
                "price": stock.price[-1],
                "change": round(stock.price[-1] - stock.price[-2], 2),
                "change_pct": change_pct,
                "alert": abs(change_pct) >= threshold_pct
            }

            span.set_attribute("stock.price", result["price"])
            span.set_attribute("stock.change_pct", change_pct)
            span.set_attribute("stock.alert", result["alert"])

            return result

    def get_multiple_prices(self, stock_ids: list) -> list:
        tracer = trace.get_tracer("stock-service")
        with tracer.start_as_current_span("get_multiple_prices") as span:
            span.set_attribute("stock.ids", ",".join(stock_ids))
            results = []
            for stock_id in stock_ids:
                try:
                    results.append(self.get_price(stock_id))
                except Exception as e:
                    results.append({
                        "stock_id": stock_id,
                        "error": str(e)
                    })
            return results