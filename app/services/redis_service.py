import json
from typing import Dict, List, Optional
import redis
import logging
from dto.dto import CartRedis
from config import REDIS_HOST, REDIS_PORT
logger = logging.getLogger(__name__)

class RedisService:
    def __init__(self, redis_url: str = f"redis://{REDIS_HOST}:{REDIS_PORT}"):
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

    async def add_to_cart(self, items: CartRedis):
        try:
            cart_key = f"cart:{items.user_id}"
            cart = json.loads(self.redis.get(cart_key) or '{"items": []}')
            for item in cart ["items"]:
                if item["product_id"] == items.product_id:
                    item["quantity"] += items.quantity
                    break
            else:
                cart["items"].append({"product_id": items.product_id, "quantity": items.quantity})

            self.redis.set(cart_key, json.dumps(cart))
            return cart
        except Exception as e:
            logger.error(f"Error adding to cart: {e}")

    async def get_cart(self, user_id: int):
        try:
            cart = self.redis.get(f"cart:{user_id}")
            return json.loads(cart) if cart else {"items": []}
        except Exception as e:
            logger.error(f"Ошибка обработки данных: {e}")
            return {"items": []}
    
    async def update_from_cart(self, items: CartRedis):
        try:
            cart_key = f"cart:{items.user_id}"
            cart = json.loads(self.redis.get(cart_key) or '{"items": []}')
            
            for item in cart["items"]:
                if item["product_id"] == items.product_id:
                    if items.quantity > 0:
                        item["quantity"] = items.quantity
                    else:
                        cart["items"].remove(item)
                    break

            self.redis.set(cart_key, json.dumps(cart))
            return cart
        except Exception as e:
            logger.error(f"Ошибка обработки данных: {e}")
            return {"items": []}
    
    async def delete_from_cart(self, product_id: int, user_id: str):
        try:
            cart_key = f"cart:{user_id}"
            cart = json.loads(self.redis.get(cart_key) or '{"items": []}')
            cart["items"] = [item for item in cart["items"] if item["product_id"] != product_id]
            self.redis.set(cart_key, json.dumps(cart))
            return cart
        except Exception as e:
            logger.error(f"Ошибка обработки данных: {e}")
            return {"items": []}