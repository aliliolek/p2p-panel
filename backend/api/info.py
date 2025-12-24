from fastapi import APIRouter, Depends

from auth import get_current_user_id
from schemas import ApiInfoResponse
from services.info_service import get_api_info

router = APIRouter(prefix="/api", tags=["info"])


@router.get("/info", response_model=ApiInfoResponse)
async def read_info(
    user_id: str = Depends(get_current_user_id),
) -> ApiInfoResponse:
    _ = user_id
    return await get_api_info()
