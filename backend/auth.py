from fastapi import Header, HTTPException, status
import httpx

from config import settings


async def _fetch_user(access_token: str) -> dict:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "apikey": settings.supabase_service_role_key,
    }
    url = f"{settings.supabase_url}/auth/v1/user"
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(url, headers=headers)
    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth token"
        )
    return response.json()


async def get_current_user_id(
    authorization: str | None = Header(default=None, convert_underscores=False),
) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing auth token"
        )
    token = authorization.split(" ", 1)[1]
    user = await _fetch_user(token)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user profile"
        )
    return user_id
