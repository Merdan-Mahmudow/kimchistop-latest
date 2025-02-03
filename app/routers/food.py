from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from config import APP_CLIENT_ID, APP_SECRET, APP_SECRET_KEY
from services.sbis import SBISService
from services.sbis import AuthorizationData
from auth.database import get_async_session
from dto import dto as DTO
from models.models import Food

class FoodService:
    async def add_food(self, food_dto: DTO.Food, session: AsyncSession):
        """
        Добавление нового блюда в базу данных
        """
        try:
            query = insert(Food).values(**food_dto.model_dump())
            await session.execute(query)
            await session.commit()
            return {"message": "Food added successfully"}
        except Exception as e:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to add food: {str(e)}")
        
    async def get_foods(self, request: DTO.FoodsRequest, token: DTO.TokenValidation) -> List[dict]:
        """
        Получение списка блюд из API СБИСа
        """
        try:
            foods = await SBISService.get_foods(request, token)
            if not foods.get('nomenclatures'):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No foods found")
            
            # Добавляем базовый URL к каждому изображению и фильтруем товары
            base_url = "https://api.sbis.ru/retail"
            filtered_foods = []
            
            for food in foods['nomenclatures']:
                # Проверяем, не является ли hierarchicalParent равным 2382
                if food.get('hierarchicalParent') == 2382:
                    continue  # Пропускаем этот товар
                
                if 'images' in food and food['images'] is not None:
                    # Фильтруем изображения, оставляя только те, которые не равны null
                    valid_images = [base_url + image for image in food['images'] if image is not None]
                    if valid_images:  # Проверяем, есть ли хотя бы одно валидное изображение
                        food['image'] = valid_images[0]  # Используем только первое валидное изображение
                        filtered_foods.append(food)  # Добавляем в отфильтрованный список
            
            if not filtered_foods:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No valid foods found")
            
            return filtered_foods
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch foods: {str(e)}")
        
    async def get_foods_categories(self, request: DTO.FoodsRequest, token: DTO.TokenValidation) -> List[dict]:
        """
        Получение списка категорий из API СБИСа с cost = null
        """
        try:
            foods = await SBISService.get_foods(request, token)
            if not foods.get('nomenclatures'):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No foods found")
            
            # Фильтруем товары с cost = null и формируем список категорий
            filtered_categories = [
                {
                    "name": food.get("name"),
                    "hierarchicalId": food.get("hierarchicalId"),
                    # "hierarchicalParent":food.get("hierarchicalParent")
                }
                for food in foods['nomenclatures']
                if food.get('cost') is None and food.get("hierarchicalParent") != None  # Проверяем условия
            ]
            
            if not filtered_categories:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No categories with cost = null found")
            
            return filtered_categories
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch categories: {str(e)}")

    async def get_food_by_id(self, food_id: int, session: AsyncSession) -> Food:
        """
        Получение блюда по ID
        """
        try:
            query = select(Food).where(Food.id == food_id)
            result = await session.execute(query)
            food = result.scalar_one_or_none()
            if not food:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Food not found")
            return food
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch food by ID: {str(e)}")

    async def get_food_by_name(self, name: str, session: AsyncSession) -> Food:
        """
        Получение блюда по имени
        """
        try:
            query = select(Food).where(Food.foodName == name)
            result = await session.execute(query)
            food = result.scalar_one_or_none()
            if not food:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Food not found")
            return food
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch food by name: {str(e)}")

    async def delete_food(self, food_id: int, session: AsyncSession):
        """
        Удаление блюда по ID
        """
        try:
            query = delete(Food).where(Food.id == food_id)
            result = await session.execute(query)
            if result.rowcount == 0:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Food not found for deletion")
            await session.commit()
            return {"message": "Food deleted successfully"}
        except Exception as e:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to delete food: {str(e)}")

    async def update_food(self, food_id: int, food_dto: DTO.Food, session: AsyncSession):
        """
        Обновление информации о блюде
        """
        try:
            query = update(Food).where(Food.id == food_id).values(**food_dto.model_dump())
            result = await session.execute(query)
            if result.rowcount == 0:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Food not found for update")
            await session.commit()
            return {"message": "Food updated successfully"}
        except Exception as e:
            await session.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update food: {str(e)}")

# Создаем сервис
food_service = FoodService()

# Создаем роутер
foodRouter = APIRouter()

@foodRouter.post("/")
async def add_food(
    food_dto: DTO.Food,
    session: AsyncSession = Depends(get_async_session),
):
    return await food_service.add_food(food_dto, session)

@foodRouter.post("/all")
async def add_all_foods(
    food_dto: List[DTO.Food],
    session: AsyncSession = Depends(get_async_session),
):
    for food in food_dto:
        await food_service.add_food(food, session)
    return {"message": "All foods added successfully"}


# @foodRouter.get("/")
# async def get_foods(
#     category: Optional[int] = None,
#     session: AsyncSession = Depends(get_async_session),
# ):
#     return await food_service.get_foods(session, category)

sbis = SBISService()

@foodRouter.get("/")
async def get_foods(
    point_id: Optional[int] = None,
    price_list_id: Optional[int] = None,
    session: AsyncSession = Depends(get_async_session),
):
    token: DTO.TokenValidation = await sbis.get_token(AuthorizationData(app_client_id=APP_CLIENT_ID, app_secret=APP_SECRET, app_secret_key=APP_SECRET_KEY))
    request = DTO.FoodsRequest(pointId=2378, priceListId=31)
    return await food_service.get_foods(request, token)

@foodRouter.get("/categories")
async def get_foods_categories(
    point_id: Optional[int] = None,
    price_list_id: Optional[int] = None,
    session: AsyncSession = Depends(get_async_session),
):
    token: DTO.TokenValidation = await sbis.get_token(AuthorizationData(app_client_id=APP_CLIENT_ID, app_secret=APP_SECRET, app_secret_key=APP_SECRET_KEY))
    request = DTO.FoodsRequest(pointId=2378, priceListId=31)
    return await food_service.get_foods_categories(request, token)

@foodRouter.get("/{id}")
async def get_food_by_id(
    id: int,
    session: AsyncSession = Depends(get_async_session),
):
    return await food_service.get_food_by_id(id, session)

@foodRouter.get("/search/{name}")
async def get_food_by_name(
    name: str,
    session: AsyncSession = Depends(get_async_session),
):
    return await food_service.get_food_by_name(name, session)

@foodRouter.delete("/{id}")
async def delete_food(
    id: int,
    session: AsyncSession = Depends(get_async_session),
):
    return await food_service.delete_food(id, session)

@foodRouter.patch("/{id}")
async def update_food(
    id: int,
    food_dto: DTO.Food,
    session: AsyncSession = Depends(get_async_session),
):
    return await food_service.update_food(id, food_dto, session)
