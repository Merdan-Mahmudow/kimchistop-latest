import logging
from fastapi import APIRouter, HTTPException
from services.redis_service import RedisService
from dto.dto import CartRedis

redis = RedisService()
cart_router = APIRouter()

logger = logging.getLogger(__name__)

@cart_router.post("/add", summary="Добавление товаров в корзину")
async def add_item_to_cart(cart: CartRedis):
    try:
        await redis.add_to_cart(cart)
        return  {"status": "success"}
    except Exception as e:
        logger.error(f"Ошибка обработки данных: {e}")
        raise HTTPException(status_code=500, detail={"error": f"{e}"})
    
@cart_router.get("/{user_id}", summary="Получение корзины из Redis")
async def get_cart(user_id: int):
    try:
        items = await redis.get_cart(user_id)
        return items
    except Exception as e:
        logger.error(f"Ошибка обработки данных: {e}")
        raise HTTPException(status_code=500, detail={"error": f"{e}"})
    
@cart_router.patch("/update", summary="Обновление товара в корзине")
async def update_item_from_cart(cart: CartRedis):
    try:
        items = await redis.update_from_cart(cart)
        return items
    except Exception as e:
        logger.error(f"Ошибка обработки данных: {e}")
        raise HTTPException(status_code=500, detail={"error": f"{e}"})
    
@cart_router.delete("/delete", summary="Удаление товара из корзины")
async def update_item_from_cart(cart: CartRedis):
    try:
        items = await redis.delete_from_cart(cart)
        return items
    except Exception as e:
        logger.error(f"Ошибка обработки данных: {e}")
        raise HTTPException(status_code=500, detail={"error": f"{e}"})