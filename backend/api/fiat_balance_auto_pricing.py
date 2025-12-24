from fastapi import APIRouter, Depends

from auth import get_current_user_id
from schemas import AutoPricingStatusResponse
from schemas_fiat_auto import FiatAutoStartRequest
from services.fiat_balance_auto_pricing_service import (
    fiat_balance_auto_worker,
)

router = APIRouter(prefix="/api/fiat-balance-auto-pricing", tags=["fiat-balance-auto-pricing"])


@router.get("/status", response_model=AutoPricingStatusResponse)
async def get_status(user_id: str = Depends(get_current_user_id)) -> AutoPricingStatusResponse:
    return AutoPricingStatusResponse(**fiat_balance_auto_worker.get_status())


@router.post("/start", response_model=AutoPricingStatusResponse)
async def start_worker(
    payload: FiatAutoStartRequest,
    user_id: str = Depends(get_current_user_id),
) -> AutoPricingStatusResponse:
    fiat_balance_auto_worker.set_config(sell=payload.sell, buy=payload.buy)
    await fiat_balance_auto_worker.start()
    return AutoPricingStatusResponse(**fiat_balance_auto_worker.get_status())


@router.post("/stop", response_model=AutoPricingStatusResponse)
async def stop_worker(user_id: str = Depends(get_current_user_id)) -> AutoPricingStatusResponse:
    await fiat_balance_auto_worker.stop()
    return AutoPricingStatusResponse(**fiat_balance_auto_worker.get_status())
