import logging
import os
from typing import Dict, List
from fastapi import APIRouter, HTTPException, status

from services import redis_service
from services.sbis import SBISService, SBISBusinessLogic
from services.sbis import SBISService as sbis_service
from exceptions.sbis import SBISAuthError, SBISRequestError
from main import auth_data

sbis_logic = SBISBusinessLogic(sbis_service, redis_service.RedisService())

logging.basicConfig(level=logging.INFO)
sbisRouter = APIRouter()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

async def get_sbis_service():
    async with SBISService() as service:
        yield service

@sbisRouter.post('/register')
async def register() -> Dict:
    try:
        async with SBISService() as service:
            return await sbis_logic.get_point_info(auth_data)
    except SBISAuthError as e:
        logger.error(f"Authentication failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )
    except SBISRequestError as e:
        logger.error(f"Request failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@sbisRouter.get("/categories")
async def get_categories() -> List[Dict]:
    try:
        async with SBISService() as service:
            return await sbis_logic.get_all_categories(auth_data)
    except SBISAuthError as e:
        logger.error(f"Authentication failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )
    except SBISRequestError as e:
        logger.error(f"Request failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@sbisRouter.get("/sbis-products")
async def get_kitchen_products() -> List[Dict]:
    try:
        return await sbis_logic.get_kitchen_products(auth_data)
    except Exception as e:
        logger.error(f"Failed to get products: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@sbisRouter.get("/sbis-product/{product_id}")
async def get_product_by_id(product_id: int) -> Dict:
    try:
        async with SBISService() as service:
            return await sbis_logic.get_product_details(auth_data, product_id)
    except SBISAuthError as e:
        logger.error(f"Authentication failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )
    except SBISRequestError as e:
        logger.error(f"Request failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
