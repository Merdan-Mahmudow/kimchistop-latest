from http.client import HTTPException
import json
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates
from routers.category import categoryRouter
from routers.food import foodRouter
from routers.user import userRouter
from routers.order import orderRouter
from routers.payment import payment_router
from routers.promocode import promoRouter
from routers.sbis import sbisRouter
from routers.cart import cart_router

import uuid

# Configuration.account_id = "393161"
# Configuration.secret_key = "test_zaHD1EDc8Mi2f_LK0evUH5neTKsKdhGs3CyacbObQ54"
templates = Jinja2Templates(directory="/app/app/templates")

router = APIRouter()


@router.get('/')
async def main_app(request: Request):
    try:
        return templates.TemplateResponse("index.html", {"request": request})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get('/manager')
async def manager(request: Request):
    return templates.TemplateResponse("manager.html", {"request": request})

router.include_router(userRouter, prefix="/user", tags=["Пользователи"])
router.include_router(foodRouter, prefix="/food", tags=["Еда"])
router.include_router(categoryRouter, prefix='/category', tags=["Категории"])
router.include_router(orderRouter, prefix='/order', tags=["Заказы"])
router.include_router(payment_router, prefix='/payments', tags=["Оплата"])
router.include_router(promoRouter, prefix='/promocode', tags=["Промокоды"])
router.include_router(sbisRouter, prefix='/sbis', tags=["SBIS"])
router.include_router(cart_router, prefix="/cart", tags=["Корзина"])