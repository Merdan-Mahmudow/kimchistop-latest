import asyncio
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from auth.database import get_async_session
from models.models import Order, User, Food

userRouter = APIRouter()

# In-memory state dictionary to store user objects
user_state = {}

def is_null(value):
    return value is None

# DTO Model for User
class UserDTO(BaseModel):
    name: Optional[str] = None
    tel: Optional[str] = None
    address: Optional[str] = None
    orders: Optional[str] = None
    nickname: Optional[str] = None
    chatID: Optional[str] = None
    favourites: List[int] = []
    role: Optional[str] = None

class UserCRUD:
    @staticmethod
    async def fetch_user_by_nickname(nickname: str, session: AsyncSession):
        query = select(User).where(User.nickname == nickname)
        result = await session.execute(query)
        return result.scalars().first()

    @staticmethod
    async def insert_user(user_dto: dict, session: AsyncSession):
        query = insert(User).values(user_dto)
        await session.execute(query)
        await session.commit()

    @staticmethod
    async def update_user(nickname: str, user_dto: dict, session: AsyncSession):
        query = update(User).where(User.nickname == nickname).values(user_dto)
        await session.execute(query)
        await session.commit()

    @staticmethod
    async def delete_user(nickname: str, session: AsyncSession):
        query = delete(User).where(User.nickname == nickname)
        await session.execute(query)
        await session.commit()
    
    @staticmethod
    async def delete_user_order(id: str, session: AsyncSession):
        query = delete(Order).where(Order.client == id)
        await session.execute(query)
        await session.commit()

    @staticmethod
    async def fetch_user_by_id(user_id: int, session: AsyncSession):
        query = select(User.nickname).where(User.id == user_id)
        result = await session.execute(query)
        return result.scalars().first()

    @staticmethod
    async def fetch_favourites(favourites: List[int], session: AsyncSession):
        foods = []
        for food_id in favourites:
            query = select(Food).where(Food.id == food_id)
            result = await session.execute(query)
            food = result.scalars().first()
            if food:
                foods.append(food)
        return foods

class UserService:
    @staticmethod
    async def add_user_to_state(nickname: str, user, state: dict):
        state[nickname] = user
        state[nickname].favourites = list(map(int, user.favourites or []))

@userRouter.post('/setstate', status_code=status.HTTP_201_CREATED)
async def set_user_state(nickname: str, session: AsyncSession = Depends(get_async_session)):
    if nickname in user_state:
        return {"message": "User already in state"}

    user = await UserCRUD.fetch_user_by_nickname(nickname, session)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await UserService.add_user_to_state(nickname, user, user_state)
    return {"message": "User added to state"}

@userRouter.get('/{nickname}')
async def get_user(nickname: str, session: AsyncSession = Depends(get_async_session)):
    if nickname in user_state:
        return user_state[nickname]

    user = await UserCRUD.fetch_user_by_nickname(nickname, session)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await UserService.add_user_to_state(nickname, user, user_state)
    return user_state[nickname]

@userRouter.post('/')
async def add_user(user_dto: UserDTO, session: AsyncSession = Depends(get_async_session)):
    try:
        await UserCRUD.insert_user(user_dto.dict(), session)
        user_state[user_dto.nickname] = user_dto.dict()
        return {"message": "User added successfully"}
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@userRouter.patch('/{nickname}')
async def update_user(nickname: str, user_dto: UserDTO, session: AsyncSession = Depends(get_async_session)):
    try:
        await UserCRUD.update_user(nickname, user_dto.dict(exclude_unset=True), session)

        if nickname in user_state:
            user_state[nickname].update(user_dto.dict(exclude_unset=True))

        return {"message": "User updated successfully"}
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@userRouter.get('/{nickname}/fav')
async def get_user_favourites(nickname: str, session: AsyncSession = Depends(get_async_session)):
    if nickname not in user_state:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    favourites: list
    if nickname in user_state:
        favourites = user_state[nickname].favourites
    else:
        favourites = []
    return await UserCRUD.fetch_favourites(favourites, session)

@userRouter.patch('/{nickname}/fav')
async def update_favourites(nickname: str, favourite_item: int, session: AsyncSession = Depends(get_async_session)):
    if nickname not in user_state:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    favourites: list
    if nickname in user_state:
        favourites = user_state[nickname].favourites
    else:
        favourites = []
    
    if favourite_item in favourites:
        favourites.remove(favourite_item)
    else:
        favourites.append(favourite_item)
    await UserCRUD.update_user(nickname, {"favourites": favourites}, session)
    return await UserCRUD.fetch_favourites(favourites, session)

@userRouter.delete('/{nickname}')
async def delete_user(id: int, nickname: str,  session: AsyncSession = Depends(get_async_session)):
    try:
        await UserCRUD.delete_user_order(id, session)
        await UserCRUD.delete_user(nickname, session)
        if nickname in user_state:
            del user_state[nickname]
            return {"message": "User deleted successfully", "state": user_state}
        else:
            return ["user not found", user_state]
        
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@userRouter.patch('/role/{nickname}')
async def update_user_role(nickname: str, role: str, session: AsyncSession = Depends(get_async_session)):
    try:
        await UserCRUD.update_user(nickname, {"role": role}, session)

        if nickname in user_state:
            user_state[nickname].role = role

        return {"message": "User role updated successfully"}
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@userRouter.get('/id/{id}')
async def get_user_by_id(user_id: int, session: AsyncSession = Depends(get_async_session)):
    data = await UserCRUD.fetch_user_by_id(user_id, session)
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {"nickname": data}
