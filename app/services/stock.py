import twstock
from opentelemetry import trace

tracer = trace.get_tracer("stock-service")

class StockService:
    
    def get_price(self, stock_id: str, threshold_pct: float = 3.0) -> dict: 
        with tracer.start_as_current_span("get_price") as span:
            span.set_attribute("stock.id", stock_id)
            span.set_attribute("stock.threshold_pct", threshold_pct)


        stock = twstock.Stock(stock_id)
        change_pct = round(
        (stock.price[-1] - stock.price[-2]) / stock.price[-2] * 100, 2
    )
        return {
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