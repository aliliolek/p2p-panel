from fastapi import APIRouter, Depends, HTTPException, status

from auth import get_current_user_id
from schemas import (
    AdActivateRequest,
    AdActivateResponse,
    AdOfflineRequest,
    AdOfflineResponse,
    AdToggleAutoRequest,
    AdToggleAutoResponse,
    AdsResponse,
)
from services.ads_service import activate_ad, get_ads, take_ad_offline, toggle_auto_marker

router = APIRouter(prefix="/api/ads", tags=["ads"])


@router.get("", response_model=AdsResponse)
async def read_ads(user_id: str = Depends(get_current_user_id)) -> AdsResponse:
    accounts = await get_ads(user_id)
    return AdsResponse(accounts=accounts)


@router.post("/toggle-auto", response_model=AdToggleAutoResponse)
async def toggle_auto(
    payload: AdToggleAutoRequest,
    user_id: str = Depends(get_current_user_id),
) -> AdToggleAutoResponse:
    try:
        result = await toggle_auto_marker(
            user_id,
            payload.credential_id,
            payload.ad_id,
            payload.enable,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return AdToggleAutoResponse(**result)


@router.post("/offline", response_model=AdOfflineResponse)
async def offline_ad(
    payload: AdOfflineRequest,
    user_id: str = Depends(get_current_user_id),
) -> AdOfflineResponse:
    try:
        result = await take_ad_offline(
            user_id,
            payload.credential_id,
            payload.ad_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
    ) from exc
    return AdOfflineResponse(**result)


@router.post("/activate", response_model=AdActivateResponse)
async def activate(
    payload: AdActivateRequest,
    user_id: str = Depends(get_current_user_id),
) -> AdActivateResponse:
    try:
        result = await activate_ad(
            user_id,
            payload.credential_id,
            payload.ad_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return AdActivateResponse(**result)
