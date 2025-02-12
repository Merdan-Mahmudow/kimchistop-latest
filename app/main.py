import uvicorn
import asyncio
from services.redis_service import RedisService
from services.sbis import SBISService, SBISBusinessLogic
from config import APP_CLIENT_ID, APP_SECRET, APP_SECRET_KEY
from dto.dto import AuthorizationData

from admin.bot import check_for_new_orders as check_redis_for_new_data
from admin.bot import dp
from admin.bot import bot

# Create services at module level
redis_service = RedisService()
sbis_service = None
sbis_logic = None

auth_data = AuthorizationData(
    app_client_id=APP_CLIENT_ID,
    app_secret=APP_SECRET,
    secret_key=APP_SECRET_KEY
)

async def startup_event():
    global sbis_service, sbis_logic
    sbis_service = SBISService()
    await sbis_service.__aenter__()
    sbis_logic = SBISBusinessLogic(sbis_service, redis_service)
    asyncio.create_task(update_products_periodic())

async def shutdown_event():
    if sbis_service:
        await sbis_service.close()

async def bott():
    print("Bot started")
    await dp.start_polling(bot)
    
async def fastapi():
    config = uvicorn.Config("app.app:app", host="0.0.0.0", port=8000, log_level="info", reload=True, ws="websockets")
    server = uvicorn.Server(config)
    await server.serve()
    print("FastAPI started")

async def redis():
    await check_redis_for_new_data()
    print("Redis started")

async def update_products_periodic():
    while True:
        try:
            if sbis_logic:
                await sbis_logic.update_products_cache(auth_data)
        except Exception as e:
            print(f"Error updating products: {e}")
        await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(startup_event())
    uvicorn.run("app:app", host="0.0.0.0", port=8000, log_level="info")