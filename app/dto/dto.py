from typing import Optional, Union, List, Dict
from pydantic import BaseModel


class User(BaseModel):
    name: Optional[str] = None
    tel: Optional[str] = None
    address: Optional[str] = None
    orders: Optional[str] = None
    nickname: Optional[str] = None
    chatID: Optional[str] = None
    favourites: Optional[List[int]] = []
    role: Optional[str] = None


class Order(BaseModel):
    number: Optional[int] = None
    items: Optional[List[Dict]] = []
    total: Optional[int] = None
    date: Optional[str] = None
    address: Optional[str] = None
    state: Optional[str] = None
    isDelivery: Optional[bool] = False
    payment: Optional[str] = None
    comment: Optional[str] = None
    client: Optional[int] = None
    cutlery: Optional[int] = None


class Category(BaseModel):
    categoryName: Optional[str] = None
    food: Optional[List] = []


class Food(BaseModel):
    foodName: Optional[str] = None
    price: Optional[int] = None
    description: Optional[str] = None
    image: Optional[str] = None
    category: Optional[int] = None


class Promo(BaseModel):
    code: Optional[str] = None
    isPercent: Optional[bool] = None
    discount: Optional[int] = None
    maxUse: Optional[int] = None
    used: Optional[List[int]] = []
    desc: Optional[str] = None


class TokenValidation(BaseModel):
    access_token: str
    sid: str
    token: str


class AuthorizationData(BaseModel):
    app_client_id: str
    app_secret: str
    secret_key: str


class FoodsRequest(BaseModel):
    pointId: int
    priceListId: int
    withBalance: Optional[bool] = True
    withBarcode: Optional[bool] = True
    onlyPublished: Optional[bool] = True
    pageSize: Optional[str] = '2000'
    noStopList: Optional[bool] = True


class CartRedis(BaseModel):
    user_id: int
    product_id: int
    quantity: int