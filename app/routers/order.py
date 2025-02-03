import os
import json
import requests
from typing import List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert
import redis

from auth.database import get_async_session
from models.models import Order, User
from dto import dto as DTO

class OrderService:
    def __init__(self):
        # Конфигурация Telegram
        self.TELEGRAM_BOT_TOKEN = os.environ.get(
            'BOT_TOKEN', 
            '6937107637:AAFarU8swL-mp7oLC0sMz44A7-F3q0QuD4Y'
        )
        self.CLIENT_BOT_TOKEN = os.environ.get(
            'CLIENT_BOT_TOKEN', 
            '6937107637:AAFarU8swL-mp7oLC0sMz44A7-F3q0QuD4Y'
        )
        # Подключение к Redis
        self.redis_client = redis.Redis(
            host=os.environ.get('REDIS_HOST', '127.0.0.1'),
            port=int(os.environ.get('REDIS_PORT', 6379)),
            decode_responses=True
        )

    def _format_telegram_message(self, order_dto: DTO.Order) -> str:
        """
        Форматирование сообщения для Telegram с учетом вашего предыдущего формата
        """
        # Определение способа получения
        delivery_type = "ДОСТАВКА" if order_dto.isDelivery else "САМОВЫВОЗ"
        
        # Формирование списка заказанных блюд
        order_items_str = "".join([
            f"{item['count']}   x   {item['foodName']}    {item['price']} руб.\n" 
            for item in order_dto.items
        ])
        
        # Формирование полного текста сообщения
        full_message = (
            f"Новый заказ №{order_dto.number}\n\n"
            f"Оплата: {order_dto.payment}\n\n"
            f"Способ получения: {delivery_type}\n\n"
            f"📍Адрес: {order_dto.address}\n\n"
            f"Заказ:\n{order_items_str}"
            f"{order_dto.cutlery}  x  Приборов\n\n"
            f"Итого: {order_dto.total}"
        )
        
        return full_message

    def _send_telegram_message(self, chat_id: int, message: str, token: str):
        """
        Отправка сообщения в Telegram
        """
        try:
            requests.get(
                f"https://api.telegram.org/bot{token}/sendMessage",
                params={
                    "chat_id": chat_id, 
                    "text": message
                }
            )
        except Exception as e:
            print(f"Ошибка отправки в Telegram: {e}")

    async def get_all_orders(self, session: AsyncSession) -> List[Order]:
        """
        Получение всех заказов из базы данных
        """
        try:
            query = select(Order)
            result = await session.execute(query)
            return result.scalars().all()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail=str(e)
            )

    async def save_to_redis(self, data: DTO.Order, session: AsyncSession) -> Dict[str, Any]:
        """
        Сохранение данных в Redis
        """
        try:
            query = select(User.chatID).where(data.client == User.id)
            result = await session.execute(query)
            chat_id = result.mappings().all()
            print(chat_id)
            print(data)
            data.client = chat_id[0]["chatID"]
            order_id = self.redis_client.incr("order_id")
            redis_key = f"order:{order_id}"
            self.redis_client.set(redis_key, json.dumps(data.model_dump()))
            return {"status": "success", "order_id": order_id, "chat_id": chat_id}
        # return {"status": "success", "chat_id": chat_id}
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail=str(e)
            )
    
    async def create_order(
        self, 
        order_dto: DTO.Order,
        chatID: int,
        session: AsyncSession
    ):
        """
        Полный процесс создания заказа:
        1. Сохранение в базу данных
        2. Отправка в Telegram
        3. Сохранение в Redis
        """
        # try:
            # 1. Сохранение в базу данных
        query = insert(Order).values(order_dto.model_dump())
        result = await session.execute(query)
        await session.commit()

        # 2. Отправка в Telegram
        telegram_message = self._format_telegram_message(order_dto)
        
        # Получаем chat ID администраторов для рассылки
        admin_query = select(User.chatID).where(User.role == "admin")
        admin_result = await session.execute(admin_query)
        admin_chat_ids = os.getenv('ADMIN_CHAT_ID', '').split(' ')

        # for admin_chat_id in admin_chat_ids:
        #     self._send_telegram_message(admin_chat_id, telegram_message, self.TELEGRAM_BOT_TOKEN)
        
        text_for_send = (
            f"Спасибо за заказ!\n\n"
            f"Ваш заказ №{order_dto.number} принят и находится в обработке.\n"
            f"Он будет готов через 18 минут.\n\n"
            f"Оплата: {order_dto.payment}\n\n"
            f"❗️{'ДОСТАВКА' if order_dto.isDelivery else 'САМОВЫВОЗ'}❗️\n\n"
            f"📍 Адрес: {order_dto.address}\n\n"
            f"Состав заказа:\n" +
            "".join(
                [f"{item['count']} x {item['foodName']} - {item['price']} руб.\n" for item in order_dto.items]
            ) +
            f"\nПриборы: {order_dto.cutlery} шт.\n\n"
            f"Итого: {order_dto.total} руб.\n\n"
            f"💮🍜 "
        )

        self._send_telegram_message(chatID, text_for_send, self.CLIENT_BOT_TOKEN)
        # 3. Сохранение в Redis
        await self.save_to_redis(order_dto, session)

        return {"status": "success", "order_number": order_dto.number}

        # except Exception as e:
        #     await session.rollback()
        #     raise HTTPException(
        #         status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
        #         detail=str(e)
        #     )


    def redis_health_check(self) -> Dict[str, str]:
        """
        Проверка работоспособности Redis
        """
        try:
            self.redis_client.ping()
            return {"status": "ok", "message": "Redis is working"}
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
                detail=str(e)
            )
    async def send_message(self, message: str, client: int, session: AsyncSession):
        """
        Отправка сообщения в Telegram
        """
        try:
            self._send_telegram_message(client, message, self.CLIENT_BOT_TOKEN)
            return {"status": "success"}
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

class OrderWebsocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)
    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = OrderWebsocketManager()


# Создаем сервис
order_service = OrderService()

# Создаем роутер
orderRouter = APIRouter()

@orderRouter.post("/")
async def create_order(
    order: DTO.Order, 
    chatID: int,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Создание заказа с сохранением в БД, отправкой в Telegram и Redis
    """
    return await order_service.create_order(order, chatID, session)

@orderRouter.get("/")
async def get_orders(
    session: AsyncSession = Depends(get_async_session)
):
    """
    Получение всех заказов из базы данных
    """
    return await order_service.get_all_orders(session)

@orderRouter.post("/redis")
async def save_to_redis(data: DTO.Order, session: AsyncSession = Depends(get_async_session)):
    """
    Тестовое сохранение данных в Redis
    """
    return await order_service.save_to_redis(data, session)

@orderRouter.get("/redis/health")
async def redis_health():
    """
    Проверка работоспособности Redis
    """
    return order_service.redis_health_check()

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    async def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)
            print(connection)


manager = ConnectionManager()
@orderRouter.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.disconnect(websocket)
    # try:
    #     while True:
    #         global currentPayment
    #         currentPayment = {}
    #         data = await websocket.receive_text()
    #         print(data)
    #         await manager.broadcast(f'[{data},'.join(json.dumps(currentPayment)) + ']')
    #         print(currentPayment)
            
    # except WebSocketDisconnect:
    #     await manager.disconnect(websocket)


@orderRouter.post("/send-message")
async def send_message(message: str, client: int, session: AsyncSession = Depends(get_async_session)):
    print(type(client))
    return await order_service.send_message(message, client, session)