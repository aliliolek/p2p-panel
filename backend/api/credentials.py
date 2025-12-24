from fastapi import APIRouter, Depends, HTTPException, Response, status

from auth import get_current_user_id
from exchanges import SUPPORTED_EXCHANGES
from schemas import CredentialCreate, CredentialListResponse, CredentialResponse
from services import credentials_service

router = APIRouter(prefix="/api/exchanges/credentials", tags=["credentials"])


@router.get("", response_model=CredentialListResponse)
async def list_credentials(
    user_id: str = Depends(get_current_user_id),
) -> CredentialListResponse:
    items = await credentials_service.list_credentials(user_id)
    return CredentialListResponse(items=items)


@router.post("", response_model=CredentialResponse, status_code=status.HTTP_201_CREATED)
async def create_credential(
    payload: CredentialCreate,
    user_id: str = Depends(get_current_user_id),
) -> CredentialResponse:
    if payload.exchange not in SUPPORTED_EXCHANGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported exchange",
        )
    return await credentials_service.create_credential(user_id, payload)


@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    credential_id: str,
    user_id: str = Depends(get_current_user_id),
) -> Response:
    deleted = await credentials_service.delete_credential(user_id, credential_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
