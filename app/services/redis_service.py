import json
from typing import Dict, List, Optional
import redis
import logging

logger = logging.getLogger(__name__)

class RedisService:
    def __init__(self, redis_url: str = "redis://localhost:6380"):
        self.redis = redis.from_url(redis_url, decode_responses=True)

    async def set_products(self, products: List[Dict]) -> None:
        try:
            self.redis.delete("sbis_products")
            for product in products:
                self.redis.hset("sbis_products", product["id"], json.dumps(product))
        except Exception as e:
            logger.error(f"Error storing products in Redis: {e}")

    async def get_products(self) -> List[Dict]:
        try:
            products = self.redis.hgetall("sbis_products")
            return [json.loads(p) for p in products.values()]
        except Exception as e:
            logger.error(f"Error getting products from Redis: {e}")
            return []

    async def get_product(self, product_id: int) -> Optional[Dict]:
        try:
            product = self.redis.hget("sbis_products", str(product_id))
            return json.loads(product) if product else None
        except Exception as e:
            logger.error(f"Error getting product from Redis: {e}")
            return None
