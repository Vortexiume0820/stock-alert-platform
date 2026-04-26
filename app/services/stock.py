import twstock

class StockService:
    
    def get_price(self, stock_id: str, threshold_pct: float = 3.0) -> dict: 
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

    def get_multiple_prices(self, stock_ids: list) -> list:  
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