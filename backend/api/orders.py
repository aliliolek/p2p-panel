from fastapi import APIRouter, Depends

from auth import get_current_user_id
from schemas import PendingOrdersResponse
from services.orders_service import get_pending_orders

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.get("/pending", response_model=PendingOrdersResponse)
async def read_pending_orders(
    user_id: str = Depends(get_current_user_id),
) -> PendingOrdersResponse:
    accounts = await get_pending_orders(user_id)
    return PendingOrdersResponse(accounts=accounts)
