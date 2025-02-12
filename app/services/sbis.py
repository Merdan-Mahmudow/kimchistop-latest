from io import BytesIO
import json
import base64
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from aiohttp import ClientSession, ClientTimeout
import requests
from PIL import Image
from services.redis_service import RedisService
from dto.dto import AuthorizationData, FoodsRequest, TokenValidation
from exceptions.sbis import SBISAuthError, SBISRequestError

logger = logging.getLogger(__name__)


class SBISService:

    def __init__(self):
        self.timeout = ClientTimeout(total=30)
        self.session = ClientSession(timeout=self.timeout)
        self._token_cache = {}

    async def __aenter__(self):
        if not self.session or self.session.closed:
            self.session = ClientSession(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session and not self.session.closed:
            await self.session.close()

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def get_token(self, data: AuthorizationData) -> TokenValidation:
        cached_token = self._token_cache.get(data.app_client_id)
        if cached_token and cached_token['expires_at'] > datetime.now():
            return cached_token['token']

        try:
            async with self.session.post(
                'https://online.sbis.ru/oauth/service/',
                json=AuthorizationData(app_client_id=data.app_client_id,
                                       app_secret=data.app_secret,
                                       secret_key=data.secret_key).model_dump()
            ) as response:
                if response.status != 200:
                    print(response.content)
                    raise SBISAuthError()

                token_data = await response.json()
                token = TokenValidation(**token_data)
                self._token_cache[data.app_client_id] = {
                    'token': token,
                    'expires_at': datetime.now() + timedelta(hours=1)
                }
                return token
        except Exception as e:
            logger.error(f"Failed to fetch token: {str(e)}")
            raise SBISAuthError()

    async def _make_request(self, method: str, url: str, **kwargs) -> Dict:
        retries = 3
        for attempt in range(retries):
            try:
                async with self.session.request(method, url, **kwargs) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 401 and attempt < retries - 1:
                        self._token_cache.clear()
                        continue
                    else:
                        raise SBISRequestError(f"Status: {response.status}")
            except Exception as e:
                if attempt == retries - 1:
                    logger.error(f"Request failed after {
                                 retries} attempts: {str(e)}")
                    raise SBISRequestError(str(e))
                await asyncio.sleep(1)

    @staticmethod
    async def get_point_id(token: TokenValidation) -> dict:
        url = 'https://api.sbis.ru/retail/point/list'
        headers = {"X-SBISAccessToken": token.access_token}
        params = {
            'withPhones': 'true',
            'withPrices': 'true'
        }
        response = requests.get(url, params=params, headers=headers)
        return response.json()

    @staticmethod
    async def get_price_lists(token: TokenValidation, point_id: int) -> dict:
        parameters = {
            'pointId': point_id,
            'actualDate': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        url = 'https://api.sbis.ru/retail/nomenclature/price-list?'
        headers = {"X-SBISAccessToken": token.access_token}
        response = requests.get(url, params=parameters, headers=headers)
        return response.json()

    @staticmethod
    async def get_foods(request: FoodsRequest, token: TokenValidation) -> dict:
        parameters = request.model_dump()
        url = 'https://api.sbis.ru/retail/nomenclature/list?'
        headers = {"X-SBISAccessToken": token.access_token}
        response = requests.get(url, params=parameters, headers=headers)
        return response.json()

    @staticmethod
    async def get_image(token: TokenValidation, image: str, name: str) -> str:
        url = "https://api.sbis.ru/retail/img"
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "image/*",
            "X-SBISAccessToken": token.access_token
        }
        replaced = image.replace("/img?params=", "")
        params = {"params": replaced}
        response = requests.get(url, params=params, headers=headers)

        if response.status_code == 200:
            try:
                image_data = BytesIO(response.content)
                img = Image.open(image_data)
                img.save(f"images/{name}.png")
                return f"Image saved as {name}.png"
            except Exception as e:
                return f"Failed to process image: {str(e)}"
        else:
            return f"Error while reading response: {response.status_code}, {response.text}"

    @staticmethod
    def decode_base64_param(encoded_param: str) -> Optional[str]:
        try:
            decoded_bytes = base64.b64decode(encoded_param)
            decoded_str = decoded_bytes.decode('utf-8')
            decoded_json = json.loads(decoded_str)
            return decoded_json.get('PhotoURL')
        except Exception:
            return None


class SBISBusinessLogic:

    def __init__(self, sbis_service: SBISService, redis_service: RedisService):
        self.sbis = sbis_service
        self.redis = redis_service
        self._categories_cache = {}
        self._products_cache = {}

    async def update_products_cache(self, auth_data: AuthorizationData) -> None:
        try:
            products = await self.get_from_primary(auth_data)
            await self.redis.set_products(products)
            logger.info("Products cache updated successfully")
        except Exception as e:
            logger.error(f"Failed to update products cache: {e}")

    async def get_point_info(self, auth_data: AuthorizationData) -> dict:
        token = await self.sbis.get_token(auth_data)
        point_id = await self.sbis.get_point_id(token)
        menu = await self.sbis.get_price_lists(token, point_id['salesPoints'][0]['id'])
        return point_id

    async def get_all_categories(self, auth_data: AuthorizationData) -> List[Dict]:
        cache_key = auth_data.app_client_id
        cached_data = self._categories_cache.get(cache_key)

        if cached_data and cached_data['expires_at'] > datetime.now():
            return cached_data['data']

        try:
            categories = await self._fetch_categories(auth_data)
            self._categories_cache[cache_key] = {
                'data': categories,
                'expires_at': datetime.now() + timedelta(minutes=15)
            }
            return categories
        except Exception as e:
            logger.error(f"Failed to fetch categories: {str(e)}")
            raise

    async def get_from_primary(self, auth_data: AuthorizationData) -> List[Dict[str, Any]]:
        token = await self.sbis.get_token(auth_data)
        point_id = await self.sbis.get_point_id(token)
        menu = await self.sbis.get_price_lists(token, point_id['salesPoints'][0]['id'])
        foods = await self.sbis.get_foods(
            FoodsRequest(
                pointId=point_id['salesPoints'][0]['id'],
                priceListId=menu["priceLists"][3]["id"],
                withBalance=True,
                withBarcode=False,
                onlyPublished=False,
            ),
            token
        )

        tasks = []

        async def process_item(item: Dict) -> Optional[Dict]:
            # nonlocal downloaded_count
            if ('images' in item and item['images'] and
                    item.get("hierarchicalParent") != 2382):

                image_url = item['images'][0]
                encoded_param = image_url.split('?params=')[-1]
                photo_url = self.sbis.decode_base64_param(encoded_param)

                if photo_url:
                    # downloaded_count += 1
                    return {
                        "id": item["hierarchicalId"],
                        "name": item["name"],
                        "status": "available",
                        "image": photo_url,
                        "price": item["cost"],
                        "description": item["description_simple"]
                    }
            return None

        for item in foods['nomenclatures']:
            # if downloaded_count >= max_downloads:
                # break
            tasks.append(process_item(item))

        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]

    async def get_kitchen_products(self, auth_data: AuthorizationData) -> List[Dict[str, Any]]:
        cached_products = await self.redis.get_products()
        if cached_products:
            return cached_products
        else:
            return await self.get_from_primary(auth_data)

    async def get_product_details(self, auth_data: AuthorizationData, product_id: int) -> Dict:
        cached_product = await self.redis.get_product(product_id)
        if cached_product:
            return cached_product

        cache_key = f"{auth_data.app_client_id}:{product_id}"
        cached_data = self._products_cache.get(cache_key)

        if cached_data and cached_data['expires_at'] > datetime.now():
            return cached_data['data']

        try:
            product = await self._fetch_product(auth_data, product_id)
            if product['status'] == "Product found":
                self._products_cache[cache_key] = {
                    'data': product,
                    'expires_at': datetime.now() + timedelta(minutes=5)
                }
            return product
        except Exception as e:
            logger.error(f"Failed to fetch product {product_id}: {str(e)}")
            raise

    async def _fetch_categories(self, auth_data: AuthorizationData) -> List[Dict]:
        token = await self.sbis.get_token(auth_data)
        point_id = await self.sbis.get_point_id(token)
        menu = await self.sbis.get_price_lists(token, point_id['salesPoints'][0]['id'])
        foods = await self.sbis.get_foods(
            FoodsRequest(
                pointId=point_id['salesPoints'][0]['id'],
                priceListId=menu["priceLists"][1]["id"]
            ),
            token
        )
        return [
            item for item in foods["nomenclatures"]
            if item.get("hierarchicalParent") == 2110
        ]

    async def _fetch_product(self, auth_data: AuthorizationData, product_id: int) -> Dict:
        token = await self.sbis.get_token(auth_data)
        point_id = await self.sbis.get_point_id(token)
        menu = await self.sbis.get_price_lists(token, point_id['salesPoints'][0]['id'])
        foods = await self.sbis.get_foods(
            FoodsRequest(
                pointId=point_id['salesPoints'][0]['id'],
                priceListId=menu["priceLists"][3]["id"],
                withBalance=True,
                withBarcode=False,
                onlyPublished=False,
            ),
            token
        )

        product = next(
            (item for item in foods['nomenclatures']
             if item['hierarchicalId'] == product_id),
            None
        )

        if not product:
            return {"status": "Product not found", "id": product_id}

        photo_url = None
        if 'images' in product and product['images']:
            image_url = product['images'][0]
            encoded_param = image_url.split('?params=')[-1]
            photo_url = self.sbis.decode_base64_param(encoded_param)

        return {
            "id": product["hierarchicalId"],
            "name": product["name"],
            "image": photo_url,
            "price": product["cost"],
            "description": product["description_simple"],
            "status": "Product found"
        }
