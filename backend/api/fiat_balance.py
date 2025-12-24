from fastapi import APIRouter, Depends

from auth import get_current_user_id
from schemas import (
    CreateFiatBalanceAdRequest,
    CreateFiatBalanceBatchRequest,
    DeleteFiatBalanceAdsRequest,
    FiatBalanceConfig,
)
from services.fiat_balance_service import (
    create_fiat_balance_ad,
    create_fiat_balance_ads_batch,
    delete_fiat_balance_ads,
    get_fiat_balance_config,
)

router = APIRouter(prefix="/api/fiat-balance", tags=["fiat-balance"])


@router.get("/config", response_model=FiatBalanceConfig)
async def read_fiat_balance_config(user_id: str = Depends(get_current_user_id)) -> FiatBalanceConfig:
    return await get_fiat_balance_config(user_id)


@router.post("/create")
async def create_ad(
    payload: CreateFiatBalanceAdRequest,
    user_id: str = Depends(get_current_user_id),
):
    return await create_fiat_balance_ad(user_id, payload)


@router.post("/create-batch")
async def create_batch(
    payload: CreateFiatBalanceBatchRequest,
    user_id: str = Depends(get_current_user_id),
):
    return await create_fiat_balance_ads_batch(user_id, payload)


@router.post("/delete-by-remark")
async def delete_by_remark(
    payload: DeleteFiatBalanceAdsRequest,
    user_id: str = Depends(get_current_user_id),
):
    return await delete_fiat_balance_ads(user_id, payload)
