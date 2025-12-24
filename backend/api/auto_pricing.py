from fastapi import APIRouter, Depends

from auth import get_current_user_id
from schemas import AutoPricingStatusResponse
from services.auto_pricing_service import auto_pricing_worker

router = APIRouter(prefix="/api/auto-pricing", tags=["auto-pricing"])


@router.get("/status", response_model=AutoPricingStatusResponse)
async def get_auto_pricing_status(
    user_id: str = Depends(get_current_user_id),
) -> AutoPricingStatusResponse:
    return AutoPricingStatusResponse(**auto_pricing_worker.get_status())


@router.post("/start", response_model=AutoPricingStatusResponse)
async def start_auto_pricing(
    user_id: str = Depends(get_current_user_id),
) -> AutoPricingStatusResponse:
    await auto_pricing_worker.start()
    return AutoPricingStatusResponse(**auto_pricing_worker.get_status())


@router.post("/stop", response_model=AutoPricingStatusResponse)
async def stop_auto_pricing(
    user_id: str = Depends(get_current_user_id),
) -> AutoPricingStatusResponse:
    await auto_pricing_worker.stop()
    return AutoPricingStatusResponse(**auto_pricing_worker.get_status())
