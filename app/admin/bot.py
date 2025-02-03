import asyncio
import os
import json
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from dotenv import load_dotenv
from redis import Redis
import requests
from dto import dto as DTO
from routers.order import send_message

load_dotenv()

# Получение токена из .env
API_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_IDS = os.getenv("ADMIN_CHAT_ID", "").split()  # Администраторские чаты
REDIS_HOST = os.getenv("REDIS_HOST", "0.0.0.0")

# Проверка токена
if not API_TOKEN:
    raise ValueError("Токен бота не задан. Убедитесь, что BOT_TOKEN указан в файле .env")

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Настройка Redis
redis_client = Redis(host=REDIS_HOST, port=6379, decode_responses=True)

# Переменная для отслеживания последнего обработанного заказа
last_processed_order_id = 0


# Форматирование заказа
def format_order(order):
    order_number = order.get("number", "Неизвестно")
    payment = order.get("payment", "None")
    address = order.get("address", "Не указан")
    is_delivery = order.get("isDelivery", False)
    cutlery_count = order.get("cutlery", 0)
    total = order.get("total", 0)
    items = order.get("items", [])

    order_lines = []
    for item in items:
        food_name = item.get("foodName", "Неизвестно")
        count = item.get("count", 0)
        price = item.get("price", 0)
        order_lines.append(f"{count} x {food_name} {price * count} руб.")

    result = f"""
НОВЫЙ ЗАКАЗ №{order_number} 

Оплата: {payment}

{'❗️ДОСТАВКА❗️' if is_delivery else '❗️ЗАБРАТЬ САМОСТОЯТЕЛЬНО❗️'}

📍Адрес: {address}

Заказ:
{chr(10).join(order_lines)}

{cutlery_count} x Приборов

Итого: {total} руб.
"""
    return result.strip()


# Класс для работы с заказами
class Order:
    def __init__(self):
        self.CLIENT_BOT_TOKEN = os.environ.get("CLIENT_BOT_TOKEN")
        if not self.CLIENT_BOT_TOKEN:
            raise ValueError("CLIENT_BOT_TOKEN не задан в файле .env")

    def _format_telegram_message(self, order_dto: DTO.Order) -> str:
        return f"Ваш заказ №{order_dto.number}, начали готовить!"

    def _send_telegram_message(self, chat_id: int, message: str):
        try:
            response = requests.get(
                f"https://api.telegram.org/bot{self.CLIENT_BOT_TOKEN}/sendMessage",
                params={"chat_id": chat_id, "text": message}
            )
            if response.status_code != 200:
                print(f"Ошибка отправки в Telegram: {response.text}")
        except Exception as e:
            print(f"Ошибка отправки в Telegram: {e}")


order_handler = Order()


# Генерация клавиатуры
def get_order_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Принять", callback_data="accept"),
            InlineKeyboardButton(text="Отклонить", callback_data="decline")
        ]
    ])
    return kb


# Обработчик callback-событий
@dp.callback_query()
async def handle_callback(callback: CallbackQuery):
    # Получение данных из callback_data
    if callback.data == "accept":
        # Отправка сообщения 
        msg = "Ваш заказ принят! Мы начали его готовить!"
        req = requests.get(
                f"https://api.telegram.org/bot{order_handler.CLIENT_BOT_TOKEN}/sendMessage",
                params={
                    "chat_id": orderr["client"], 
                    "text": msg
                }
            )
        print(orderr["client"])
        
        # Сообщение сотруднику
        await callback.message.answer("Вы приняли заказ! Клиенту отправлено уведомление.")
    
    elif callback.data == "decline":
        # Запрос причины отказа
        await callback.message.answer(
            "Пожалуйста, укажите причину отклонения заказа, отправив её следующим сообщением.",
        )
        
        # Ожидание причины от администратора
        @dp.message()
        async def handle_decline_reason(message: types.Message):
            reason = message.text
            client_chat_id = orderr["client"]
            client_message = (
                f"Ваш заказ был отклонен. Мы извиняемся за неудобства.\n"
                f"Причина: {reason}"
            )
            order_handler._send_telegram_message(client_chat_id, client_message)
            
            # Сообщение сотруднику
            await message.answer("Клиенту отправлено уведомление об отказе.")
    
    # Закрытие callback-запроса
    await callback.answer()


# Функция проверки новых заказов
async def check_for_new_orders():
    global last_processed_order_id
    while True:
        try:
            last_order_id = redis_client.get("order_id")
            if last_order_id and int(last_order_id) > last_processed_order_id:
                last_processed_order_id = int(last_order_id)
                last_order_data = redis_client.get(f"order:{last_order_id}")
                if last_order_data:
                    global orderr
                    orderr = json.loads(last_order_data)
                    formatted_order = format_order(orderr)

                    # Отправляем уведомления администраторам
                    for chat_id in ADMIN_CHAT_IDS:
                        try:
                            await bot.send_message(chat_id, formatted_order, reply_markup=get_order_keyboard())
                        except Exception as e:
                            print(f"Ошибка отправки сообщения в чат {chat_id}: {e}")

        except Exception as e:
            print(f"Ошибка при проверке заказов: {e}")

        await asyncio.sleep(0.1)


# Команда /start
@dp.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer(f"Бот запущен и проверяет новые заказы каждую секунду. Ваш ID: {message.chat.id}")
