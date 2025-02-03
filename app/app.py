import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.routers import *
from scalar_fastapi import get_scalar_api_reference
from fastapi.staticfiles import StaticFiles
from services.redis_service import RedisService
from services.sbis import SBISService, SBISBusinessLogic
from config import APP_CLIENT_ID, APP_SECRET, APP_SECRET_KEY
from dto.dto import AuthorizationData
import asyncio

app = FastAPI(tags=["Freestyle BOT"])

# Обработчик для статических файлов
app.mount("/images", StaticFiles(directory="static"), name="images")

origins = [
    "http://localhost:3000",
    "https://skyrodev.ru",
    "http://0.0.0.0:8000",
    "https://backend.skyrodev.ru",
    "http://127.0.0.1:3000",
    "https://kimchistop.ru",
    "https://api.kimchistop.ru"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "DELETE", "PATCH", "PUT"],
    allow_headers=["Content-Type", "Set-Cookie", "Access-Control-Allow-Headers", "Access-Control-Allow-Origin",
                   "Authorization"],
)

app.include_router(router)

@app.get("/scalar")
async def scalar():
    return get_scalar_api_reference(
        title="Scalar API",
        openapi_url=app.openapi_url
    )

UPLOAD_DIR = os.path.abspath("uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)   
app.mount("/static", StaticFiles(directory=UPLOAD_DIR), name="static")

# Initialize services and logic
redis_service = RedisService()
sbis_service = SBISService()
auth_data = AuthorizationData(
    app_client_id=APP_CLIENT_ID,
    app_secret=APP_SECRET,
    secret_key=APP_SECRET_KEY
)
sbis_logic = SBISBusinessLogic(sbis_service, redis_service)

@app.on_event("startup")
async def startup_event():
    await sbis_service.__aenter__()
    asyncio.create_task(update_products_periodic())

@app.on_event("shutdown")
async def shutdown_event():
    await sbis_service.close()

async def update_products_periodic():
    while True:
        try:
            await sbis_logic.update_products_cache(auth_data)
        except Exception as e:
            print(f"Error updating products: {e}")
        await asyncio.sleep(30)
